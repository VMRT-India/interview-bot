import secrets
import uuid

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.postgres import get_db
from db.redis import get_redis
from models.pg.oauth_identity import OAuthIdentity
from models.pg.user import User
from models.pg.user_api_key import UserAPIKey
from models.schemas.auth import (
    ChangePasswordRequest,
    LinkEmailRequest,
    LinkPhoneRequest,
    LoginRequest,
    SetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UserRead,
)
from models.schemas.user_api_key import UserAPIKeyCreate, UserAPIKeyRead
from services import crypto_service
from services.auth_service import create_access_token, hash_password, normalize_email, verify_password
from api.dependencies import get_current_user

router = APIRouter(prefix="/auth")
logger = structlog.get_logger()

_OAUTH_STATE_TTL = 600

_PROVIDERS = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
        "client_id": lambda: settings.google_client_id,
        "client_secret": lambda: settings.google_client_secret,
    },
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scope": "read:user user:email",
        "client_id": lambda: settings.github_client_id,
        "client_secret": lambda: settings.github_client_secret,
    },
    "microsoft": {
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/oidc/userinfo",
        "scope": "openid email profile",
        "client_id": lambda: settings.microsoft_client_id,
        "client_secret": lambda: settings.microsoft_client_secret,
    },
}


# ---------------------------------------------------------------------------
# Email / phone + password
# ---------------------------------------------------------------------------


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    email = normalize_email(body.email)

    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")
    existing = await db.execute(select(User).where(User.phone_number == body.phone_number))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Phone number already registered")

    try:
        password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    user = User(email=email, phone_number=body.phone_number, password_hash=password_hash)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("user_signed_up", user_id=str(user.id))
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    identifier = normalize_email(body.identifier)
    result = await db.execute(
        select(User).where(or_(User.email == identifier, User.phone_number == identifier))
    )
    user = result.scalar_one_or_none()
    if not user or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    logger.info("user_logged_in", user_id=str(user.id))
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/guest", response_model=TokenResponse, status_code=201)
async def create_guest(db: AsyncSession = Depends(get_db)):
    """No-signup trial account — no email/phone/password. Capped to one free
    session by services.llm_service's free-tier quota check (is_guest -> limit 1),
    same as a regular account's quota but tighter. Purely a browser-token identity,
    not abuse-hardened (see TODO.md)."""
    user = User(is_guest=True)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("guest_created", user_id=str(user.id))
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me/link-email", response_model=UserRead)
async def link_email(
    body: LinkEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Attaches an email to an account that only has a phone number so far.

    Having both identifiers on one account makes multi-accounting meaningfully harder
    (phone numbers are scarce; email addresses are not) — this is intentionally a
    one-time attach, not an update: an account that already has an email must go
    through a separate change-email flow (not yet built) rather than silently
    overwriting the existing one here.
    """
    if current_user.email:
        raise HTTPException(status_code=409, detail="Account already has an email linked")

    email = normalize_email(body.email)
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered to another account")

    current_user.email = email
    await db.commit()
    await db.refresh(current_user)
    logger.info("email_linked", user_id=str(current_user.id))
    return current_user


@router.put("/me/link-phone", response_model=UserRead)
async def link_phone(
    body: LinkPhoneRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Attaches a phone number to an account that only has an email so far. See
    link_email() for why this matters and why it's attach-once, not update."""
    if current_user.phone_number:
        raise HTTPException(status_code=409, detail="Account already has a phone number linked")

    existing = await db.execute(
        select(User).where(User.phone_number == body.phone_number)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="Phone number already registered to another account"
        )

    current_user.phone_number = body.phone_number
    await db.commit()
    await db.refresh(current_user)
    logger.info("phone_linked", user_id=str(current_user.id))
    return current_user


@router.put("/me/set-password", response_model=UserRead)
async def set_password(
    body: SetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """For accounts with no password yet (created via OAuth) — lets the user set one so
    they're not locked into a single login provider. Use change_password() instead if the
    account already has one."""
    if current_user.password_hash:
        raise HTTPException(
            status_code=409, detail="Account already has a password — use change-password instead"
        )

    try:
        current_user.password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    await db.commit()
    await db.refresh(current_user)
    logger.info("password_set", user_id=str(current_user.id))
    return current_user


@router.put("/me/change-password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.password_hash or not verify_password(
        body.current_password, current_user.password_hash
    ):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    try:
        current_user.password_hash = hash_password(body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    await db.commit()
    logger.info("password_changed", user_id=str(current_user.id))


@router.put("/me/reset-password", response_model=UserRead)
async def reset_password(
    body: SetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """"Forgot password" flow with no email/SMS service required: the user re-authenticates
    via a linked OAuth provider (Google/GitHub) — proof of identity — and sets a brand new
    password from that authenticated session, without needing to know the old one.

    Deliberately unrestricted (unlike change_password, no current-password check) — the
    caller already proved who they are by obtaining a valid JWT, whether via OAuth login
    or an existing password login. Frontend should surface this specifically as part of an
    OAuth-based recovery flow, not as a general-purpose "change password without knowing it"
    button, to avoid an attacker who steals a live session token silently taking over the
    password login path too.

    Caveat: this only helps users who have at least one OAuth provider linked. An account
    with only email/phone + password and no linked OAuth has no recovery path today — that
    would need real email or SMS delivery, deliberately not built to avoid that cost/complexity.
    """
    try:
        current_user.password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    await db.commit()
    await db.refresh(current_user)
    logger.info("password_reset_via_reauth", user_id=str(current_user.id))
    return current_user


# ---------------------------------------------------------------------------
# BYOK — bring your own LLM API key
# ---------------------------------------------------------------------------


@router.put("/me/api-keys", response_model=UserAPIKeyRead)
async def upsert_api_key(
    body: UserAPIKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.user_id == current_user.id, UserAPIKey.provider == body.provider
        )
    )
    existing = result.scalar_one_or_none()
    encrypted = crypto_service.encrypt(body.api_key)

    if existing:
        existing.encrypted_key = encrypted
        existing.model_name = body.model_name
        existing.base_url = body.base_url
        await db.commit()
        await db.refresh(existing)
        return existing

    key_row = UserAPIKey(
        user_id=current_user.id,
        provider=body.provider,
        encrypted_key=encrypted,
        model_name=body.model_name,
        base_url=body.base_url,
    )
    db.add(key_row)
    await db.commit()
    await db.refresh(key_row)
    logger.info("byok_key_stored", user_id=str(current_user.id), provider=body.provider)
    return key_row


@router.get("/me/api-keys", response_model=list[UserAPIKeyRead])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UserAPIKey).where(UserAPIKey.user_id == current_user.id))
    return list(result.scalars().all())


@router.delete("/me/api-keys/{provider}", status_code=204)
async def delete_api_key(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserAPIKey).where(
            UserAPIKey.user_id == current_user.id, UserAPIKey.provider == provider
        )
    )
    key_row = result.scalar_one_or_none()
    if not key_row:
        raise HTTPException(status_code=404, detail="No stored key for this provider")
    await db.delete(key_row)
    await db.commit()


