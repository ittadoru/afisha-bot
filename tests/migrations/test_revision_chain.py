import ast
from pathlib import Path

from afishabot.core.database import EXPECTED_MIGRATION_HEAD

VERSIONS = Path("migrations/versions")
EXPECTED_SCHEMAS = {
    "accounts",
    "communication",
    "discovery",
    "events",
    "media",
    "reputation",
    "trust_safety",
}


def revision_value(path: Path, name: str) -> str | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            if node.value is None:
                raise AssertionError(f"{name} has no value in {path}")
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path}")


def test_alembic_chain_has_exactly_one_head() -> None:
    files = sorted(VERSIONS.glob("*.py"))
    revisions = {revision_value(path, "revision") for path in files}
    parents = {revision_value(path, "down_revision") for path in files}

    assert len(files) == 36
    assert parents - {None} < revisions
    assert revisions - parents == {"0036_typed_moderation_evidence"}
    assert EXPECTED_MIGRATION_HEAD in revisions - parents


def test_profile_background_migration_updates_profiles_reports_and_media() -> None:
    text = (VERSIONS / "0031_profile_backgrounds.py").read_text(encoding="utf-8")

    assert "ALTER TABLE accounts.profiles ADD COLUMN background_asset_id" in text
    assert "ALTER TABLE trust_safety.profile_reports " in text
    assert '"ADD COLUMN background_asset_id uuid"' in text
    assert "profile_background" in text


def test_category_unification_migration_remaps_records_before_deactivation() -> None:
    text = (VERSIONS / "0035_unify_categories_and_map_markers.py").read_text(
        encoding="utf-8"
    )

    release_sort_orders = (
        "UPDATE discovery.categories SET sort_order = sort_order + 100;"
    )
    assign_sort_orders = "color_key = values.color_key, sort_order = values.sort_order"

    assert release_sort_orders in text
    assert text.index(release_sort_orders) < text.index(assign_sort_orders)
    assert "UPDATE events.events" in text
    assert "UPDATE discovery.looking_posts" in text
    assert "('cafe','entertainment','walks','work')" in text
    assert "'Прогулки и поездки'" in text
    assert "'Обучение и работа'" in text


def test_platform_extension_and_seven_owner_schemas_exist() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(VERSIONS.glob("*.py"))
    )

    assert "CREATE EXTENSION IF NOT EXISTS postgis" in text
    for schema in EXPECTED_SCHEMAS:
        assert f"CREATE SCHEMA {schema}" in text


def test_mvp_foundation_tables_are_owned_by_the_expected_schemas() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(VERSIONS.glob("*.py"))
    )
    expected_tables = {
        "accounts": {
            "users",
            "telegram_identities",
            "profiles",
            "sessions",
            "age_acceptances",
        },
        "discovery": {
            "cities",
            "categories",
            "street_anchors",
            "looking_posts",
            "looking_post_likes",
            "looking_post_questions",
            "looking_post_requests",
        },
        "events": {
            "events",
            "event_revisions",
            "event_photos",
            "participation_episodes",
            "event_interests",
            "waitlist_entries",
            "creation_requests",
            "staff_creation_requests",
            "change_requests",
        },
        "media": {"assets", "storage_analysis"},
        "trust_safety": {
            "event_reviews",
            "profile_reports",
            "staff_accounts",
            "staff_credentials",
            "staff_sessions",
            "staff_login_limits",
            "staff_permissions",
            "staff_audit_log",
        },
        "reputation": {"organizer_profiles"},
        "communication": {"messages", "notifications", "chat_message_requests"},
    }

    for schema, tables in expected_tables.items():
        for table in tables:
            assert f"CREATE TABLE {schema}.{table}" in text


def test_foundation_keeps_module_boundaries_and_key_product_constraints() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(VERSIONS.glob("*.py"))
    )

    assert "telegram_user_id bigint NOT NULL UNIQUE" in text
    assert "capacity IS NULL OR capacity >= 3" in text
    assert "schedule_changes_used BETWEEN 0 AND 1" in text
    assert "uq_events_one_pending_revision" in text
    assert "uq_events_active_participation" in text
    assert "uq_events_active_waitlist" in text
    assert "queue_order bigint GENERATED ALWAYS AS IDENTITY" in text
    assert "geography(Point, 4326)" in text
    owner_migrations = [
        VERSIONS / "0011_events_foundation.py",
        VERSIONS / "0012_media_foundation.py",
        VERSIONS / "0013_event_moderation_foundation.py",
        VERSIONS / "0014_communication_foundation.py",
    ]
    assert all(
        "REFERENCES accounts." not in path.read_text(encoding="utf-8")
        for path in owner_migrations
    )
