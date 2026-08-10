"""Add customizable profile backgrounds."""

from collections.abc import Sequence

from alembic import op

revision: str = "0031_profile_backgrounds"
down_revision: str | None = "0030_staff_street_anchors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE accounts.profiles ADD COLUMN background_asset_id uuid")
    op.execute(
        "ALTER TABLE trust_safety.profile_reports "
        "ADD COLUMN background_asset_id uuid"
    )
    op.execute("ALTER TABLE media.assets DROP CONSTRAINT assets_purpose_check")
    op.execute(
        "ALTER TABLE media.assets ADD CONSTRAINT assets_purpose_check "
        "CHECK (purpose IN ('profile_avatar', 'profile_background', 'event_photo'))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE media.assets DROP CONSTRAINT assets_purpose_check")
    op.execute(
        "ALTER TABLE media.assets ADD CONSTRAINT assets_purpose_check "
        "CHECK (purpose IN ('profile_avatar', 'event_photo'))"
    )
    op.execute(
        "ALTER TABLE trust_safety.profile_reports DROP COLUMN background_asset_id"
    )
    op.execute("ALTER TABLE accounts.profiles DROP COLUMN background_asset_id")
