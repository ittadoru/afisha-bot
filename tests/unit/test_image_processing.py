import sys
from pathlib import Path
from types import ModuleType
from typing import ClassVar, Self

import pytest

from afishabot.modules.media.application.image_processing import (
    AvatarImageProcessor,
    EventImageProcessor,
    ImageLimits,
    NormalizedCrop,
    ProfileBackgroundImageProcessor,
    UnsafeImageError,
)


class FakeVipsImage:
    width: int = 3200
    height: int = 1800
    fail_save: ClassVar[bool] = False
    crop_calls: ClassVar[list[tuple[int, int, int, int]]] = []
    thumbnail_calls: ClassVar[list[tuple[int, dict[str, object]]]] = []
    webpsave_calls: ClassVar[list[dict[str, object]]] = []

    def autorot(self) -> Self:
        return self

    def crop(self, left: int, top: int, width: int, height: int) -> Self:
        self.crop_calls.append((left, top, width, height))
        self.width = width
        self.height = height
        return self

    def thumbnail_image(self, width: int, **kwargs: object) -> Self:
        self.thumbnail_calls.append((width, kwargs))
        self.width = width
        height = kwargs["height"]
        assert isinstance(height, int)
        self.height = height
        return self

    def webpsave(self, filename: str, **kwargs: object) -> None:
        self.webpsave_calls.append(kwargs)
        if self.fail_save:
            raise RuntimeError("encoder failed")
        Path(filename).write_bytes(b"webp")


class FakeImageFactory:
    width: ClassVar[int] = 3200
    height: ClassVar[int] = 1800

    @classmethod
    def new_from_file(cls, filename: str, **kwargs: object) -> FakeVipsImage:
        del filename, kwargs
        image = FakeVipsImage()
        image.width = cls.width
        image.height = cls.height
        return image


def install_fake_pyvips(monkeypatch: pytest.MonkeyPatch) -> None:
    module = ModuleType("pyvips")
    module.Image = FakeImageFactory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyvips", module)


def test_normalized_crop_accepts_4_by_3() -> None:
    NormalizedCrop(x=0, y=0.1, width=1, height=0.75).validate()


@pytest.mark.parametrize(
    "crop",
    [
        NormalizedCrop(x=-0.1, y=0, width=1, height=0.75),
        NormalizedCrop(x=0.5, y=0, width=0.6, height=0.45),
    ],
)
def test_normalized_crop_rejects_unsafe_values(crop: NormalizedCrop) -> None:
    with pytest.raises(UnsafeImageError):
        crop.validate()


def test_image_processor_creates_safe_derivative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_pyvips(monkeypatch)
    source = tmp_path / "quarantine" / "source.jpg"
    destination = tmp_path / "public" / "event.webp"
    source.parent.mkdir()
    source.write_bytes(b"image")

    result = EventImageProcessor().process(
        source,
        destination,
        NormalizedCrop(x=0, y=0, width=0.75, height=1),
    )

    assert result == destination
    assert destination.read_bytes() == b"webp"
    assert not source.exists()


def test_avatar_processor_always_creates_256_and_64_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_pyvips(monkeypatch)
    source = tmp_path / "quarantine" / "avatar.jpg"
    destination = tmp_path / "avatars" / "avatar.webp"
    thumbnail = tmp_path / "avatars" / "avatar.64.webp"
    source.parent.mkdir()
    source.write_bytes(b"image")

    result = AvatarImageProcessor().process_variants(
        source, destination, thumbnail
    )

    assert result == (destination, thumbnail)
    assert destination.read_bytes() == b"webp"
    assert thumbnail.read_bytes() == b"webp"
    assert not source.exists()


