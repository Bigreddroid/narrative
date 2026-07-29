"""Normalise current_status and category on existing events.

backend/taxonomy.py now normalises these where the mapper WRITES them, but rows
already in the table were persisted straight from the LLM's answer, and the model
does not reliably honour the enum it is handed. Live data carried:

    current_status : "Developing" x4, "Escalating" x2, plus 2 empty
    category       : "Economy", "Geopolitics|Economy", "Geopolitics/Economy"

Every one of those rows was invisible to the matching filter — an off-vocabulary
value matches nothing, and nothing on the board indicated the row had been dropped.
The read paths were made case-insensitive as a stopgap; this migration fixes the
stored data so the stopgap is not load-bearing.

Deliberately data-only: no schema change, and no CHECK constraint. A constraint
would make a future off-enum answer from the model crash the mapping worker rather
than degrade to a known value, which trades a silent wrong row for a dead pipeline.

Irreversible by design — the downgrade is a no-op because the original values were
malformed and there is nothing worth restoring them to.

Revision ID: 020
Revises: 019
"""

from typing import Sequence, Union

from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Keep in lockstep with backend/taxonomy.py STATUSES / DEFAULT_STATUS.
STATUSES = ("developing", "escalating", "stable", "resolved")
DEFAULT_STATUS = "developing"


def upgrade() -> None:
    # 1. Case only — "Developing" -> "developing".
    op.execute(
        """
        UPDATE narrative_events
           SET current_status = lower(btrim(current_status))
         WHERE current_status IS NOT NULL
           AND current_status <> lower(btrim(current_status))
        """
    )
    # 2. Missing or unrecognisable -> the default, so every row answers a status
    #    filter as SOMETHING rather than falling through every column.
    known = ", ".join(f"'{s}'" for s in STATUSES)
    op.execute(
        f"""
        UPDATE narrative_events
           SET current_status = '{DEFAULT_STATUS}'
         WHERE current_status IS NULL
            OR btrim(current_status) = ''
            OR lower(btrim(current_status)) NOT IN ({known})
        """
    )
    # 3. Category: fold case, then take the first part of a joined answer
    #    ("Geopolitics|Economy" -> "geopolitics"). split_part on the first
    #    separator handles both observed shapes.
    op.execute(
        """
        UPDATE narrative_events
           SET category = lower(btrim(category))
         WHERE category IS NOT NULL
           AND category <> lower(btrim(category))
        """
    )
    op.execute(
        """
        UPDATE narrative_events
           SET category = btrim(split_part(regexp_replace(category, '[|/,;]', '|', 'g'), '|', 1))
         WHERE category IS NOT NULL
           AND category ~ '[|/,;]'
        """
    )


def downgrade() -> None:
    """No-op: the previous values were malformed, not meaningful."""
