"""User authentication helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from database.models import User


def hash_password(plain: str) -> str:
    return generate_password_hash(plain, method="pbkdf2:sha256")


def verify_password(plain: str, hashed: str) -> bool:
    return check_password_hash(hashed, plain)


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower()).first()


def create_user(
    db: Session,
    *,
    email: str,
    username: str,
    password: str,
    role: str,
    full_name: str | None = None,
) -> User:
    user = User(
        email=email.lower().strip(),
        username=username.strip(),
        password_hash=hash_password(password),
        role=role,
        full_name=(full_name or "").strip() or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username.strip())
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
