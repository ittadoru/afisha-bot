import ast
from pathlib import Path

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

    assert len(files) == 22
    assert parents - {None} < revisions
    assert revisions - parents == {"0022_public_event_discovery"}


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
        "discovery": {"cities", "categories", "street_anchors"},
        "events": {
            "events",
            "event_revisions",
            "event_photos",
            "participation_episodes",
            "creation_requests",
            "staff_creation_requests",
            "change_requests",
        },
        "media": {"assets"},
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
        "communication": {"messages", "notifications"},
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
