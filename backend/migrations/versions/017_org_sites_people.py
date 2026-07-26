"""Product spine: organizations, org members, sites, people, trips

Revision ID: 017
Revises: 016
Create Date: 2026-07-26 00:00:00.000000

The customer-facing product has had no data spine. Before this migration the API
served 50 routes and none of them were sites, people or org: the executive deck
computed every per-site and per-person figure from a 214-row JavaScript fixture in
the browser. This adds the tables everything else joins to.

Tables:
  - organizations   the customer tenant. Flat: no parent_id, no nesting. The
                    incumbent offers "Wipro and Sub-Organizations", but nesting
                    multiplies the cost of every permission check and roll-up, and
                    no customer requirement for it has been observed.
  - org_members     membership + ROLE (admin | analyst | viewer). Role lives here
                    and deliberately NOT on users.tier: tier answers "what has this
                    account paid for" and is already overloaded as the platform-admin
                    check. UNIQUE (org_id, user_id) is enforced in the database
                    rather than by a SELECT-then-409 in route code, which races.
  - sites           the register. Column names mirror the deck fixture exactly
                    (name, city, country, lat, lng, type, criticality, headcount) so
                    the existing pure libs keep working when the fixture is swapped.
                    external_id is the customer's own identifier and is deliberately
                    NOT unique — a real register can repeat one (observed: the same
                    identifier on two rows under different countries), and we must be
                    able to store and REPORT that defect rather than reject the import.
                    headcount is nullable: "no headcount" is an audit finding, not a 0,
                    because defaulting it silently under-reports people at risk.
  - people          employees the customer owes a duty of care to.
  - trips           traveller itineraries. to_site_id is the real join to a location;
                    to_city is display text. Nullable because people travel to cities
                    where the customer has no site, and those trips still need tracking.

Every table carries org_id. All DDL is CREATE ... IF NOT EXISTS so the migration is
re-runnable and self-heals against alembic-version drift (same posture as 008-016).
No data migration here — the register is populated by import, never by a backfill,
and schema/data migrations stay separate.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS org_members (
            id UUID PRIMARY KEY,
            org_id UUID NOT NULL REFERENCES organizations(id),
            user_id UUID NOT NULL REFERENCES users(id),
            role TEXT NOT NULL DEFAULT 'viewer',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_org_members_org_user UNIQUE (org_id, user_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_org_members_user "
        "ON org_members (user_id, is_active)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sites (
            id UUID PRIMARY KEY,
            org_id UUID NOT NULL REFERENCES organizations(id),
            external_id TEXT,
            name TEXT NOT NULL,
            city TEXT,
            country TEXT,
            lat DOUBLE PRECISION,
            lng DOUBLE PRECISION,
            type TEXT NOT NULL DEFAULT 'office',
            criticality TEXT NOT NULL DEFAULT 'tier-3',
            headcount INTEGER,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_sites_org ON sites (org_id, is_active)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sites_org_external ON sites (org_id, external_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_sites_country ON sites (org_id, country)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS people (
            id UUID PRIMARY KEY,
            org_id UUID NOT NULL REFERENCES organizations(id),
            name TEXT NOT NULL,
            email TEXT,
            role TEXT,
            home_site_id UUID REFERENCES sites(id),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_people_org ON people (org_id, is_active)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_people_home_site ON people (home_site_id)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS trips (
            id UUID PRIMARY KEY,
            org_id UUID NOT NULL REFERENCES organizations(id),
            person_id UUID NOT NULL REFERENCES people(id),
            from_site_id UUID REFERENCES sites(id),
            to_site_id UUID REFERENCES sites(id),
            to_city TEXT,
            to_country TEXT,
            to_lat DOUBLE PRECISION,
            to_lng DOUBLE PRECISION,
            depart_date DATE,
            return_date DATE,
            last_check_in_at TIMESTAMPTZ,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trips_org_dates "
        "ON trips (org_id, depart_date, return_date)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_trips_person ON trips (person_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_trips_to_site ON trips (to_site_id)")


def downgrade() -> None:
    # Reverse dependency order: trips -> people -> sites -> org_members -> organizations.
    op.execute("DROP INDEX IF EXISTS ix_trips_to_site")
    op.execute("DROP INDEX IF EXISTS ix_trips_person")
    op.execute("DROP INDEX IF EXISTS ix_trips_org_dates")
    op.execute("DROP TABLE IF EXISTS trips")

    op.execute("DROP INDEX IF EXISTS ix_people_home_site")
    op.execute("DROP INDEX IF EXISTS ix_people_org")
    op.execute("DROP TABLE IF EXISTS people")

    op.execute("DROP INDEX IF EXISTS ix_sites_country")
    op.execute("DROP INDEX IF EXISTS ix_sites_org_external")
    op.execute("DROP INDEX IF EXISTS ix_sites_org")
    op.execute("DROP TABLE IF EXISTS sites")

    op.execute("DROP INDEX IF EXISTS ix_org_members_user")
    op.execute("DROP TABLE IF EXISTS org_members")

    op.execute("DROP TABLE IF EXISTS organizations")
