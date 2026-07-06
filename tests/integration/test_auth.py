import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from config import settings
from models.pg.user import User
from services.auth_service import create_access_token


def _fake_phone() -> str:
    return f"+1555{uuid.uuid4().int % 10**7:07d}"


def _mock_oauth_httpx(email: str, provider_user_id: str = "12345"):
    """Mocks the token-exchange + userinfo calls oauth_callback makes via httpx.AsyncClient."""
    token_resp = MagicMock()
    token_resp.raise_for_status = MagicMock()
    token_resp.json = MagicMock(return_value={"access_token": "fake-provider-token"})

    userinfo_resp = MagicMock()
    userinfo_resp.raise_for_status = MagicMock()
    userinfo_resp.json = MagicMock(return_value={"sub": provider_user_id, "email": email})

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=token_resp)
    mock_client.get = AsyncMock(return_value=userinfo_resp)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


async def _seed_oauth_style_user(pg_test_engine, email: str | None = None, phone: str | None = None):
    """Creates a user the way OAuth login would (email only, no password) — used to test
    endpoints that only make sense for such accounts (set-password, link-phone)."""
    factory = async_sessionmaker(pg_test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        user = User(email=email, phone_number=phone)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def test_signup_with_email_and_phone_returns_token(client):
    resp = await client.post(
        "/auth/signup",
        json={
            "email": f"a-{uuid.uuid4()}@example.com",
            "phone_number": _fake_phone(),
            "password": "hunter22",
        },
    )
    assert resp.status_code == 201
    assert "access_token" in resp.json()


async def test_signup_without_email_fails(client):
    resp = await client.post(
        "/auth/signup", json={"phone_number": _fake_phone(), "password": "hunter22"}
    )
    assert resp.status_code == 422


async def test_signup_without_phone_fails(client):
    resp = await client.post(
        "/auth/signup", json={"email": f"b-{uuid.uuid4()}@example.com", "password": "hunter22"}
    )
    assert resp.status_code == 422


async def test_signup_without_email_or_phone_fails(client):
    resp = await client.post("/auth/signup", json={"password": "hunter22"})
    assert resp.status_code == 422


async def test_signup_duplicate_email_fails(client):
    email = f"dup-{uuid.uuid4()}@example.com"
    body = {"email": email, "phone_number": _fake_phone(), "password": "hunter22"}
    await client.post("/auth/signup", json=body)
    resp = await client.post(
        "/auth/signup", json={**body, "phone_number": _fake_phone()}
    )
    assert resp.status_code == 409


async def test_signup_duplicate_phone_fails(client):
    phone = _fake_phone()
    await client.post(
        "/auth/signup",
        json={"email": f"p1-{uuid.uuid4()}@example.com", "phone_number": phone, "password": "hunter22"},
    )
    resp = await client.post(
        "/auth/signup",
        json={"email": f"p2-{uuid.uuid4()}@example.com", "phone_number": phone, "password": "hunter22"},
    )
    assert resp.status_code == 409


async def test_signup_blocks_gmail_dot_alias(client):
    tag = uuid.uuid4().hex[:8]
    await client.post(
        "/auth/signup",
        json={"email": f"{tag}@gmail.com", "phone_number": _fake_phone(), "password": "hunter22"},
    )
    dotted = ".".join(tag)  # e.g. "a1b2c3d4" -> "a.1.b.2.c.3.d.4"
    resp = await client.post(
        "/auth/signup",
        json={
            "email": f"{dotted}@gmail.com",
            "phone_number": _fake_phone(),
            "password": "hunter22",
        },
    )
    assert resp.status_code == 409


async def test_signup_blocks_gmail_plus_alias(client):
    tag = uuid.uuid4().hex[:8]
    await client.post(
        "/auth/signup",
        json={"email": f"{tag}@gmail.com", "phone_number": _fake_phone(), "password": "hunter22"},
    )
    resp = await client.post(
        "/auth/signup",
        json={
            "email": f"{tag}+work@gmail.com",
            "phone_number": _fake_phone(),
            "password": "hunter22",
        },
    )
    assert resp.status_code == 409


async def test_login_with_gmail_alias_matches_original_account(client):
    tag = uuid.uuid4().hex[:8]
    signup_resp = await client.post(
        "/auth/signup",
        json={"email": f"{tag}@gmail.com", "phone_number": _fake_phone(), "password": "hunter22"},
    )
    original_user_id = pyjwt.decode(
        signup_resp.json()["access_token"], options={"verify_signature": False}
    )["sub"]

    login_resp = await client.post(
        "/auth/login", json={"identifier": f"{tag}+alias@gmail.com", "password": "hunter22"}
    )
    assert login_resp.status_code == 200
    logged_in_user_id = pyjwt.decode(
        login_resp.json()["access_token"], options={"verify_signature": False}
    )["sub"]
    assert logged_in_user_id == original_user_id


async def test_login_with_correct_password_succeeds(client):
    email = f"login-{uuid.uuid4()}@example.com"
    await client.post(
        "/auth/signup",
        json={"email": email, "phone_number": _fake_phone(), "password": "hunter22"},
    )
    resp = await client.post("/auth/login", json={"identifier": email, "password": "hunter22"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


async def test_login_with_wrong_password_fails(client):
    email = f"wrongpw-{uuid.uuid4()}@example.com"
    await client.post(
        "/auth/signup",
        json={"email": email, "phone_number": _fake_phone(), "password": "hunter22"},
    )
    resp = await client.post("/auth/login", json={"identifier": email, "password": "nope"})
    assert resp.status_code == 401


async def test_login_nonexistent_user_fails(client):
    resp = await client.post(
        "/auth/login", json={"identifier": "ghost@example.com", "password": "hunter22"}
    )
    assert resp.status_code == 401


async def test_me_requires_auth(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_returns_current_user(client):
    email = f"me-{uuid.uuid4()}@example.com"
    signup_resp = await client.post(
        "/auth/signup",
        json={"email": email, "phone_number": _fake_phone(), "password": "hunter22"},
    )
    token = signup_resp.json()["access_token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == email
    assert body["has_password"] is True


# ---------------------------------------------------------------------------
# Guest trial accounts (Phase 9)
# ---------------------------------------------------------------------------

async def test_create_guest_returns_valid_token(client):
    resp = await client.post("/auth/guest")
    assert resp.status_code == 201
    assert "access_token" in resp.json()


async def test_guest_me_has_is_guest_true_and_no_identifiers(client):
    guest_resp = await client.post("/auth/guest")
    token = guest_resp.json()["access_token"]
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_guest"] is True
    assert body["email"] is None
    assert body["phone_number"] is None
    assert body["has_password"] is False


async def test_each_guest_call_creates_a_distinct_account(client):
    first = (await client.post("/auth/guest")).json()["access_token"]
    second = (await client.post("/auth/guest")).json()["access_token"]
    first_me = await client.get("/auth/me", headers={"Authorization": f"Bearer {first}"})
    second_me = await client.get("/auth/me", headers={"Authorization": f"Bearer {second}"})
    assert first_me.json()["id"] != second_me.json()["id"]


# ---------------------------------------------------------------------------
# Password management: set (OAuth accounts) / change (existing password)
# ---------------------------------------------------------------------------

async def test_set_password_on_oauth_style_account(client, pg_test_engine):
    user = await _seed_oauth_style_user(pg_test_engine, email=f"oauth-{uuid.uuid4()}@example.com")
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}

    me_before = await client.get("/auth/me", headers=headers)
    assert me_before.json()["has_password"] is False

    resp = await client.put("/auth/me/set-password", json={"password": "newpass123"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["has_password"] is True

    # can now log in with the identifier + new password
    login_resp = await client.post(
        "/auth/login", json={"identifier": user.email, "password": "newpass123"}
    )
    assert login_resp.status_code == 200


async def test_set_password_fails_if_already_set(client):
    signup_resp = await client.post(
        "/auth/signup",
        json={
            "email": f"hasit-{uuid.uuid4()}@example.com",
            "phone_number": _fake_phone(),
            "password": "hunter22",
        },
    )
    headers = {"Authorization": f"Bearer {signup_resp.json()['access_token']}"}
    resp = await client.put("/auth/me/set-password", json={"password": "another123"}, headers=headers)
    assert resp.status_code == 409


async def test_change_password_succeeds_with_correct_current(client):
    email = f"change-{uuid.uuid4()}@example.com"
    signup_resp = await client.post(
        "/auth/signup",
        json={"email": email, "phone_number": _fake_phone(), "password": "hunter22"},
    )
    headers = {"Authorization": f"Bearer {signup_resp.json()['access_token']}"}

    resp = await client.put(
        "/auth/me/change-password",
        json={"current_password": "hunter22", "new_password": "newerpass456"},
        headers=headers,
    )
    assert resp.status_code == 204

    login_resp = await client.post(
        "/auth/login", json={"identifier": email, "password": "newerpass456"}
    )
    assert login_resp.status_code == 200


async def test_change_password_fails_with_wrong_current(client):
    signup_resp = await client.post(
        "/auth/signup",
        json={
            "email": f"wrongcur-{uuid.uuid4()}@example.com",
            "phone_number": _fake_phone(),
            "password": "hunter22",
        },
    )
    headers = {"Authorization": f"Bearer {signup_resp.json()['access_token']}"}

    resp = await client.put(
        "/auth/me/change-password",
        json={"current_password": "wrongpassword", "new_password": "newerpass456"},
        headers=headers,
    )
    assert resp.status_code == 401


async def test_reset_password_via_reauth_overwrites_forgotten_password(client):
    """Simulates the OAuth-recovery flow: user forgot their password, logs in via a linked
    OAuth identity instead (already-authenticated JWT), and resets the password without
    needing the old one."""
    email = f"forgot-{uuid.uuid4()}@example.com"
    signup_resp = await client.post(
        "/auth/signup",
        json={"email": email, "phone_number": _fake_phone(), "password": "originalpass"},
    )
    headers = {"Authorization": f"Bearer {signup_resp.json()['access_token']}"}

    resp = await client.put("/auth/me/reset-password", json={"password": "brandnewpass"}, headers=headers)
    assert resp.status_code == 200

    old_login = await client.post(
        "/auth/login", json={"identifier": email, "password": "originalpass"}
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/auth/login", json={"identifier": email, "password": "brandnewpass"}
    )
    assert new_login.status_code == 200


async def test_password_endpoints_require_auth(client):
    resp = await client.put("/auth/me/set-password", json={"password": "x"})
    assert resp.status_code == 401
    resp = await client.put("/auth/me/reset-password", json={"password": "x"})
    assert resp.status_code == 401
    resp = await client.put(
        "/auth/me/change-password", json={"current_password": "a", "new_password": "b"}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# BYOK
# ---------------------------------------------------------------------------

async def test_byok_store_list_delete_roundtrip(client):
    signup_resp = await client.post(
        "/auth/signup",
        json={
            "email": f"byok-{uuid.uuid4()}@example.com",
            "phone_number": _fake_phone(),
            "password": "hunter22",
        },
    )
    headers = {"Authorization": f"Bearer {signup_resp.json()['access_token']}"}

    put_resp = await client.put(
        "/auth/me/api-keys",
        json={"provider": "groq", "api_key": "gsk_supersecret", "model_name": "openai/gpt-oss-120b"},
        headers=headers,
    )
    assert put_resp.status_code == 200
    body = put_resp.json()
    assert body["provider"] == "groq"
    assert "api_key" not in body
    assert "encrypted_key" not in body

    list_resp = await client.get("/auth/me/api-keys", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    delete_resp = await client.delete("/auth/me/api-keys/groq", headers=headers)
    assert delete_resp.status_code == 204

    list_resp2 = await client.get("/auth/me/api-keys", headers=headers)
    assert list_resp2.json() == []


async def test_byok_update_overwrites_existing_key(client):
    signup_resp = await client.post(
        "/auth/signup",
        json={
            "email": f"byok2-{uuid.uuid4()}@example.com",
            "phone_number": _fake_phone(),
            "password": "hunter22",
        },
    )
    headers = {"Authorization": f"Bearer {signup_resp.json()['access_token']}"}

    await client.put(
        "/auth/me/api-keys", json={"provider": "groq", "api_key": "key-one"}, headers=headers
    )
    await client.put(
        "/auth/me/api-keys", json={"provider": "groq", "api_key": "key-two"}, headers=headers
    )

    list_resp = await client.get("/auth/me/api-keys", headers=headers)
    assert len(list_resp.json()) == 1  # updated in place, not duplicated


async def test_byok_requires_auth(client):
    resp = await client.get("/auth/me/api-keys")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# OAuth — account linking
# ---------------------------------------------------------------------------

async def test_oauth_callback_links_to_existing_email_account(client):
    """A GitHub/Google login whose verified email matches an existing password-auth
    account must link to that account, not fail on the unique-email constraint or
    silently create a duplicate user."""
    email = f"oauth-link-{uuid.uuid4()}@example.com"
    signup_resp = await client.post(
        "/auth/signup",
        json={"email": email, "phone_number": _fake_phone(), "password": "hunter22"},
    )
    existing_user_id = signup_resp.json()["access_token"]
    existing_user_id = pyjwt.decode(existing_user_id, options={"verify_signature": False})["sub"]

    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value="google")
    redis_mock.delete = AsyncMock()

    with (
        patch.object(settings, "google_client_id", "fake-client-id"),
        patch.object(settings, "google_client_secret", "fake-client-secret"),
        patch("api.routers.auth.get_redis", return_value=redis_mock),
        patch("httpx.AsyncClient", return_value=_mock_oauth_httpx(email)),
    ):
        resp = await client.get("/auth/google/callback?code=fake-code&state=fake-state")

    assert resp.status_code == 200
    token = resp.json()["access_token"]
    linked_user_id = pyjwt.decode(token, options={"verify_signature": False})["sub"]
    assert linked_user_id == existing_user_id


# ---------------------------------------------------------------------------
# Linking a second identifier (email + phone on one account)
# ---------------------------------------------------------------------------

async def test_link_phone_to_email_only_account(client, pg_test_engine):
    user = await _seed_oauth_style_user(pg_test_engine, email=f"linkphone-{uuid.uuid4()}@example.com")
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}
    phone = _fake_phone()

    resp = await client.put("/auth/me/link-phone", json={"phone_number": phone}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["phone_number"] == phone


async def test_link_email_to_phone_only_account(client, pg_test_engine):
    phone = _fake_phone()
    user = await _seed_oauth_style_user(pg_test_engine, phone=phone)
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}
    email = f"linkemail-{uuid.uuid4()}@example.com"

    resp = await client.put("/auth/me/link-email", json={"email": email}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == email


async def test_link_email_fails_if_already_linked(client, pg_test_engine):
    user = await _seed_oauth_style_user(
        pg_test_engine, email=f"already-{uuid.uuid4()}@example.com"
    )
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}

    resp = await client.put(
        "/auth/me/link-email",
        json={"email": f"other-{uuid.uuid4()}@example.com"},
        headers=headers,
    )
    assert resp.status_code == 409


async def test_link_email_fails_if_taken_by_another_account(client, pg_test_engine):
    taken_email = f"taken-{uuid.uuid4()}@example.com"
    await client.post(
        "/auth/signup",
        json={"email": taken_email, "phone_number": _fake_phone(), "password": "hunter22"},
    )

    user = await _seed_oauth_style_user(pg_test_engine, phone=_fake_phone())
    headers = {"Authorization": f"Bearer {create_access_token(user.id)}"}

    resp = await client.put("/auth/me/link-email", json={"email": taken_email}, headers=headers)
    assert resp.status_code == 409


async def test_link_endpoints_require_auth(client):
    resp = await client.put("/auth/me/link-email", json={"email": "x@example.com"})
    assert resp.status_code == 401
    resp = await client.put("/auth/me/link-phone", json={"phone_number": "+15551234567"})
    assert resp.status_code == 401
