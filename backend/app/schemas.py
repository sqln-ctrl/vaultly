import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=120)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginIn(BaseModel):
    credential: str = Field(min_length=1, max_length=8192)


class VerifyIn(BaseModel):
    token: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=1, max_length=2048)
    password: str = Field(min_length=8, max_length=128)


class ResendVerificationIn(BaseModel):
    email: EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    email_verified: bool
    timezone: str
    currency: str


class AuthOut(BaseModel):
    access_token: str
    user: UserOut


class DocumentFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vendor: str | None = None
    doc_number: str | None = None
    issue_date: datetime | None = None
    due_date: datetime | None = None
    expiry_date: datetime | None = None
    total_amount: float | None = None
    tax_amount: float | None = None
    currency: str | None = None
    user_verified: bool = False


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    page_count: int | None
    category: str
    status: str
    error_message: str | None = None
    summary: str | None = None
    uploaded_at: datetime
    processed_at: datetime | None = None
    fields: DocumentFieldOut | None = None


class DocumentRenameIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)


class UsageOut(BaseModel):
    documents: int
    document_limit: int
    bytes: int
    byte_limit: int
