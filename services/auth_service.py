"""User authentication helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session
from werkzeug.security import check_password_hash, generate_password_hash

from config.settings import settings
from database.models import User

ALLOWED_ROLES = {"recruiter", "candidate", "admin"}


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

    # Admin account is locked to the configured owner email only.
    if role_normalized == "admin":
        owner_email = (settings.ADMIN_EMAIL or "").strip().lower()
        if owner_email:
            if email_normalized != owner_email:
                raise ValueError("Only the configured owner email can be admin.")
            existing_admin = db.query(User).filter(User.role == "admin", User.email != owner_email).first()
            if existing_admin:
                raise ValueError("Admin role is locked and cannot be assigned to additional users.")
        else:
            existing_admin = db.query(User).filter(User.role == "admin").first()
            if existing_admin:
                raise ValueError("Only one admin account is allowed.")

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
    user = get_user_by_username(db, username.strip())
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def enforce_admin_lock(db: Session) -> None:
    owner_email = (settings.ADMIN_EMAIL or "").strip().lower()
    changed = False
    if owner_email:
        owner = db.query(User).filter(User.email == owner_email).first()
        if owner and owner.role != "admin":
            owner.role = "admin"
            changed = True

        non_owner_admins = db.query(User).filter(User.role == "admin", User.email != owner_email).all()
        for u in non_owner_admins:
            u.role = "recruiter"
            changed = True
    else:
        admins = db.query(User).filter(User.role == "admin").order_by(User.id.asc()).all()
        for extra_admin in admins[1:]:
            extra_admin.role = "recruiter"
            changed = True

    if changed:
        db.commit()
