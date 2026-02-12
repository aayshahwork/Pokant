"""add customer api_token_hash and last_active_at

Revision ID: 001
Revises:
Create Date: 2026-02-10

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create pgvector extension if not exists (for fresh DBs that use init_db after)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Add columns to customers if table exists (idempotent for add_column: run only if missing)
    conn = op.get_bind()
    from sqlalchemy import inspect
    insp = inspect(conn)
    if "customers" in insp.get_table_names():
        cols = [c["name"] for c in insp.get_columns("customers")]
        if "api_token_hash" not in cols:
            op.add_column("customers", sa.Column("api_token_hash", sa.String(64), unique=True, nullable=True))
        if "last_active_at" not in cols:
            op.add_column("customers", sa.Column("last_active_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    from sqlalchemy import inspect
    conn = op.get_bind()
    insp = inspect(conn)
    if "customers" not in insp.get_table_names():
        return
    cols = [c["name"] for c in insp.get_columns("customers")]
    if "last_active_at" in cols:
        op.drop_column("customers", "last_active_at")
    if "api_token_hash" in cols:
        op.drop_column("customers", "api_token_hash")
