import hashlib
import mimetypes
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Document, DocumentField, User
from ..schemas import DocumentOut, DocumentRenameIn, UsageOut
from ..security import create_token, decode_token
from .deps import verified_user

router = APIRouter(prefix="/documents", tags=["documents"])
MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_DOCUMENTS = 50
MAX_STORAGE_BYTES = 200 * 1024 * 1024
MAX_PAGES = 20


def _storage_root() -> Path:
    root = Path(settings.storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name).strip(". ")
    return name[:255] or "document"


def _detect_type(header: bytes) -> tuple[str, str] | None:
    if header.startswith(b"%PDF"):
        return "application/pdf", ".pdf"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def _owned_document(db: Session, document_id: uuid.UUID, user: User) -> Document:
    document = db.scalar(select(Document).where(Document.id == document_id, Document.user_id == user.id))
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


def _usage(db: Session, user: User) -> tuple[int, int]:
    count = db.scalar(select(func.count(Document.id)).where(Document.user_id == user.id)) or 0
    size = db.scalar(select(func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.user_id == user.id)) or 0
    return int(count), int(size)


@router.get("/usage", response_model=UsageOut)
def usage(user: User = Depends(verified_user), db: Session = Depends(get_db)):
    count, size = _usage(db, user)
    return UsageOut(documents=count, document_limit=MAX_DOCUMENTS, bytes=size, byte_limit=MAX_STORAGE_BYTES)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    user: User = Depends(verified_user),
    db: Session = Depends(get_db),
):
    count, current_size = _usage(db, user)
    if count >= MAX_DOCUMENTS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Document limit reached")
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Filename is required")

    header = await file.read(16)
    detected = _detect_type(header)
    await file.seek(0)
    if not detected:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported or invalid file type")
    mime_type, extension = detected

    storage_key = f"{user.id}/{uuid.uuid4()}{extension}"
    destination = _storage_root() / storage_key
    destination.parent.mkdir(parents=True, exist_ok=True)
    sha256 = hashlib.sha256()
    size = 0
    page_count: int | None = None
    try:
        with destination.open("xb") as target:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_FILE_BYTES:
                    raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "File exceeds the 15 MB limit")
                if current_size + size > MAX_STORAGE_BYTES:
                    raise HTTPException(status.HTTP_403_FORBIDDEN, "Storage limit reached")
                sha256.update(chunk)
                target.write(chunk)
        os.chmod(destination, 0o600)

        duplicate = db.scalar(select(Document).where(Document.user_id == user.id, Document.sha256 == sha256.hexdigest()))
        if duplicate:
            destination.unlink(missing_ok=True)
            raise HTTPException(status.HTTP_409_CONFLICT, "This file is already in your vault")

        if mime_type == "application/pdf":
            try:
                import fitz
                with fitz.open(destination) as pdf:
                    page_count = pdf.page_count
                if page_count > MAX_PAGES:
                    destination.unlink(missing_ok=True)
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "PDF exceeds the 20-page processing limit")
            except HTTPException:
                raise
            except Exception:
                destination.unlink(missing_ok=True)
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "PDF could not be validated")
        else:
            try:
                from PIL import Image
                with Image.open(destination) as image:
                    image.verify()
                page_count = 1
            except Exception:
                destination.unlink(missing_ok=True)
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image could not be validated")

        document = Document(
            user_id=user.id,
            original_filename=_safe_filename(file.filename),
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=size,
            sha256=sha256.hexdigest(),
            page_count=page_count,
            category="Other",
            status="ready",
            fields=None,
            processed_at=datetime.now(timezone.utc),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        destination.unlink(missing_ok=True)
        raise


@router.get("", response_model=list[DocumentOut])
def list_documents(
    q: str | None = None,
    category: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(verified_user),
    db: Session = Depends(get_db),
):
    statement = select(Document).where(Document.user_id == user.id)
    if category:
        statement = statement.where(Document.category == category)
    if q:
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(Document.original_filename.ilike(f"%{escaped}%", escape="\\"))
    return db.scalars(statement.order_by(Document.uploaded_at.desc()).offset(offset).limit(limit)).all()


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, user: User = Depends(verified_user), db: Session = Depends(get_db)):
    return _owned_document(db, document_id, user)


@router.patch("/{document_id}", response_model=DocumentOut)
def rename_document(
    document_id: uuid.UUID,
    body: DocumentRenameIn,
    user: User = Depends(verified_user),
    db: Session = Depends(get_db),
):
    document = _owned_document(db, document_id, user)
    document.original_filename = _safe_filename(body.filename)
    db.commit()
    db.refresh(document)
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: uuid.UUID, user: User = Depends(verified_user), db: Session = Depends(get_db)):
    document = _owned_document(db, document_id, user)
    db.delete(document)
    db.commit()
    path = _storage_root() / document.storage_key
    if path.is_file():
        path.unlink()


@router.get("/{document_id}/download")
def get_download_url(document_id: uuid.UUID, user: User = Depends(verified_user), db: Session = Depends(get_db)):
    document = _owned_document(db, document_id, user)
    token = create_token(f"{user.id}:{document.id}", "download", 5)
    return {"url": f"/api/v1/documents/{document.id}/file?token={token}"}


@router.get("/{document_id}/file")
def download_file(
    document_id: uuid.UUID,
    token: str,
    db: Session = Depends(get_db),
):
    subject = decode_token(token, "download")
    if not subject or ":" not in subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Download link is invalid or expired")
    user_id, token_document_id = subject.split(":", 1)
    if str(document_id) != token_document_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid document download")
    try:
        owner_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Download link is invalid or expired")
    document = db.scalar(select(Document).where(Document.id == document_id, Document.user_id == owner_id))
    if not document:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    path = (_storage_root() / document.storage_key).resolve()
    try:
        path.relative_to(_storage_root())
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stored file not found")
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stored file not found")
    return FileResponse(
        path,
        media_type=document.mime_type,
        filename=document.original_filename,
        headers={"Cache-Control": "private, no-store"},
    )
