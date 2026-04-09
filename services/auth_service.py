"""User authentication helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from config.settings import settings
from database.models import User

ALLOWED_ROLES = {"candidate", "admin"}


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
    role_normalized = (role or "").strip().lower()
    email_normalized = email.lower().strip()
    if role_normalized not in ALLOWED_ROLES:
        raise ValueError("Invalid role selected.")

    owner_email = (settings.ADMIN_EMAIL or "").strip().lower()
    if role_normalized == "admin" and email_normalized != owner_email:
        raise ValueError("Only configured admin email can have admin access.")
    if role_normalized != "admin":
        role_normalized = "candidate"

    user = User(
        email=email_normalized,
        username=username.strip(),
        password_hash=hash_password(password),
        role=role_normalized,
        full_name=(full_name or "").strip() or None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, username: str, password: str) -> User | None:
    login = username.strip()
    owner_email = (settings.ADMIN_EMAIL or "").strip().lower()
    login_normalized = login.lower()

    user = get_user_by_username(db, login)
    if not user and "@" in login:
        user = get_user_by_email(db, login)
    if not user or not user.is_active:
        return None
    if user.role == "admin" and owner_email and login_normalized != owner_email:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def enforce_admin_lock(db: Session) -> None:
    owner_email = (settings.ADMIN_EMAIL or "").strip().lower()
    owner_password = settings.ADMIN_PASSWORD or ""
    changed = False
    if not owner_email:
        # Without configured owner email, hard-lock all accounts to candidate.
        users = db.query(User).all()
        for u in users:
            if u.role != "candidate":
                u.role = "candidate"
                changed = True
        if changed:
            db.commit()
        return

    owner = db.query(User).filter(User.email == owner_email).first()
    if owner:
        if owner.role != "admin":
            owner.role = "admin"
            changed = True
        if owner_password and not verify_password(owner_password, owner.password_hash):
            owner.password_hash = hash_password(owner_password)
            changed = True
    elif owner_password:
        derived_username = owner_email.split("@", 1)[0]
        owner = User(
            email=owner_email,
            username=derived_username,
            password_hash=hash_password(owner_password),
            role="admin",
            full_name="Admin",
            is_active=True,
        )
        db.add(owner)
        changed = True

    others = db.query(User).filter(User.email != owner_email).all()
    for u in others:
        if u.role != "candidate":
            u.role = "candidate"
            changed = True

    if changed:
        db.commit()
