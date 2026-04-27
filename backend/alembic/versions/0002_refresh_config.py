"""add refresh_config table and price_cache.fetched_at

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refresh_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "price_refresh_interval",
            sa.String(20),
            nullable=False,
            server_default="1hour",
        ),
        sa.Column(
            "score_refresh_interval",
            sa.String(20),
            nullable=False,
            server_default="1hour",
        ),
        sa.Column(
            "catalyst_auto_review",
            sa.Boolean,
            nullable=False,
            server_default="true",
        ),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.add_column(
        "price_cache",
        sa.Column("fetched_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("price_cache", "fetched_at")
    op.drop_table("refresh_config")
