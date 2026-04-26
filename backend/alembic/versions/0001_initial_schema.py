"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "regime_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("detected_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("regime", sa.String(20), nullable=False),
        sa.Column("vix", sa.Float),
        sa.Column("spy_3m_return", sa.Float),
        sa.Column("yield_curve_spread", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("favored_sectors", ARRAY(sa.String)),
        sa.Column("avoided_sectors", ARRAY(sa.String)),
    )

    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.String(10), nullable=False, unique=True),
        sa.Column("company", sa.String(150), nullable=False),
        sa.Column("sector", sa.String(80), nullable=False),
        sa.Column("sub_sector", sa.String(80)),
        sa.Column("market_cap_category", sa.String(20)),
        sa.Column("exchange", sa.String(10)),
        sa.Column("universe_level", sa.Integer, server_default="1"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
    )

    op.create_table(
        "ceos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("stock_id", sa.Integer, sa.ForeignKey("stocks.id")),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("profile", sa.String(50)),
        sa.Column("tenure_years", sa.Float),
        sa.Column("ownership_pct", sa.Float),
        sa.Column("succession_quality", sa.String(20)),
        sa.Column("is_founder", sa.Boolean, server_default="false"),
        sa.Column("notes", sa.Text),
    )

    op.create_table(
        "catalysts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("catalyst_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("affected_sectors", ARRAY(sa.String)),
        sa.Column("affected_tickers", ARRAY(sa.String)),
        sa.Column("intensity_score", sa.Float),
        sa.Column("expected_window", sa.String(20)),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("detected_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "score_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("scored_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("regime", sa.String(20)),
        sa.Column("regime_score", sa.Float),
        sa.Column("sector_score", sa.Float),
        sa.Column("base_score", sa.Float),
        sa.Column("ceo_score", sa.Float),
        sa.Column("roic_wacc_score", sa.Float),
        sa.Column("core_total", sa.Float),
        sa.Column("catalyst_intensity", sa.Float),
        sa.Column("catalyst_discount", sa.Float),
        sa.Column("catalyst_sensitivity", sa.Float),
        sa.Column("catalyst_window_score", sa.Float),
        sa.Column("catalyst_coverage", sa.Float),
        sa.Column("catalyst_total", sa.Float),
        sa.Column("catalyst_id", sa.Integer, sa.ForeignKey("catalysts.id")),
        sa.Column("final_score", sa.Float),
        sa.Column("signal", sa.String(20)),
        sa.Column("horizon", sa.String(20)),
        sa.Column("expected_return_low", sa.Float),
        sa.Column("expected_return_high", sa.Float),
        sa.Column("probability", sa.Float),
        sa.Column("invalidators", JSONB),
    )

    op.create_table(
        "price_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("price_date", sa.Date, nullable=False),
        sa.Column("close_price", sa.Float),
        sa.Column("volume", sa.BigInteger),
        sa.Column("change_pct", sa.Float),
        sa.UniqueConstraint("ticker", "price_date", name="uq_price_cache_ticker_date"),
    )


def downgrade() -> None:
    op.drop_table("price_cache")
    op.drop_table("score_snapshots")
    op.drop_table("catalysts")
    op.drop_table("ceos")
    op.drop_table("stocks")
    op.drop_table("regime_history")
