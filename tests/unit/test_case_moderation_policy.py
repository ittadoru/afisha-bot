from afishabot.modules.trust_safety.application.case_moderation import _direction


def test_profile_components_have_independent_policy_directions() -> None:
    assert _direction("avatar") == "profile_media"
    assert _direction("background") == "profile_media"
    assert _direction("display_name") == "profile_text"
    assert _direction("bio") == "profile_text"
    assert _direction(None) is None


def test_staff_moderation_migration_contains_required_safety_guards() -> None:
    source = open(
        "migrations/versions/0034_staff_case_moderation.py", encoding="utf-8"
    ).read()
    assert "case_decisions" in source
    assert "idempotency_key uuid NOT NULL UNIQUE" in source
    assert "profile_violations" in source
    assert "profile_restrictions" in source
    assert "180 days" not in source  # policy window belongs to application logic
