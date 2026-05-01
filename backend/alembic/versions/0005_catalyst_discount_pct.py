"""add catalysts.discount_pct column

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "catalysts",
        sa.Column("discount_pct", sa.Float, nullable=True, server_default="0.0"),
    )
    # Seed realistic discount values for the 5 initial catalysts by type
    op.execute("""
        UPDATE catalysts SET discount_pct =
            CASE catalyst_type
                WHEN 'AI_INFRASTRUCTURE'    THEN 15.0
                WHEN 'TRADE_WAR_TARIFFS'    THEN 20.0
                WHEN 'BIOTECH_BREAKTHROUGH' THEN 10.0
                WHEN 'GOVERNMENT_CAPEX'     THEN 25.0
                WHEN 'GEOPOLITICAL_CONFLICT' THEN 18.0
                ELSE 0.0
            END
        WHERE discount_pct IS NULL OR discount_pct = 0
    """)


def downgrade() -> None:
    op.drop_column("catalysts", "discount_pct")
