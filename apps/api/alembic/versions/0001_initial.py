"""Initial privacy-first SaaS schema.

This revision is deliberately a static schema snapshot. Do not import ORM
metadata here: changing a model must produce a new Alembic revision instead of
silently changing the meaning of an already published migration.
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

user_status = sa.Enum("active", "blocked", "deleted", name="userstatus")
ai_mode = sa.Enum("off", "copilot", name="aimode")
conversation_status = sa.Enum("active", "archived", name="conversationstatus")
direction = sa.Enum("incoming", "outgoing", name="direction")
sender_type = sa.Enum("owner", "contact", name="sendertype")
send_status = sa.Enum("pending", "sent", "failed", "unknown", name="sendstatus")


def _id():
    return sa.Column("id", sa.String(length=36), primary_key=True)


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def upgrade():
    op.create_table(
        "users",
        _id(),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_username", sa.String(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("language_code", sa.String(), nullable=True),
        sa.Column("status", user_status, nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("telegram_user_id"),
    )
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"], unique=True)

    op.create_table(
        "telegram_business_connections",
        _id(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("telegram_business_connection_id", sa.String(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("can_reply", sa.Boolean(), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rights_json", sa.JSON(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("telegram_business_connection_id"),
    )
    op.create_index(
        "ix_telegram_business_connections_user_id",
        "telegram_business_connections",
        ["user_id"],
    )

    op.create_table(
        "conversations",
        _id(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("business_connection_id", sa.String(length=36), nullable=False),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_peer_user_id", sa.BigInteger(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("ai_mode", ai_mode, nullable=False),
        sa.Column("status", conversation_status, nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_version", sa.Integer(), nullable=False),
        sa.Column("summary_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_message_cursor", sa.BigInteger(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["business_connection_id"],
            ["telegram_business_connections.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "business_connection_id", "telegram_chat_id"),
    )
    op.create_index("ix_conversations_user_chat", "conversations", ["user_id", "telegram_chat_id"])
    op.create_index("ix_conversations_user_last", "conversations", ["user_id", "last_message_at"])

    op.create_table(
        "messages",
        _id(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("direction", direction, nullable=False),
        sa.Column("sender_type", sender_type, nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("telegram_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("conversation_id", "telegram_message_id"),
    )
    op.create_index(
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "telegram_created_at"],
    )

    op.create_table(
        "ai_generations",
        _id(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("source_last_message_id", sa.BigInteger(), nullable=False),
        sa.Column("analysis_json", sa.JSON(), nullable=False),
        sa.Column("suggestions_json", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ai_generations_user_id", "ai_generations", ["user_id"])

    op.create_table(
        "user_style_profiles",
        sa.Column("user_id", sa.String(length=36), primary_key=True),
        sa.Column("tone", sa.String(), nullable=False),
        sa.Column("humor_level", sa.Integer(), nullable=False),
        sa.Column("flirt_level", sa.Integer(), nullable=False),
        sa.Column("message_length", sa.String(), nullable=False),
        sa.Column("emoji_level", sa.String(), nullable=False),
        sa.Column("directness", sa.Integer(), nullable=False),
        sa.Column("custom_instructions", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "conversation_memories",
        _id(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "subscriptions",
        _id(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("plan", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("telegram_payment_charge_id", sa.String(), nullable=True),
        sa.Column("amount_stars", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("telegram_payment_charge_id"),
    )
    op.create_index("ix_subscription_user_status", "subscriptions", ["user_id", "status"])

    op.create_table(
        "usage_events",
        _id(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_usage_user_created", "usage_events", ["user_id", "created_at"])

    op.create_table(
        "processed_updates",
        sa.Column("update_id", sa.BigInteger(), primary_key=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "send_attempts",
        _id(),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("generation_id", sa.String(length=36), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=False),
        sa.Column("status", send_status, nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["generation_id"], ["ai_generations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "idempotency_key"),
    )


def downgrade():
    for table in (
        "send_attempts",
        "processed_updates",
        "usage_events",
        "subscriptions",
        "conversation_memories",
        "user_style_profiles",
        "ai_generations",
        "messages",
        "conversations",
        "telegram_business_connections",
        "users",
    ):
        op.drop_table(table)
    for enum_type in (
        send_status,
        sender_type,
        direction,
        conversation_status,
        ai_mode,
        user_status,
    ):
        enum_type.drop(op.get_bind(), checkfirst=True)
