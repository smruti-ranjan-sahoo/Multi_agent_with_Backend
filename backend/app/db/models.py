import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


# ── User ──────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id            : Mapped[str]      = mapped_column(String, primary_key=True, default=generate_uuid)
    email         : Mapped[str]      = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str]     = mapped_column(String, nullable=False)
    full_name     : Mapped[str]      = mapped_column(String, nullable=True)
    is_active     : Mapped[bool]     = mapped_column(Boolean, default=True)
    created_at    : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversations : Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )


# ── Conversation ──────────────────────────────────
class Conversation(Base):
    __tablename__ = "conversations"

    id         : Mapped[str]      = mapped_column(String, primary_key=True, default=generate_uuid)
    user_id    : Mapped[str]      = mapped_column(String, ForeignKey("users.id"), nullable=False)
    title      : Mapped[str]      = mapped_column(String(255), default="New Conversation")
    provider   : Mapped[str]      = mapped_column(String(50), default="groq")
    model      : Mapped[str]      = mapped_column(String(100), default="llama-3.3-70b-versatile")
    created_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages   : Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
    user       : Mapped["User"] = relationship("User", back_populates="conversations")

    uploaded_files: Mapped[list["UploadedFile"]] = relationship(
        "UploadedFile", back_populates="conversation", cascade="all, delete-orphan"
    )


# ── Message ───────────────────────────────────────
class Message(Base):
    __tablename__ = "messages"

    id             : Mapped[str]      = mapped_column(String, primary_key=True, default=generate_uuid)
    conversation_id: Mapped[str]      = mapped_column(String, ForeignKey("conversations.id"), nullable=False)
    role           : Mapped[str]      = mapped_column(String(20), nullable=False)  # user / assistant / system
    content        : Mapped[str]      = mapped_column(Text, nullable=False)
    token_count    : Mapped[int]      = mapped_column(Integer, default=0)
    created_at     : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation   : Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


# ── Uploaded File ─────────────────────────────────
class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id             : Mapped[str]      = mapped_column(String, primary_key=True, default=generate_uuid)
    conversation_id: Mapped[str]      = mapped_column(String, ForeignKey("conversations.id"), nullable=False)
    file_name      : Mapped[str]      = mapped_column(String, nullable=False)
    file_type      : Mapped[str]      = mapped_column(String, nullable=False)  # pdf | csv | image
    cloudinary_url : Mapped[str]      = mapped_column(String, nullable=True)
    created_at     : Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation   : Mapped["Conversation"] = relationship("Conversation", back_populates="uploaded_files")