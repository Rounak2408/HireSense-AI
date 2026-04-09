"""Secure-ish file storage under uploads/."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from config.settings import settings


def safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^a-zA-Z0-9._\-]", "_", base)
    return base[:200] or "file"


def store_upload(user_id: int, data: bytes, original_name: str) -> str:
    uid = str(uuid.uuid4())[:8]
    folder = settings.UPLOAD_DIR / str(user_id)
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"{uid}_{safe_filename(original_name)}"
    path = folder / fname
    path.write_bytes(data)
    rel = Path("uploads") / str(user_id) / fname
    return rel.as_posix()
