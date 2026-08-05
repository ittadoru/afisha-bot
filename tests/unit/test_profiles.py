import pytest

from afishabot.modules.accounts.application.profiles import ProfileError, normalize_bio, normalize_display_name


def test_display_name_normalizes_spaces_and_allows_duplicate_safe_characters() -> None:
    assert normalize_display_name("  Али  2026_год ") == "Али 2026_год"


@pytest.mark.parametrize("value", ["ab", "имя🙂", "https-user", "www user"])
def test_display_name_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ProfileError):
        normalize_display_name(value)


def test_bio_is_trimmed_and_limited() -> None:
    assert normalize_bio("  О себе  ") == "О себе"
    with pytest.raises(ProfileError):
        normalize_bio("x" * 151)
