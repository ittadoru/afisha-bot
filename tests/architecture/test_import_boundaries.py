import ast
from pathlib import Path

MODULES = {
    "accounts",
    "communication",
    "discovery",
    "events",
    "media",
    "reputation",
    "trust_safety",
}
FORBIDDEN_DOMAIN_ROOTS = {"fastapi", "sqlalchemy", "celery", "redis"}
SOURCE_ROOT = Path("src/afishabot/modules")


def imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_domain_has_no_framework_or_foreign_module_imports() -> None:
    for module in MODULES:
        for path in (SOURCE_ROOT / module / "domain").rglob("*.py"):
            for imported in imported_names(path):
                assert imported.split(".", maxsplit=1)[0] not in FORBIDDEN_DOMAIN_ROOTS
                parts = imported.split(".")
                if len(parts) >= 3 and parts[:2] == ["afishabot", "modules"]:
                    assert parts[2] == module


def test_cross_module_imports_use_public_contracts_only() -> None:
    for owner in MODULES:
        for path in (SOURCE_ROOT / owner).rglob("*.py"):
            for imported in imported_names(path):
                parts = imported.split(".")
                if len(parts) < 4 or parts[:2] != ["afishabot", "modules"]:
                    continue
                foreign = parts[2]
                if foreign != owner:
                    assert foreign in MODULES
                    assert parts[3] == "public"
