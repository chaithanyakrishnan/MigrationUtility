"""Persistent cross-engagement schema understanding library

Revision ID: 002
Revises: 001
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Where an engagement's schema came from: a real upload or the library.
    op.add_column(
        "schema_files",
        sa.Column("origin", sa.String(50), nullable=False, server_default="upload"),
    )

    # ── Canonical schema understanding (one per product+version) ──
    op.create_table(
        "schema_knowledge",
        sa.Column("id",                sa.String(),    nullable=False),
        sa.Column("product",           sa.String(50),  nullable=False),
        sa.Column("version",           sa.String(50),  nullable=False, server_default="unspecified"),
        sa.Column("table_count",       sa.Integer(),   nullable=False, server_default="0"),
        sa.Column("field_count",       sa.Integer(),   nullable=False, server_default="0"),
        sa.Column("domain_count",      sa.Integer(),   nullable=False, server_default="0"),
        sa.Column("contributor_count", sa.Integer(),   nullable=False, server_default="0"),
        sa.Column("notes",             sa.Text()),
        sa.Column("created_at",        sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",        sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product", "version", name="uq_schema_knowledge"),
    )

    # ── Canonical field catalog ───────────────────────────────────
    op.create_table(
        "schema_knowledge_fields",
        sa.Column("id",               sa.String(),    nullable=False),
        sa.Column("knowledge_id",     sa.String(),    nullable=False),
        sa.Column("table_name",       sa.String(255), nullable=False),
        sa.Column("field_name",       sa.String(255), nullable=False),
        sa.Column("data_type",        sa.String(100)),
        sa.Column("description",      sa.Text()),
        sa.Column("domain_id",        sa.String(100)),
        sa.Column("is_pk",            sa.Boolean(),   server_default=sa.false()),
        sa.Column("is_fk",            sa.Boolean(),   server_default=sa.false()),
        sa.Column("references",       sa.String(512)),
        sa.Column("occurrence_count", sa.Integer(),   nullable=False, server_default="1"),
        sa.Column("last_updated",     sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("embedding",        postgresql.JSONB()),  # JSONB fallback; pgvector adds vector type
        sa.ForeignKeyConstraint(["knowledge_id"], ["schema_knowledge.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("knowledge_id", "table_name", "field_name", name="uq_skf"),
    )
    op.create_index("ix_skf_knowledge", "schema_knowledge_fields", ["knowledge_id"])
    op.create_index("ix_skf_knowledge_table", "schema_knowledge_fields", ["knowledge_id", "table_name"])


def downgrade() -> None:
    op.drop_index("ix_skf_knowledge_table", table_name="schema_knowledge_fields")
    op.drop_index("ix_skf_knowledge", table_name="schema_knowledge_fields")
    op.drop_table("schema_knowledge_fields")
    op.drop_table("schema_knowledge")
    op.drop_column("schema_files", "origin")
