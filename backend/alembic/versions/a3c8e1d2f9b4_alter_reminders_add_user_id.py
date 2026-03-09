"""alter_reminders_add_user_id

Revision ID: a3c8e1d2f9b4
Revises:
Create Date: 2026-03-09

Add user_id (non-nullable, indexed) to the reminders table so that every
reminder is owned by a specific authenticated user.  No production data exists
yet, so we go straight to NOT NULL with no default — per Auth team sign-off.

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c8e1d2f9b4"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reminders",
        sa.Column("user_id", sa.Integer(), nullable=False),
    )
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_reminders_user_id", table_name="reminders")
    op.drop_column("reminders", "user_id")
