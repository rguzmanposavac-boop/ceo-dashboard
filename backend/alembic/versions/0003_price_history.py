"""add price_history table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "price_history",
        sa.Column("id",         sa.Integer,     primary_key=True),
        sa.Column("stock_id",   sa.Integer,     sa.ForeignKey("stocks.id"), nullable=False),
        sa.Column("ticker",     sa.String(10),  nullable=False),
        sa.Column("date",       sa.DateTime,    nullable=False),
        sa.Column("open",       sa.Float),
        sa.Column("high",       sa.Float),
        sa.Column("low",        sa.Float),
        sa.Column("close",      sa.Float),
        sa.Column("volume",     sa.BigInteger),
        sa.Column("created_at", sa.DateTime,    server_default=sa.func.now()),
        sa.UniqueConstraint("stock_id", "date", name="uq_price_history_stock_date"),
    )
    op.create_index("ix_price_history_stock_id", "price_history", ["stock_id"])
    op.create_index("ix_price_history_ticker",   "price_history", ["ticker"])
    op.create_index(
        "ix_price_history_ticker_date",
        "price_history",
        ["ticker", "date"],
    )


def downgrade() -> None:
    op.drop_index("ix_price_history_ticker_date", table_name="price_history")
    op.drop_index("ix_price_history_ticker",      table_name="price_history")
    op.drop_index("ix_price_history_stock_id",    table_name="price_history")
    op.drop_table("price_history")
