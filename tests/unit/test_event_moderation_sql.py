from pathlib import Path


def test_nullable_moderation_reason_has_an_explicit_postgres_type() -> None:
    """asyncpg cannot infer the type of a NULL value inside jsonb_build_object."""
    source = Path(
        "src/afishabot/modules/trust_safety/application/event_moderation.py"
    ).read_text(encoding="utf-8")

    assert "'reason', CAST(:reason AS text)" in source
    assert "CAST(:revision AS uuid)" in source
