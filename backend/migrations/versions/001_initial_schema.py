"""Initial schema — all tables + pgvector + pg_trgm

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("rss_url", sa.Text),
        sa.Column("country", sa.Text),
        sa.Column("category", sa.Text),
        sa.Column("bias_rating", sa.Text),
        sa.Column("bias_source", sa.Text),
        sa.Column("scrape_method", sa.Text, server_default="rss"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True)),
        sa.Column("scrape_error_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "narrative_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("canonical_title", sa.Text, nullable=False),
        sa.Column("canonical_summary", sa.Text),
        sa.Column("category", sa.Text),
        sa.Column("global_importance_score", sa.Float, server_default="0"),
        sa.Column("current_status", sa.Text, server_default="developing"),
        sa.Column("affected_sectors", postgresql.ARRAY(sa.Text)),
        sa.Column("affected_professions", postgresql.ARRAY(sa.Text)),
        sa.Column("geographic_relevance", postgresql.ARRAY(sa.Text)),
        sa.Column("geo_centroid_lat", sa.Float),
        sa.Column("geo_centroid_lng", sa.Float),
        sa.Column("follow_keywords", postgresql.ARRAY(sa.Text)),
        sa.Column("is_mapped", sa.Boolean, server_default="false"),
        sa.Column("is_importance_scored", sa.Boolean, server_default="false"),
        sa.Column("is_graph_connected", sa.Boolean, server_default="false"),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_updated_at", sa.DateTime(timezone=True)),
        sa.Column("embedding", Vector(1024)),
    )

    op.create_table(
        "articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id")),
        sa.Column("narrative_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("narrative_events.id")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("url_hash", sa.Text, unique=True, nullable=False),
        sa.Column("content", sa.Text),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("importance_score", sa.Float, server_default="0"),
        sa.Column("embedding", Vector(1024)),
        sa.Column("is_embedded", sa.Boolean, server_default="false"),
        sa.Column("is_clustered", sa.Boolean, server_default="false"),
        sa.Column("is_processed", sa.Boolean, server_default="false"),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("is_archived", sa.Boolean, server_default="false"),
    )

    op.create_table(
        "event_consequence_maps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("narrative_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("narrative_events.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("consensus_summary", sa.Text),
        sa.Column("disputed_points", postgresql.ARRAY(sa.Text)),
        sa.Column("consequence_chain", postgresql.JSONB),
        sa.Column("direct_impact", postgresql.JSONB),
        sa.Column("indirect_impact", postgresql.JSONB),
        sa.Column("prediction_score", sa.Integer),
        sa.Column("prediction_reasoning", sa.Text),
        sa.Column("confidence", sa.Text),
        sa.Column("sources_analyzed", postgresql.ARRAY(sa.Text)),
        sa.Column("is_suppressed", sa.Boolean, server_default="false"),
        sa.Column("suppression_reason", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "event_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_a_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("narrative_events.id"), nullable=False),
        sa.Column("event_b_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("narrative_events.id"), nullable=False),
        sa.Column("connection_type", sa.Text),
        sa.Column("connection_weight", sa.Float),
        sa.Column("shared_sectors", postgresql.ARRAY(sa.Text)),
        sa.Column("shared_geography", postgresql.ARRAY(sa.Text)),
        sa.Column("shared_context", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "event_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("narrative_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("narrative_events.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("consequence_chain", postgresql.JSONB),
        sa.Column("prediction_score", sa.Integer),
        sa.Column("confidence", sa.Text),
        sa.Column("change_summary", sa.Text),
        sa.Column("triggered_by", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "prediction_outcomes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("narrative_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("narrative_events.id"), nullable=False),
        sa.Column("original_prediction_score", sa.Integer),
        sa.Column("predicted_timeline", sa.Text),
        sa.Column("actual_outcome", sa.Text),
        sa.Column("outcome_notes", sa.Text),
        sa.Column("evaluated_at", sa.DateTime(timezone=True)),
        sa.Column("calibration_error", sa.Float),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text, unique=True, nullable=False),
        sa.Column("city", sa.Text),
        sa.Column("country", sa.Text),
        sa.Column("profession", sa.Text),
        sa.Column("spending_categories", postgresql.ARRAY(sa.Text)),
        sa.Column("tier", sa.Text, server_default="free"),
        sa.Column("stripe_customer_id", sa.Text),
        sa.Column("revenue_cat_id", sa.Text),
        sa.Column("fcm_token", sa.Text),
        sa.Column("notification_preferences", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "user_follows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("narrative_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("narrative_events.id"), nullable=False),
        sa.Column("follow_keywords", postgresql.ARRAY(sa.Text)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("is_active", sa.Boolean, server_default="true"),
    )

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("narrative_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("narrative_events.id")),
        sa.Column("type", sa.Text),
        sa.Column("payload", postgresql.JSONB),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "segment_feed_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("segment_key", sa.Text, unique=True, nullable=False),
        sa.Column("event_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True))),
        sa.Column("built_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "admin_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target_type", sa.Text),
        sa.Column("target_id", postgresql.UUID(as_uuid=True)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "pipeline_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("worker_name", sa.Text, nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("articles_scraped", sa.Integer, server_default="0"),
        sa.Column("articles_embedded", sa.Integer, server_default="0"),
        sa.Column("clusters_created", sa.Integer, server_default="0"),
        sa.Column("events_mapped", sa.Integer, server_default="0"),
        sa.Column("connections_computed", sa.Integer, server_default="0"),
        sa.Column("alerts_sent", sa.Integer, server_default="0"),
        sa.Column("claude_calls", sa.Integer, server_default="0"),
        sa.Column("claude_tokens_used", sa.Integer, server_default="0"),
        sa.Column("claude_cost_usd", sa.Float, server_default="0"),
        sa.Column("errors", sa.Integer, server_default="0"),
        sa.Column("duration_seconds", sa.Float),
    )

    # Indexes for pipeline performance
    op.create_index("ix_articles_is_embedded", "articles", ["is_embedded"])
    op.create_index("ix_articles_is_clustered", "articles", ["is_clustered"])
    op.create_index("ix_articles_is_processed", "articles", ["is_processed"])
    op.create_index("ix_articles_narrative_event_id", "articles", ["narrative_event_id"])
    op.create_index("ix_articles_source_id", "articles", ["source_id"])
    op.create_index("ix_narrative_events_is_mapped", "narrative_events", ["is_mapped"])
    op.create_index("ix_narrative_events_is_graph_connected", "narrative_events", ["is_graph_connected"])
    op.create_index("ix_narrative_events_category", "narrative_events", ["category"])
    op.create_index("ix_narrative_events_current_status", "narrative_events", ["current_status"])
    op.create_index("ix_event_connections_event_a_id", "event_connections", ["event_a_id"])
    op.create_index("ix_event_connections_event_b_id", "event_connections", ["event_b_id"])
    op.create_index("ix_user_follows_user_id", "user_follows", ["user_id"])
    op.create_index("ix_user_follows_narrative_event_id", "user_follows", ["narrative_event_id"])
    op.create_index("ix_pipeline_metrics_worker_name", "pipeline_metrics", ["worker_name"])
    op.create_index("ix_pipeline_metrics_run_at", "pipeline_metrics", ["run_at"])

    # HNSW index for fast ANN search on article embeddings
    op.execute("""
        CREATE INDEX ix_articles_embedding_hnsw
        ON articles
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # HNSW index for narrative_events embeddings
    op.execute("""
        CREATE INDEX ix_narrative_events_embedding_hnsw
        ON narrative_events
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.drop_index("ix_narrative_events_embedding_hnsw", "narrative_events")
    op.drop_index("ix_articles_embedding_hnsw", "articles")
    op.drop_table("pipeline_metrics")
    op.drop_table("admin_logs")
    op.drop_table("segment_feed_cache")
    op.drop_table("notifications")
    op.drop_table("user_follows")
    op.drop_table("users")
    op.drop_table("prediction_outcomes")
    op.drop_table("event_revisions")
    op.drop_table("event_connections")
    op.drop_table("event_consequence_maps")
    op.drop_table("articles")
    op.drop_table("narrative_events")
    op.drop_table("sources")
