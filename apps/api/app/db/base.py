import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class UserStatus(enum.StrEnum):
    active = "active"
    blocked = "blocked"
    deleted = "deleted"


class AIMode(enum.StrEnum):
    off = "off"
    copilot = "copilot"


class ConversationStatus(enum.StrEnum):
    active = "active"
    archived = "archived"


class Direction(enum.StrEnum):
    incoming = "incoming"
    outgoing = "outgoing"


class SenderType(enum.StrEnum):
    owner = "owner"
    contact = "contact"


class SendStatus(enum.StrEnum):
    pending = "pending"
    sent = "sent"
    failed = "failed"
    unknown = "unknown"


class UUIDMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String)
    first_name: Mapped[str | None] = mapped_column(String)
    language_code: Mapped[str | None] = mapped_column(String)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.active)


class BusinessConnection(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "telegram_business_connections"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    telegram_business_connection_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    can_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rights_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Conversation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("user_id", "business_connection_id", "telegram_chat_id"),
        Index("ix_conversations_user_last", "user_id", "last_message_at"),
        Index("ix_conversations_user_chat", "user_id", "telegram_chat_id"),
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    business_connection_id: Mapped[str] = mapped_column(
        ForeignKey("telegram_business_connections.id", ondelete="CASCADE")
    )
    telegram_chat_id: Mapped[int] = mapped_column(BigInteger)
    telegram_peer_user_id: Mapped[int | None] = mapped_column(BigInteger)
    display_name: Mapped[str | None] = mapped_column(String)
    username: Mapped[str | None] = mapped_column(String)
    ai_mode: Mapped[AIMode] = mapped_column(Enum(AIMode), default=AIMode.off)
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus), default=ConversationStatus.active
    )
    summary: Mapped[str | None] = mapped_column(Text)
    summary_version: Mapped[int] = mapped_column(Integer, default=0)
    summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary_message_cursor: Mapped[int | None] = mapped_column(BigInteger)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base, UUIDMixin):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "telegram_message_id"),
        Index("ix_messages_conversation_created", "conversation_id", "telegram_created_at"),
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    telegram_message_id: Mapped[int] = mapped_column(BigInteger)
    direction: Mapped[Direction] = mapped_column(Enum(Direction))
    sender_type: Mapped[SenderType] = mapped_column(Enum(SenderType))
    text: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String, default="text")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    telegram_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Generation(Base, UUIDMixin):
    __tablename__ = "ai_generations"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    source_last_message_id: Mapped[int] = mapped_column(BigInteger)
    analysis_json: Mapped[dict] = mapped_column(JSON)
    suggestions_json: Mapped[dict] = mapped_column(JSON)
    provider: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SendAttempt(Base, UUIDMixin):
    __tablename__ = "send_attempts"
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    generation_id: Mapped[str] = mapped_column(ForeignKey("ai_generations.id", ondelete="CASCADE"))
    idempotency_key: Mapped[str] = mapped_column(String)
    status: Mapped[SendStatus] = mapped_column(Enum(SendStatus))
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class StyleProfile(Base):
    __tablename__ = "user_style_profiles"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tone: Mapped[str] = mapped_column(String, default="natural")
    humor_level: Mapped[int] = mapped_column(Integer, default=5)
    flirt_level: Mapped[int] = mapped_column(Integer, default=3)
    message_length: Mapped[str] = mapped_column(String, default="short")
    emoji_level: Mapped[str] = mapped_column(String, default="low")
    directness: Mapped[int] = mapped_column(Integer, default=5)
    custom_instructions: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class Memory(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "conversation_memories"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(Text)


class Subscription(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "subscriptions"
    __table_args__ = (Index("ix_subscription_user_status", "user_id", "status"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String, default="telegram_stars")
    plan: Mapped[str] = mapped_column(String, default="free")
    status: Mapped[str] = mapped_column(String, default="active")
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    telegram_payment_charge_id: Mapped[str | None] = mapped_column(String, unique=True)
    amount_stars: Mapped[int | None] = mapped_column(Integer)


class UsageEvent(Base, UUIDMixin):
    __tablename__ = "usage_events"
    __table_args__ = (Index("ix_usage_user_created", "user_id", "created_at"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    event_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ProcessedUpdate(Base):
    __tablename__ = "processed_updates"
    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_type: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
