"""Add max_power_data table for client mode

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2026-03-01 01:00:00

Creates max_power_data table for storing daily maximum power (Pmax / DCMP in VA).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("""
            CREATE TABLE IF NOT EXISTS max_power_data (
                id VARCHAR(36) PRIMARY KEY,
                usage_point_id VARCHAR(14) NOT NULL,
                date DATE NOT NULL,
                value INTEGER NOT NULL,
                event_time VARCHAR(25),
                source VARCHAR(50) DEFAULT 'myelectricaldata',
                raw_data JSONB,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                CONSTRAINT uq_max_power_data UNIQUE (usage_point_id, date)
            )
        """)
        op.execute("CREATE INDEX IF NOT EXISTS ix_max_power_usage_point_date ON max_power_data(usage_point_id, date)")
    else:
        op.create_table(
            "max_power_data",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("usage_point_id", sa.String(14), nullable=False, index=True),
            sa.Column("date", sa.Date(), nullable=False, index=True),
            sa.Column("value", sa.Integer(), nullable=False),
            sa.Column("event_time", sa.String(25), nullable=True),
            sa.Column("source", sa.String(50), default="myelectricaldata"),
            sa.Column("raw_data", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.UniqueConstraint("usage_point_id", "date", name="uq_max_power_data"),
        )
        op.create_index("ix_max_power_usage_point_date", "max_power_data", ["usage_point_id", "date"])


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute("DROP TABLE IF EXISTS max_power_data CASCADE")
    else:
        op.drop_table("max_power_data")
