import os
import mimetypes
import uuid
from datetime import datetime, timedelta, timezone
from werkzeug.utils import secure_filename

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
ARCHIVE_EXT = {".zip", ".rar", ".7z", ".tar", ".gz"}
DOC_EXT = {
    ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
    ".pdf", ".txt", ".md", ".rtf"
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def ext_of(name: str) -> str:
    return os.path.splitext(name)[1].lower()

def detect_mime(filename: str) -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or "application/octet-stream"

def classify_by_ext(ext: str) -> str:
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    if ext in ARCHIVE_EXT:
        return "archive"
    if ext in DOC_EXT:
        return "doc"
    return "other"

def gen_stored_name(orig_filename: str) -> str:
    ext = ext_of(orig_filename)
    return f"{uuid.uuid4().hex}{ext}"

def compute_expires(days: int | None):
    if days is None:
        return None  # 永久
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

def normalise_expiry_choice(choice: str):
    """
    choice in: '1','3','7','15','30','forever'
    """
    if choice == "forever":
        return (1, None)
    days = int(choice)
    return (0, compute_expires(days))

def safe_name(name: str) -> str:
    # secure_filename 會處理奇怪字元；中文也可能被替換，你也可自行改策略
    s = secure_filename(name)
    return s or "file"