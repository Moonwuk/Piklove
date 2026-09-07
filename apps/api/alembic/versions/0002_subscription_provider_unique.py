"""Enforce one subscription per account and billing provider."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.create_unique_constraint(
            "uq_subscriptions_user_provider",
            ["user_id", "provider"],
        )


def downgrade():
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_constraint("uq_subscriptions_user_provider", type_="unique")
