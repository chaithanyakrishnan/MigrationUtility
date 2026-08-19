"""v5 Knowledge-Base architecture: KB catalogues + migration-project tables

Revision ID: 003
Revises: 002
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    # ── Knowledge Bases ───────────────────────────────────────
    op.create_table(
        "knowledge_bases",
        sa.Column("id",         sa.String(), nullable=False),
        sa.Column("kind",       sa.String(20), nullable=False),
        sa.Column("status",     sa.String(20), nullable=False, server_default="draft"),
        sa.Column("version",    sa.String(50), nullable=False, server_default="v1"),
        sa.Column("stats",      JSONB),
        sa.Column("load_order", JSONB),
        sa.Column("constants",  JSONB),
        sa.Column("built_at",   sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", name="uq_kb_kind"),
    )

    op.create_table(
        "kb_relius_domains",
        sa.Column("id",           sa.String(), nullable=False),
        sa.Column("kb_id",        sa.String(), nullable=False),
        sa.Column("domain_id",    sa.String(100), nullable=False),
        sa.Column("name",         sa.String(255), nullable=False),
        sa.Column("icon",         sa.String(16)),
        sa.Column("table_count",  sa.Integer(), server_default="0"),
        sa.Column("row_estimate", sa.String(50)),
        sa.Column("completeness", sa.Integer(), server_default="0"),
        sa.Column("tables",       JSONB),
        sa.Column("approved",     sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order",   sa.Integer(), server_default="0"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_relius_domain_kb", "kb_relius_domains", ["kb_id"])

    op.create_table(
        "kb_relius_fields",
        sa.Column("id",           sa.String(), nullable=False),
        sa.Column("domain_id",    sa.String(), nullable=False),
        sa.Column("table_name",   sa.String(255), nullable=False),
        sa.Column("field_name",   sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255)),
        sa.Column("data_type",    sa.String(100)),
        sa.Column("description",  sa.Text()),
        sa.Column("is_key",       sa.Boolean(), server_default=sa.false()),
        sa.Column("included",     sa.Boolean(), server_default=sa.true()),
        sa.Column("approved",     sa.Boolean(), server_default=sa.false()),
        sa.Column("sort_order",   sa.Integer(), server_default="0"),
        sa.ForeignKeyConstraint(["domain_id"], ["kb_relius_domains.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_relius_field_domain", "kb_relius_fields", ["domain_id"])

    op.create_table(
        "kb_omni_records",
        sa.Column("id",             sa.String(), nullable=False),
        sa.Column("kb_id",          sa.String(), nullable=False),
        sa.Column("record_id",      sa.String(100), nullable=False),
        sa.Column("prefix",         sa.String(20)),
        sa.Column("name",           sa.String(255), nullable=False),
        sa.Column("icon",           sa.String(16)),
        sa.Column("category",       sa.String(100)),
        sa.Column("category_color", sa.String(20)),
        sa.Column("description",    sa.Text()),
        sa.Column("approved",       sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order",     sa.Integer(), server_default="0"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_omni_record_kb", "kb_omni_records", ["kb_id"])

    op.create_table(
        "kb_omni_fields",
        sa.Column("id",           sa.String(), nullable=False),
        sa.Column("record_id",    sa.String(), nullable=False),
        sa.Column("code",         sa.String(50), nullable=False),
        sa.Column("name",         sa.String(255), nullable=False),
        sa.Column("description",  sa.Text()),
        sa.Column("is_key",       sa.Boolean(), server_default=sa.false()),
        sa.Column("legal_values", JSONB),
        sa.Column("included",     sa.Boolean(), server_default=sa.true()),
        sa.Column("approved",     sa.Boolean(), server_default=sa.false()),
        sa.Column("sort_order",   sa.Integer(), server_default="0"),
        sa.ForeignKeyConstraint(["record_id"], ["kb_omni_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_omni_field_record", "kb_omni_fields", ["record_id"])

    op.create_table(
        "kb_transaction_cards",
        sa.Column("id",            sa.String(), nullable=False),
        sa.Column("kb_id",         sa.String(), nullable=False),
        sa.Column("code",          sa.String(20), nullable=False),
        sa.Column("name",          sa.String(255)),
        sa.Column("category",      sa.String(100)),
        sa.Column("icon",          sa.String(16)),
        sa.Column("has_layout",    sa.Boolean(), server_default=sa.false()),
        sa.Column("record_length", sa.Integer(), server_default="110"),
        sa.Column("note",          sa.Text()),
        sa.Column("approved",      sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("selected",      sa.Boolean(), server_default=sa.false()),
        sa.Column("sort_order",    sa.Integer(), server_default="0"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_txn_card_kb", "kb_transaction_cards", ["kb_id"])

    op.create_table(
        "kb_transaction_card_fields",
        sa.Column("id",         sa.String(), nullable=False),
        sa.Column("card_id",    sa.String(), nullable=False),
        sa.Column("sub_card",   sa.String(10), server_default="01"),
        sa.Column("code",       sa.String(50), nullable=False),
        sa.Column("name",       sa.String(255)),
        sa.Column("col_range",  sa.String(20)),
        sa.Column("picture",    sa.String(50)),
        sa.Column("req_opt",    sa.String(10)),
        sa.Column("src_guess",  sa.String(255)),
        sa.Column("confidence", sa.Integer()),
        sa.Column("field_type", sa.String(50)),
        sa.Column("note",       sa.Text()),
        sa.Column("sort_order", sa.Integer(), server_default="0"),
        sa.ForeignKeyConstraint(["card_id"], ["kb_transaction_cards.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kb_txn_field_card", "kb_transaction_card_fields", ["card_id"])

    # ── Migration project ─────────────────────────────────────
    op.create_table(
        "project_state",
        sa.Column("id",              sa.String(), nullable=False),
        sa.Column("engagement_id",   sa.String(), nullable=False),
        sa.Column("selected_tables", JSONB),
        sa.Column("approved_cards",  JSONB),
        sa.Column("mapping_seeded",  sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at",      sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",      sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("engagement_id", name="uq_project_state"),
    )

    op.create_table(
        "project_mappings",
        sa.Column("id",            sa.String(), nullable=False),
        sa.Column("engagement_id", sa.String(), nullable=False),
        sa.Column("domain_id",     sa.String(100)),
        sa.Column("src_table",     sa.String(255), nullable=False),
        sa.Column("src_field",     sa.String(255), nullable=False),
        sa.Column("omni_record",   sa.String(255)),
        sa.Column("tgt_display",   sa.String(512)),
        sa.Column("txn_code",      sa.String(20)),
        sa.Column("confidence",    sa.Integer(), server_default="0"),
        sa.Column("mapping_type",  sa.String(50)),
        sa.Column("note",          sa.Text()),
        sa.Column("is_multi",      sa.Boolean(), server_default=sa.false()),
        sa.Column("approved",      sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("omni_override", sa.String(255)),
        sa.Column("tgt_override",  sa.String(512)),
        sa.Column("txn_override",  sa.String(20)),
        sa.Column("sort_order",    sa.Integer(), server_default="0"),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_project_mapping_eng", "project_mappings", ["engagement_id"])

    op.create_table(
        "project_exports",
        sa.Column("id",            sa.String(), nullable=False),
        sa.Column("engagement_id", sa.String(), nullable=False),
        sa.Column("filename",      sa.String(512), nullable=False),
        sa.Column("content",       sa.Text()),
        sa.Column("line_count",    sa.Integer(), server_default="0"),
        sa.Column("files_read",    sa.Integer(), server_default="0"),
        sa.Column("manifest",      JSONB),
        sa.Column("created_at",    sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for tbl in (
        "project_exports", "project_mappings", "project_state",
        "kb_transaction_card_fields", "kb_transaction_cards",
        "kb_omni_fields", "kb_omni_records",
        "kb_relius_fields", "kb_relius_domains",
        "knowledge_bases",
    ):
        op.drop_table(tbl)
