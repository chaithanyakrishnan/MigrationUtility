"""Initial schema — all tables

Revision ID: 001
Revises:
Create Date: 2026-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Extensions ───────────────────────────────────────────────
    # Handled by app/db/session.py init_db() at startup — not here.
    # Reason: CREATE EXTENSION must run outside a transaction, which
    # Alembic's psycopg2 connection does not support cleanly.
    # pgvector and pg_trgm are optional — the app degrades gracefully without them.

    # ── Tables ────────────────────────────────────────────────────
    op.create_table(
        "engagements",
        sa.Column("id",             sa.String(),       nullable=False),
        sa.Column("name",           sa.String(255),    nullable=False),
        sa.Column("client_name",    sa.String(255),    nullable=False),
        sa.Column("status",         sa.String(50),     nullable=False, server_default="active"),
        sa.Column("current_step",   sa.Integer(),      nullable=False, server_default="1"),
        sa.Column("max_unlocked",   sa.Integer(),      nullable=False, server_default="1"),
        sa.Column("relius_version", sa.String(50)),
        sa.Column("omni_version",   sa.String(50)),
        sa.Column("created_by",     sa.String(255),    nullable=False),
        sa.Column("created_at",     sa.DateTime(),     nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",     sa.DateTime(),     nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "schema_files",
        sa.Column("id",            sa.String(),    nullable=False),
        sa.Column("engagement_id", sa.String(),    sa.ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("side",          sa.String(10),  nullable=False),
        sa.Column("filename",      sa.String(512), nullable=False),
        sa.Column("file_type",     sa.String(50)),
        sa.Column("size_bytes",    sa.BigInteger()),
        sa.Column("s3_key",        sa.String(1024)),
        sa.Column("parse_status",  sa.String(50),  nullable=False, server_default="pending"),
        sa.Column("parse_result",  postgresql.JSONB()),
        sa.Column("parse_error",   sa.Text()),
        sa.Column("uploaded_by",   sa.String(255), nullable=False),
        sa.Column("uploaded_at",   sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "domain_reviews",
        sa.Column("id",             sa.String(),    nullable=False),
        sa.Column("engagement_id",  sa.String(),    sa.ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("side",           sa.String(10),  nullable=False),
        sa.Column("domain_id",      sa.String(100), nullable=False),
        sa.Column("approved",       sa.Boolean(),   nullable=False, server_default="false"),
        sa.Column("completeness",   sa.Integer()),
        sa.Column("field_edits",    postgresql.JSONB()),
        sa.Column("include_fields", postgresql.JSONB()),
        sa.Column("exclude_fields", postgresql.JSONB()),
        sa.Column("reviewed_by",    sa.String(255)),
        sa.Column("reviewed_at",    sa.DateTime()),
        sa.Column("created_at",     sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",     sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("engagement_id", "domain_id", "side", name="uq_domain_review"),
    )

    op.create_table(
        "field_embeddings",
        sa.Column("id",                sa.String(),     nullable=False),
        sa.Column("engagement_id",     sa.String(),     sa.ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("side",              sa.String(10),   nullable=False),
        sa.Column("table_name",        sa.String(255),  nullable=False),
        sa.Column("field_name",        sa.String(255),  nullable=False),
        sa.Column("domain_id",         sa.String(100)),
        sa.Column("data_type",         sa.String(100)),
        sa.Column("description",       sa.Text()),
        sa.Column("embedding",         postgresql.JSONB()),  # JSONB fallback; pgvector adds vector type
        sa.Column("embedding_version", sa.String(50),   server_default="v1"),
        sa.Column("created_at",        sa.DateTime(),   nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",        sa.DateTime(),   nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_field_embed_engagement", "field_embeddings", ["engagement_id"])

    op.create_table(
        "mapping_entries",
        sa.Column("id",              sa.String(),    nullable=False),
        sa.Column("engagement_id",   sa.String(),    sa.ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain_id",       sa.String(100), nullable=False),
        sa.Column("src_table",       sa.String(255), nullable=False),
        sa.Column("src_field",       sa.String(255), nullable=False),
        sa.Column("src_display",     sa.String(512)),
        sa.Column("tgt_table",       sa.String(255), nullable=False),
        sa.Column("tgt_field",       sa.String(255), nullable=False),
        sa.Column("tgt_display",     sa.String(512)),
        sa.Column("confidence",      sa.Integer(),   nullable=False),
        sa.Column("mapping_type",    sa.String(50)),
        sa.Column("transform_rule",  sa.Text()),
        sa.Column("is_multi_source", sa.Boolean(),   server_default="false"),
        sa.Column("multi_sources",   postgresql.JSONB()),
        sa.Column("is_udf",          sa.Boolean(),   server_default="false"),
        sa.Column("is_constant",     sa.Boolean(),   server_default="false"),
        sa.Column("constant_value",  sa.String(255)),
        sa.Column("note",            sa.Text()),
        sa.Column("status",          sa.String(50),  nullable=False, server_default="pending"),
        sa.Column("approved_by",     sa.String(255)),
        sa.Column("approved_at",     sa.DateTime()),
        sa.Column("git_commit_sha",  sa.String(64)),
        sa.Column("i4_source",       sa.Boolean(),   server_default="false"),
        sa.Column("created_at",      sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",      sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "engagement_id", "src_table", "src_field", "tgt_table", "tgt_field",
            name="uq_mapping_entry",
        ),
    )
    op.create_index("ix_mapping_engagement_domain", "mapping_entries", ["engagement_id", "domain_id"])

    op.create_table(
        "control_files",
        sa.Column("id",                 sa.String(),    nullable=False),
        sa.Column("engagement_id",      sa.String(),    sa.ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("filename",           sa.String(512), nullable=False),
        sa.Column("file_type",          sa.String(100)),
        sa.Column("s3_key",             sa.String(1024)),
        sa.Column("line_count",         sa.Integer()),
        sa.Column("parsed_kv",          postgresql.JSONB()),
        sa.Column("env_specific_flags", postgresql.JSONB()),
        sa.Column("uploaded_by",        sa.String(255), nullable=False),
        sa.Column("uploaded_at",        sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "etl_artefacts",
        sa.Column("id",                sa.String(),    nullable=False),
        sa.Column("engagement_id",     sa.String(),    sa.ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("artefact_type",     sa.String(100), nullable=False),
        sa.Column("filename",          sa.String(512), nullable=False),
        sa.Column("s3_key",            sa.String(1024)),
        sa.Column("content_hash",      sa.String(128)),
        sa.Column("generation_config", postgresql.JSONB()),
        sa.Column("generated_by",      sa.String(255)),
        sa.Column("generated_at",      sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "recon_results",
        sa.Column("id",            sa.String(),   nullable=False),
        sa.Column("engagement_id", sa.String(),   sa.ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id",        sa.String(),   nullable=False),
        sa.Column("check_id",      sa.String(100), nullable=False),
        sa.Column("check_name",    sa.String(255), nullable=False),
        sa.Column("status",        sa.String(20),  nullable=False),
        sa.Column("expected",      sa.Text()),
        sa.Column("actual",        sa.Text()),
        sa.Column("delta",         sa.Float()),
        sa.Column("detail",        postgresql.JSONB()),
        sa.Column("auto_resolved", sa.Boolean(),  server_default="false"),
        sa.Column("resolution",    sa.Text()),
        sa.Column("run_at",        sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id",            sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("engagement_id", sa.String(),     sa.ForeignKey("engagements.id"), nullable=True),
        sa.Column("event_type",    sa.String(100),  nullable=False),
        sa.Column("actor_type",    sa.String(20),   nullable=False),
        sa.Column("actor_id",      sa.String(255)),
        sa.Column("summary",       sa.Text(),       nullable=False),
        sa.Column("detail",        postgresql.JSONB()),
        sa.Column("created_at",    sa.DateTime(),   nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_engagement_ts", "audit_events", ["engagement_id", "created_at"])

    op.create_table(
        "learned_mappings",
        sa.Column("id",               sa.String(),    nullable=False),
        sa.Column("plan_type",        sa.String(100), nullable=False),
        sa.Column("relius_version",   sa.String(50)),
        sa.Column("omni_version",     sa.String(50)),
        sa.Column("src_table",        sa.String(255), nullable=False),
        sa.Column("src_field",        sa.String(255), nullable=False),
        sa.Column("tgt_table",        sa.String(255), nullable=False),
        sa.Column("tgt_field",        sa.String(255), nullable=False),
        sa.Column("mapping_type",     sa.String(50)),
        sa.Column("transform_rule",   sa.Text()),
        sa.Column("confidence_prior", sa.Integer()),
        sa.Column("approval_count",   sa.Integer(),   server_default="1"),
        sa.Column("rejection_count",  sa.Integer(),   server_default="0"),
        sa.Column("embedding",        postgresql.JSONB()),
        sa.Column("last_seen_at",     sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("created_at",       sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_learned_plan_type", "learned_mappings", ["plan_type", "relius_version"])


def downgrade() -> None:
    for tbl in [
        "learned_mappings", "audit_events", "recon_results", "etl_artefacts",
        "control_files", "mapping_entries", "field_embeddings",
        "domain_reviews", "schema_files", "engagements",
    ]:
        op.drop_table(tbl)
