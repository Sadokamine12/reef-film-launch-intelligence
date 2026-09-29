import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from reef.config import settings
from reef.db import session
from reef.models import LoginSession, UserAccount

COOKIE = "reef_session"


@dataclass
class User:
    email: str
    role: str


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return base64.b64encode(salt + key).decode()


def verify_password(password: str, encoded: str) -> bool:
    try:
        raw = base64.b64decode(encoded)
        return secrets.compare_digest(
            raw[16:], hashlib.scrypt(password.encode(), salt=raw[:16], n=16384, r=8, p=1)
        )
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(request: Request, db: Session = Depends(session)) -> User:
    if settings().dev_auth_bypass:
        return User("local-developer", "editor")
    token = request.cookies.get(COOKIE, "")
    stored = db.get(LoginSession, token_hash(token)) if token else None
    if not stored or stored.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(401, "Sign in to access REEF Launch Intelligence")
    account = db.get(UserAccount, stored.email)
    if not account or not account.active:
        raise HTTPException(401, "Account is unavailable")
    return User(account.email, account.role)


def editor(user: User = Depends(current_user)) -> User:
    if user.role != "editor":
        raise HTTPException(403, "Editor access required")
    return user
