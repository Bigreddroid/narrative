"""Choosable customer lens — granular profile columns on users (idempotent)

Revision ID: 011
Revises: 010
Create Date: 2026-07-11 00:00:00.000000

Phase 3 (R2): the customer lens becomes granular and user-chosen. Beyond the
existing home city/country + spending_categories, a user now picks:
  - purpose         WHY they watch (protect supply chain / people / capital / sites)
  - regions         named regions / routes / chokepoints they care about
                    (e.g. Rotterdam, Strait of Hormuz, Suez) — distinct from home
  - watched_assets  named entities (suppliers, ports, counterparties, companies)

Every screen then computes strictly through profile_exposure over this profile,
so two profiles yield two different apps on the same events.

ADD COLUMN IF NOT EXISTS keeps this safe to re-run and self-healing against
alembic-version drift (same posture as 008/009/010). NULL columns are read as
empty lists by the app, so an un-migrated row behaves exactly as before.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS purpose TEXT[]")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS regions TEXT[]")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS watched_assets TEXT[]")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS purpose")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS regions")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS watched_assets")
