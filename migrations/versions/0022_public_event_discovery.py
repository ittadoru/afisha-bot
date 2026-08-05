"""Add privacy-safe street anchors for public event discovery."""

from collections.abc import Sequence

from alembic import op

revision: str = "0022_public_event_discovery"
down_revision: str | None = "0021_published_event_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE discovery.street_anchors (
            id uuid PRIMARY KEY,
            city_id uuid NOT NULL REFERENCES discovery.cities(id),
            street_key varchar(200) NOT NULL,
            display_name varchar(200) NOT NULL,
            provider_place_id varchar(100) NOT NULL,
            anchor geography(Point,4326) NOT NULL,
            geometry_version integer NOT NULL DEFAULT 1 CHECK (geometry_version>0),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (city_id,street_key)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_discovery_street_anchors_point "
        "ON discovery.street_anchors USING gist(anchor)"
    )
    op.execute(
        "ALTER TABLE events.event_revisions ADD COLUMN street_anchor_id uuid "
        "REFERENCES discovery.street_anchors(id)"
    )
    op.execute(
        "ALTER TABLE events.event_revisions ADD CONSTRAINT "
        "event_revisions_hidden_anchor_check CHECK "
        "(address_visibility='exact_public' OR street_anchor_id IS NOT NULL) NOT VALID"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE events.event_revisions DROP CONSTRAINT "
        "event_revisions_hidden_anchor_check"
    )
    op.execute("ALTER TABLE events.event_revisions DROP COLUMN street_anchor_id")
    op.execute("DROP TABLE discovery.street_anchors")
