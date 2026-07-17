"""INT-discipline lens dimension — disciplines[] column on users (idempotent)

Revision ID: 013
Revises: 012
Create Date: 2026-07-17 02:00:00.000000

Phase 2d (folded-in surfaces): the customer lens gains an INT-discipline axis so a
user can favour, say, CYBINT + FININT and have the feed/deck/globe re-rank toward
those disciplines. Stored as a TEXT[] of discipline codes (HUMINT/SIGINT/IMINT/
GEOINT/MASINT/FININT/CYBINT); NULL/empty ⇒ no discipline bias (behaves exactly as
before).

ADD COLUMN IF NOT EXISTS keeps this safe to re-run and self-healing against
alembic-version drift (same posture as 008–012). NULL is read as an empty list by
the app, so an un-migrated row is unaffected.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS disciplines TEXT[]")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS disciplines")
