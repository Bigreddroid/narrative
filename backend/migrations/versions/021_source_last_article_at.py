"""Record when a source last actually YIELDED an article.

`scrape_error_count` answers "could we read this feed?" and quarantine acts on it.
Neither answers "is this feed still giving us anything?", and the two are not the
same question. Measured on the live corpus, three states were indistinguishable:

    Brookings Institution   HTTP 200, 0 items, 0 articles ever
    The Defense Post        HTTP 200, 0 items, 0 articles ever
    Straits Times           HTTP 200, 10 items, none new since Jul 13
    Crisis Group            HTTP 200, 10 items, none new since Jul 13

Every one of those reported `scrape_error_count = 0` and a `last_scraped_at` of
minutes ago — indistinguishable from a healthy feed. `scrape_source` treats an
empty list as a success (correctly: the feed answered), so a feed that answers
with nothing forever looks perfectly well and resets its own failure streak on
every cycle. This is the same class of bug as the festival tile claiming a layer
was "checked" when it was hardcoded empty: the system could not tell you what it
had stopped hearing from.

`last_article_at` is stamped only when a scrape produces a NEW article, so
"answered" and "delivered" become separate facts.

Backfilled from `articles` rather than left NULL, because a NULL would read as
"never yielded" for every healthy feed on the first deploy and the health view
would open with 120 false alarms. `max(scraped_at)` is the right source: it is
when WE received the article, which is what feed health is about (a publisher
backdating `published_at` must not look like rot).

Revision ID: 021
Revises: 020
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("last_article_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Seed from what we already hold so the column is true on day one. Sources that
    # genuinely never delivered stay NULL — which is the correct, and useful, answer.
    op.execute(
        """
        UPDATE sources s
           SET last_article_at = sub.max_scraped
          FROM (SELECT source_id, max(scraped_at) AS max_scraped
                  FROM articles
                 GROUP BY source_id) AS sub
         WHERE sub.source_id = s.id
        """
    )


def downgrade() -> None:
    op.drop_column("sources", "last_article_at")
