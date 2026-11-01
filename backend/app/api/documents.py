import hashlib
import logging
import mimetypes
import os
import re
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Document, DocumentField, User, VaultChatConversation, VaultChatMessage
from ..schemas import (
    ChatConversationIn,
    ChatConversationOut,
    ChatMessageIn,
    ChatMessageOut,
    DocumentOut,
    DocumentRenameIn,
    UsageOut,
)
from ..security import create_token, decode_token
from ..processing import answer_vault_question, process_document
from .deps import verified_user

router = APIRouter(prefix="/documents", tags=["documents"])
MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_DOCUMENTS = 50
MAX_STORAGE_BYTES = 200 * 1024 * 1024
MAX_PAGES = 20
logger = logging.getLogger(__name__)


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


def _parse_date(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _delete_expired_chat_messages(db: Session, user: User) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=15)
    db.execute(
        delete(VaultChatMessage).where(
            VaultChatMessage.user_id == user.id,
            VaultChatMessage.created_at < cutoff,
        )
    )
    expired_conversations = db.scalars(
        select(VaultChatConversation.id).where(
            VaultChatConversation.user_id == user.id,
            VaultChatConversation.updated_at < cutoff,
        )
    ).all()
    if expired_conversations:
        db.execute(delete(VaultChatConversation).where(
            VaultChatConversation.id.in_(expired_conversations)
        ))
    db.commit()


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
                with fitz.open(stream=destination.read_bytes(), filetype="pdf") as pdf:
                    page_count = pdf.page_count
                if page_count > MAX_PAGES:
                    destination.unlink(missing_ok=True)
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "PDF exceeds the 20-page processing limit")
            except HTTPException:
                raise
            except Exception as exc:
                destination.unlink(missing_ok=True)
                logger.warning("PDF validation failed for uploaded file: %s", exc, exc_info=True)
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

        result = process_document(destination, mime_type, file.filename)
        fields_data = result["fields"]
        document = Document(
            user_id=user.id,
            original_filename=_safe_filename(file.filename),
            storage_key=storage_key,
            mime_type=mime_type,
            size_bytes=size,
            sha256=sha256.hexdigest(),
            page_count=page_count,
            category=result["category"],
            status="ready",
            summary=result["summary"],
            extracted_text=result["text"],
            processed_at=datetime.now(timezone.utc),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        document.fields = DocumentField(
            document_id=document.id,
            vendor=fields_data.get("vendor"),
            doc_number=fields_data.get("doc_number"),
            issue_date=_parse_date(fields_data.get("issue_date")),
            due_date=_parse_date(fields_data.get("due_date")),
            total_amount=fields_data.get("total_amount"),
            currency=fields_data.get("currency"),
        )
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


@router.get("/chat", response_model=list[ChatMessageOut])
def get_vault_chat(
    conversation_id: uuid.UUID | None = None,
    user: User = Depends(verified_user),
    db: Session = Depends(get_db),
):
    _delete_expired_chat_messages(db, user)
    statement = (
        select(VaultChatMessage)
        .where(VaultChatMessage.user_id == user.id)
        .order_by(VaultChatMessage.created_at.asc())
    )
    if conversation_id:
        statement = statement.where(VaultChatMessage.conversation_id == conversation_id)
    return db.scalars(statement).all()


@router.get("/chats", response_model=list[ChatConversationOut])
def list_vault_chats(user: User = Depends(verified_user), db: Session = Depends(get_db)):
    _delete_expired_chat_messages(db, user)
    return db.scalars(
        select(VaultChatConversation)
        .where(VaultChatConversation.user_id == user.id)
        .order_by(VaultChatConversation.updated_at.desc())
    ).all()


@router.post("/chats", response_model=ChatConversationOut, status_code=status.HTTP_201_CREATED)
def create_vault_chat(
    body: ChatConversationIn,
    user: User = Depends(verified_user),
    db: Session = Depends(get_db),
):
    _delete_expired_chat_messages(db, user)
    conversation = VaultChatConversation(user_id=user.id, title=body.title.strip() or "New chat")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/chats/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vault_chat(
    conversation_id: uuid.UUID,
    user: User = Depends(verified_user),
    db: Session = Depends(get_db),
):
    conversation = db.scalar(select(VaultChatConversation).where(
        VaultChatConversation.id == conversation_id,
        VaultChatConversation.user_id == user.id,
    ))
    if not conversation:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat not found")
    db.execute(delete(VaultChatMessage).where(
        VaultChatMessage.conversation_id == conversation_id,
        VaultChatMessage.user_id == user.id,
    ))
    db.delete(conversation)
    db.commit()


@router.post("/chat", response_model=ChatMessageOut)
def send_vault_chat(
    body: ChatMessageIn,
    user: User = Depends(verified_user),
    db: Session = Depends(get_db),
):
    _delete_expired_chat_messages(db, user)
    conversation: VaultChatConversation | None = None
    if body.conversation_id:
        conversation = db.scalar(select(VaultChatConversation).where(
            VaultChatConversation.id == body.conversation_id,
            VaultChatConversation.user_id == user.id,
        ))
    if not conversation:
        conversation = VaultChatConversation(user_id=user.id, title="New chat")
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    message = body.message.strip()
    question = VaultChatMessage(
        user_id=user.id,
        conversation_id=conversation.id,
        role="user",
        content=message,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    if conversation.title == "New chat":
        conversation.title = message[:60] + ("..." if len(message) > 60 else "")

    history_rows = db.scalars(
        select(VaultChatMessage)
        .where(VaultChatMessage.user_id == user.id)
        .where(VaultChatMessage.conversation_id == conversation.id)
        .order_by(VaultChatMessage.created_at.asc())
    ).all()
    history = [{"role": row.role, "content": row.content} for row in history_rows if row.role in ("user", "assistant")]

    documents = db.scalars(
        select(Document).where(Document.user_id == user.id).order_by(Document.uploaded_at.desc())
    ).all()
    context = [
        {
            "name": document.original_filename,
            "text": document.extracted_text or document.summary or "",
            "summary": document.summary or "",
        }
        for document in documents
    ]
    answer_text = answer_vault_question(context, body.message.strip(), history[:-1])
    answer = VaultChatMessage(
        user_id=user.id,
        conversation_id=conversation.id,
        role="assistant",
        content=answer_text,
    )
    db.add(answer)
    conversation.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(answer)
    return {
        "id": answer.id,
        "role": answer.role,
        "content": answer.content,
        "created_at": answer.created_at,
        "conversation_id": conversation.id,
    }


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
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
        },
    )
