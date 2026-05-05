"""recreate price_cache

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("price_cache")
    op.create_table(
        "price_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("price_date", sa.Date, nullable=False),
        sa.Column("close_price", sa.Float),
        sa.Column("volume", sa.BigInteger),
        sa.Column("change_pct", sa.Float),
        sa.Column("fetched_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("ticker", "price_date", name="uq_price_cache_ticker_date"),
    )


def downgrade() -> None:
    op.drop_table("price_cache")
    op.create_table(
        "price_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("price_date", sa.Date, nullable=False),
        sa.Column("close_price", sa.Float),
        sa.Column("volume", sa.BigInteger),
        sa.Column("change_pct", sa.Float),
        sa.Column("fetched_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("ticker", "price_date", name="uq_price_cache_ticker_date"),
    )
