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
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                if node.value is None:
                    raise AssertionError(f"{name} has no value in {path}")
                return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path}")


def test_alembic_chain_has_exactly_one_head() -> None:
    files = sorted(VERSIONS.glob("*.py"))
    revisions = {revision_value(path, "revision") for path in files}
    parents = {revision_value(path, "down_revision") for path in files}

    assert len(files) == 8
    assert parents - {None} < revisions
    assert revisions - parents == {"0008_media_schema"}


def test_only_platform_extension_and_seven_schemas_exist() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(VERSIONS.glob("*.py"))
    )

    assert "CREATE EXTENSION IF NOT EXISTS postgis" in text
    for schema in EXPECTED_SCHEMAS:
        assert f"CREATE SCHEMA {schema}" in text
    assert "CREATE TABLE" not in text.upper()
