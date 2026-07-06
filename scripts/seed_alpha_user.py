"""One-shot: create (or promote) the alpha-tester account.

Usage:
    python scripts/seed_alpha_user.py <email> <password>

Uses the app's default LLM key (no BYOK entry created) — matches the alpha-tester/demo
path in services/llm_service.py::resolve_llm_service (falls back to the app default
whenever a session has no llm_provider set).
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from db.postgres import AsyncSessionFactory
from models.pg.user import User
from services.auth_service import create_access_token, hash_password


async def main(email: str, password: str) -> None:
    async with AsyncSessionFactory() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            user.password_hash = hash_password(password)
            user.is_alpha_tester = True
            await db.commit()
            print(f"Promoted existing user {email} to alpha tester.")
        else:
            user = User(email=email, password_hash=hash_password(password), is_alpha_tester=True)
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"Created alpha-tester user {email}.")

        token = create_access_token(user.id)
        print(f"user_id: {user.id}")
        print(f"access_token: {token}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/seed_alpha_user.py <email> <password>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