def test_image_processor_rejects_oversized_file(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    source.write_bytes(b"too large")
    processor = EventImageProcessor(ImageLimits(max_file_bytes=2))

    with pytest.raises(UnsafeImageError, match="file_too_large"):
        processor.process(
            source,
            tmp_path / "event.webp",
            NormalizedCrop(x=0, y=0, width=1, height=0.75),
        )


def test_image_processor_rejects_invalid_dimensions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_pyvips(monkeypatch)
    FakeImageFactory.width = 0
    source = tmp_path / "source.jpg"
    source.write_bytes(b"image")
    try:
        with pytest.raises(UnsafeImageError, match="invalid_dimensions"):
            EventImageProcessor().process(
                source,
                tmp_path / "event.webp",
                NormalizedCrop(x=0, y=0, width=1, height=0.75),
            )
    finally:
        FakeImageFactory.width = 3200


def test_image_processor_wraps_encoder_failure_and_cleans_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_pyvips(monkeypatch)
    FakeVipsImage.fail_save = True
    source = tmp_path / "source.jpg"
    source.write_bytes(b"image")
    try:
        with pytest.raises(UnsafeImageError, match="image_decode_or_encode_failed"):
            EventImageProcessor().process(
                source,
                tmp_path / "event.webp",
                NormalizedCrop(x=0, y=0, width=0.75, height=1),
            )
        assert not source.exists()
    finally:
        FakeVipsImage.fail_save = False


def test_image_processor_accepts_4_by_3_crop_on_square_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 4:3 box on a non-4:3 photo (e.g. square) must not be rejected."""

    class NonFourThreeFactory(FakeImageFactory):
        @classmethod
        def new_from_file(cls, filename: str, **kwargs: object) -> FakeVipsImage:
            del filename, kwargs
            image = FakeVipsImage()
            image.width = 1200
            image.height = 1200
            return image

    module = ModuleType("pyvips")
    module.Image = NonFourThreeFactory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyvips", module)
    FakeVipsImage.crop_calls = []

    source = tmp_path / "square.jpg"
    source.write_bytes(b"image")
    EventImageProcessor().process(
        source,
        tmp_path / "event.webp",
        NormalizedCrop(x=0, y=0.1, width=1, height=0.75),
    )

    left, top, width, height = FakeVipsImage.crop_calls[0]
    assert (left, top) == (0, 120)
    assert (width, height) == (1200, 900)
    FakeVipsImage.crop_calls = []


def test_image_processor_rejects_non_4_by_3_box_on_4_by_3_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class NonFourThreeFactory(FakeImageFactory):
        @classmethod
        def new_from_file(cls, filename: str, **kwargs: object) -> FakeVipsImage:
            del filename, kwargs
            image = FakeVipsImage()
            image.width = 1200
            image.height = 900
            return image

    module = ModuleType("pyvips")
    module.Image = NonFourThreeFactory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyvips", module)

    source = tmp_path / "landscape.jpg"
    source.write_bytes(b"image")
    with pytest.raises(UnsafeImageError, match="crop_must_be_4_3"):
        EventImageProcessor().process(
            source,
            tmp_path / "event.webp",
            NormalizedCrop(x=0, y=0, width=0.75, height=0.5),
        )


def test_image_processor_auto_crops_wide_photo_to_4_by_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without an explicit crop the processor takes a centered horizontal 4:3 frame."""

    install_fake_pyvips(monkeypatch)
    FakeVipsImage.crop_calls = []

    source = tmp_path / "wide.jpg"
    source.write_bytes(b"image")
    EventImageProcessor().process(source, tmp_path / "event.webp")

    left, top, width, height = FakeVipsImage.crop_calls[0]
    assert (left, top) == (400, 0)
    assert (width, height) == (2400, 1800)
    FakeVipsImage.crop_calls = []


def test_image_processor_auto_crop_reduces_to_full_width_on_portrait_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tall source keeps its full width; only height is trimmed to keep 4:3."""

    class TallFactory(FakeImageFactory):
        @classmethod
        def new_from_file(cls, filename: str, **kwargs: object) -> FakeVipsImage:
            del filename, kwargs
            image = FakeVipsImage()
            image.width = 900
            image.height = 2400
            return image

    module = ModuleType("pyvips")
    module.Image = TallFactory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyvips", module)
    FakeVipsImage.crop_calls = []

    source = tmp_path / "tall.jpg"
    source.write_bytes(b"image")
    EventImageProcessor().process(source, tmp_path / "event.webp")

    left, top, width, height = FakeVipsImage.crop_calls[0]
    assert (left, top) == (0, 862)
    assert (width, height) == (900, 675)
    FakeVipsImage.crop_calls = []


def test_image_processor_accepts_rotated_portrait_photo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A phone portrait photo (EXIF orientation) is measured after autorot."""

    class RotatingImage(FakeVipsImage):
        rotated: ClassVar[bool] = False

        def autorot(self) -> Self:
            self.width, self.height = self.height, self.width
            RotatingImage.rotated = True
            return self

    class RotatingFactory(FakeImageFactory):
        @classmethod
        def new_from_file(cls, filename: str, **kwargs: object) -> RotatingImage:
            del filename, kwargs
            image = RotatingImage()
            image.width = 1800
            image.height = 3200
            return image

    module = ModuleType("pyvips")
    module.Image = RotatingFactory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyvips", module)
    FakeVipsImage.crop_calls = []

    source = tmp_path / "portrait.jpg"
    source.write_bytes(b"image")
    EventImageProcessor().process(
        source,
        tmp_path / "event.webp",
        NormalizedCrop(x=0.21875, y=0.125, width=0.5625, height=0.75),
    )

    assert RotatingImage.rotated
    left, top, width, height = FakeVipsImage.crop_calls[0]
    assert left >= 0 and top >= 0
    assert left + width <= 3200
    assert top + height <= 1800
    assert abs((width / height) - (4 / 3)) < 0.001
    FakeVipsImage.crop_calls = []


@pytest.mark.parametrize(
    ("source_width", "source_height", "expected_crop"),
    [
        (3200, 1800, (0, 0, 3200, 1800)),
        (1800, 1800, (0, 394, 1800, 1012)),
        (900, 2400, (0, 947, 900, 506)),
    ],
)
def test_profile_background_processor_center_crops_to_16_by_9(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_width: int,
    source_height: int,
    expected_crop: tuple[int, int, int, int],
) -> None:
    install_fake_pyvips(monkeypatch)
    FakeImageFactory.width = source_width
    FakeImageFactory.height = source_height
    FakeVipsImage.crop_calls = []
    FakeVipsImage.thumbnail_calls = []
    FakeVipsImage.webpsave_calls = []
    source = tmp_path / "background.jpg"
    destination = tmp_path / "background.webp"
    source.write_bytes(b"image")
    try:
        ProfileBackgroundImageProcessor().process(source, destination)
        assert FakeVipsImage.crop_calls[0] == expected_crop
        assert FakeVipsImage.thumbnail_calls == [
            (1280, {"height": 720, "size": "force", "crop": "centre"})
        ]
        assert FakeVipsImage.webpsave_calls == [
            {"Q": 82, "effort": 5, "strip": True}
        ]
        assert destination.read_bytes() == b"webp"
        assert not source.exists()
    finally:
        FakeImageFactory.width = 3200
        FakeImageFactory.height = 1800
        FakeVipsImage.crop_calls = []
        FakeVipsImage.thumbnail_calls = []
        FakeVipsImage.webpsave_calls = []


def test_profile_background_processor_rejects_pixel_bomb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_fake_pyvips(monkeypatch)
    FakeImageFactory.width = 10_000
    FakeImageFactory.height = 10_000
    source = tmp_path / "background.png"
    source.write_bytes(b"image")
    try:
        with pytest.raises(UnsafeImageError, match="too_many_pixels"):
            ProfileBackgroundImageProcessor().process(
                source, tmp_path / "background.webp"
            )
        assert not source.exists()
    finally:
        FakeImageFactory.width = 3200
        FakeImageFactory.height = 1800
