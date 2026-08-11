from pathlib import Path
from typing import Any

import pytest

from afishabot.adapters.http.profiles import _avatar_path
from afishabot.modules.accounts.application.profiles import (
    ProfileError,
    normalize_bio,
    normalize_display_name,
)


class _AvatarResult:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row

    def mappings(self) -> "_AvatarResult":
        return self

    def one_or_none(self) -> dict[str, Any]:
        return self.row


class _AvatarConnection:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row

    async def execute(self, *_args: Any, **_kwargs: Any) -> _AvatarResult:
        return _AvatarResult(self.row)


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


@pytest.mark.asyncio
async def test_avatar_path_falls_back_when_thumbnail_row_points_to_missing_file(
    tmp_path: Path,
) -> None:
    source = tmp_path / "avatars" / "source.webp"
    source.parent.mkdir()
    source.write_bytes(b"RIFF\x04\x00\x00\x00WEBPsource")
    connection = _AvatarConnection(
        {
            "source_key": "avatars/source.webp",
            "source_size": source.stat().st_size,
            "source_checksum": None,
            "variant_key": "avatars/missing.64.webp",
            "variant_size": 123,
            "variant_checksum": None,
        }
    )

    resolved = await _avatar_path(  # type: ignore[arg-type]
        connection,
        public_id="12345678",
        size=64,
        media_root=tmp_path,
    )

    assert resolved == source
