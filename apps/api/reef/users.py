"""Invite a user: python -m reef.users EMAIL --role editor (password entered securely)."""

import argparse
import getpass
import os

from sqlalchemy.orm import Session

from reef.auth import password_hash
from reef.db import engine
from reef.models import UserAccount


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("--role", choices=["editor", "viewer"], default="viewer")
    args = parser.parse_args()
    password = os.environ.get("REEF_USER_PASSWORD") or getpass.getpass("Password (at least 12 characters): ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")
    with Session(engine()) as db:
        email = args.email.strip().lower()
        if db.get(UserAccount, email):
            raise SystemExit("Account already exists. Use the documented reset procedure.")
        db.add(UserAccount(email=email, role=args.role, password_hash=password_hash(password), active=True))
        db.commit()
    print("Invited account created.")


if __name__ == "__main__":
    main()
