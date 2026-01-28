#!/usr/bin/env python3
import argparse
import asyncio
from getpass import getpass
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from backend.auth import hash_password
from backend.db import async_session_maker
from backend.models import User


async def create_user(username: str, password: str) -> None:
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.username == username))
        existing = result.scalar_one_or_none()
        if existing:
            raise RuntimeError(f"User '{username}' already exists")

        user = User(username=username, hashed_password=hash_password(password))
        session.add(user)
        await session.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new user in the database.")
    parser.add_argument("username")
    parser.add_argument("--password", help="Password (will prompt if omitted)")
    args = parser.parse_args()

    password = args.password or getpass("Password: ")
    asyncio.run(create_user(args.username, password))
    print("User created.")


if __name__ == "__main__":
    main()
