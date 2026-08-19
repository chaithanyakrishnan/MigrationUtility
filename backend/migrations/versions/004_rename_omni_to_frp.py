"""Rename Omni → FRP across the KB schema.

Renames the two Omni-specific tables and their indexes, and migrates the
knowledge_bases.kind discriminator value from 'omni' to 'frp'. Existing rows
(records, fields, the built Omni KB, transaction cards) are preserved — this is
a pure rename, no data is dropped.

Revision ID: 004
Revises: 003
"""
from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tables
    op.rename_table("kb_omni_records", "kb_frp_records")
    op.rename_table("kb_omni_fields", "kb_frp_fields")
    # Indexes (Postgres keeps the old names after a table rename)
    op.execute("ALTER INDEX IF EXISTS ix_kb_omni_record_kb RENAME TO ix_kb_frp_record_kb")
    op.execute("ALTER INDEX IF EXISTS ix_kb_omni_field_record RENAME TO ix_kb_frp_field_record")
    # Discriminator value on the single Omni KB row
    op.execute("UPDATE knowledge_bases SET kind = 'frp' WHERE kind = 'omni'")


def downgrade() -> None:
    op.execute("UPDATE knowledge_bases SET kind = 'omni' WHERE kind = 'frp'")
    op.execute("ALTER INDEX IF EXISTS ix_kb_frp_field_record RENAME TO ix_kb_omni_field_record")
    op.execute("ALTER INDEX IF EXISTS ix_kb_frp_record_kb RENAME TO ix_kb_omni_record_kb")
    op.rename_table("kb_frp_fields", "kb_omni_fields")
    op.rename_table("kb_frp_records", "kb_omni_records")