# ---------------------------------------------------------------------------
# OAuth — Google / GitHub / Microsoft
# ---------------------------------------------------------------------------


def _require_configured(provider: str) -> dict:
    cfg = _PROVIDERS.get(provider)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    if not cfg["client_id"]() or not cfg["client_secret"]():
        raise HTTPException(
            status_code=501,
            detail=f"{provider} OAuth is not configured yet (missing client_id/client_secret)",
        )
    return cfg


def _oauth_redirect_uri(provider: str) -> str:
    path = settings.oauth_callback_path_template.format(provider=provider)
    return f"{settings.oauth_redirect_base_url}{path}"


@router.get("/{provider}/login")
async def oauth_login(provider: str):
    cfg = _require_configured(provider)
    state = secrets.token_urlsafe(32)
    await get_redis().set(f"oauth_state:{state}", provider, ex=_OAUTH_STATE_TTL)

    redirect_uri = _oauth_redirect_uri(provider)
    params = {
        "client_id": cfg["client_id"](),
        "redirect_uri": redirect_uri,
        "scope": cfg["scope"],
        "state": state,
        "response_type": "code",
    }
    query = str(httpx.QueryParams(params))
    return RedirectResponse(f"{cfg['authorize_url']}?{query}")


@router.get("/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    cfg = _require_configured(provider)

    stored_provider = await get_redis().get(f"oauth_state:{state}")
    if not stored_provider or stored_provider != provider:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    await get_redis().delete(f"oauth_state:{state}")

    redirect_uri = _oauth_redirect_uri(provider)

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            cfg["token_url"],
            data={
                "client_id": cfg["client_id"](),
                "client_secret": cfg["client_secret"](),
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        userinfo_resp = await client.get(
            cfg["userinfo_url"], headers={"Authorization": f"Bearer {access_token}"}
        )
        userinfo_resp.raise_for_status()
        userinfo = userinfo_resp.json()

        email = userinfo.get("email")
        if not email and provider == "github":
            # GitHub's /user endpoint omits email unless the user made it public —
            # fetch it from /user/emails instead (requires the user:email scope).
            emails_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            emails_resp.raise_for_status()
            primary = next(
                (e for e in emails_resp.json() if e.get("primary") and e.get("verified")), None
            )
            email = primary["email"] if primary else None

        if email:
            email = normalize_email(email)

    provider_user_id = str(userinfo.get("sub") or userinfo.get("id"))

    result = await db.execute(
        select(OAuthIdentity).where(
            OAuthIdentity.provider == provider,
            OAuthIdentity.provider_user_id == provider_user_id,
        )
    )
    identity = result.scalar_one_or_none()

    if identity:
        user_result = await db.execute(select(User).where(User.id == identity.user_id))
        user = user_result.scalar_one()
    else:
        # Link to an existing account with the same email (e.g. signed up via password,
        # or already linked a different OAuth provider) rather than erroring on the
        # unique-email constraint or creating a duplicate account.
        user = None
        if email:
            existing_result = await db.execute(select(User).where(User.email == email))
            user = existing_result.scalar_one_or_none()

        if not user:
            user = User(email=email)
            db.add(user)
            await db.flush()

        db.add(
            OAuthIdentity(user_id=user.id, provider=provider, provider_user_id=provider_user_id)
        )
        await db.commit()
        await db.refresh(user)

    logger.info("oauth_login_success", provider=provider, user_id=str(user.id))
    return TokenResponse(access_token=create_access_token(user.id))
