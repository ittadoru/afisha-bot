from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from afishabot.adapters.http import profiles as profiles_http
from afishabot.adapters.http.profiles import _avatar_path
from afishabot.modules.accounts.application.profiles import (
    ProfileError,
    normalize_bio,
    normalize_display_name,
)


class _AvatarResult:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row

    def mappings(self) -> _AvatarResult:
        return self

    def one_or_none(self) -> dict[str, Any]:
        return self.row


class _AvatarConnection:
    def __init__(self, row: dict[str, Any]) -> None:
        self.row = row

    async def execute(self, *_args: Any, **_kwargs: Any) -> _AvatarResult:
        return _AvatarResult(self.row)


class _AvatarEngine:
    def connect(self) -> _AvatarEngine:
        return self

    async def __aenter__(self) -> _AvatarEngine:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "expected_private"),
    [
        ("/public/profiles/12345678/avatar", False),
        ("/profiles/12345678/avatar", True),
    ],
)
@pytest.mark.parametrize(
    ("query", "expected_size"), [("", 256), ("?size=64", 64), ("?size=256", 256)]
)
async def test_avatar_http_contract_accepts_supported_query_sizes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    expected_private: bool,
    query: str,
    expected_size: int,
) -> None:
    files = {64: tmp_path / "avatar.64.webp", 256: tmp_path / "avatar.webp"}
    files[64].write_bytes(b"RIFFthumbWEBP")
    files[256].write_bytes(b"RIFFfull-WEBP")
    seen_sizes: list[int] = []

    async def fake_avatar_path(*_args: object, size: int, **_kwargs: object) -> Path:
        seen_sizes.append(size)
        return files[size]

    async def fake_current_user(
        _request: object, token: str | None, _csrf: str | None = None
    ) -> object:
        if token is None:
            raise HTTPException(status_code=401, detail="session_required")
        return uuid4()

    monkeypatch.setattr(profiles_http, "_avatar_path", fake_avatar_path)
    monkeypatch.setattr(profiles_http, "current_user", fake_current_user)
    monkeypatch.setattr(
        profiles_http,
        "dependencies",
        lambda _request: (
            type("Settings", (), {"media_root": tmp_path})(),
            None,
            _AvatarEngine(),
        ),
    )
    app = FastAPI()
    app.include_router(profiles_http.router)
    cookies = {profiles_http.SESSION_COOKIE: "session"} if expected_private else None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        response = await client.get(f"{path}{query}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.content == files[expected_size].read_bytes()
    assert seen_sizes == [expected_size]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path", ["/public/profiles/12345678/avatar", "/profiles/12345678/avatar"]
)
async def test_avatar_http_contract_rejects_unsupported_size(path: str) -> None:
    app = FastAPI()
    app.include_router(profiles_http.router)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"{path}?size=128")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_private_avatar_requires_session() -> None:
    app = FastAPI()
    app.include_router(profiles_http.router)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/profiles/12345678/avatar?size=64")

    assert response.status_code == 401
