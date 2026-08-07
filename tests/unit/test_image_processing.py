import sys
from pathlib import Path
from types import ModuleType
from typing import ClassVar, Self

import pytest

from afishabot.modules.media.application.image_processing import (
    EventImageProcessor,
    ImageLimits,
    NormalizedCrop,
    UnsafeImageError,
)


class FakeVipsImage:
    width: int = 3200
    height: int = 1800
    fail_save: ClassVar[bool] = False
    crop_calls: ClassVar[list[tuple[int, int, int, int]]] = []

    def autorot(self) -> Self:
        return self

    def crop(self, left: int, top: int, width: int, height: int) -> Self:
        self.crop_calls.append((left, top, width, height))
        self.width = width
        self.height = height
        return self

    def thumbnail_image(self, width: int, **kwargs: object) -> Self:
        self.width = width
        height = kwargs["height"]
        assert isinstance(height, int)
        self.height = height
        return self

    def webpsave(self, filename: str, **kwargs: object) -> None:
        del kwargs
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


def test_normalized_crop_accepts_16_by_9() -> None:
    NormalizedCrop(x=0, y=0.1, width=1, height=0.5625).validate()


@pytest.mark.parametrize(
    "crop",
    [
        NormalizedCrop(x=-0.1, y=0, width=1, height=0.5625),
        NormalizedCrop(x=0.5, y=0, width=0.6, height=0.3375),
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
        NormalizedCrop(x=0, y=0, width=1, height=1),
    )

    assert result == destination
    assert destination.read_bytes() == b"webp"
    assert not source.exists()


def test_image_processor_rejects_oversized_file(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    source.write_bytes(b"too large")
    processor = EventImageProcessor(ImageLimits(max_file_bytes=2))

    with pytest.raises(UnsafeImageError, match="file_too_large"):
        processor.process(
            source,
            tmp_path / "event.webp",
            NormalizedCrop(x=0, y=0, width=1, height=0.5625),
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
                NormalizedCrop(x=0, y=0, width=1, height=0.5625),
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
                NormalizedCrop(x=0, y=0, width=1, height=1),
            )
        assert not source.exists()
    finally:
        FakeVipsImage.fail_save = False


def test_image_processor_accepts_16_by_9_crop_on_4_by_3_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 16:9 box on a non-16:9 photo (e.g. 4:3) must not be rejected."""

    class NonSixteenNineFactory(FakeImageFactory):
        @classmethod
        def new_from_file(cls, filename: str, **kwargs: object) -> FakeVipsImage:
            del filename, kwargs
            image = FakeVipsImage()
            image.width = 1200
            image.height = 900
            return image

    module = ModuleType("pyvips")
    module.Image = NonSixteenNineFactory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyvips", module)
    FakeVipsImage.crop_calls = []

    source = tmp_path / "landscape.jpg"
    source.write_bytes(b"image")
    EventImageProcessor().process(
        source,
        tmp_path / "event.webp",
        NormalizedCrop(x=0.1, y=0.2, width=0.8, height=0.6),
    )

    left, top, width, height = FakeVipsImage.crop_calls[0]
    assert (left, top) == (120, 180)
    assert (width, height) == (960, 540)
    FakeVipsImage.crop_calls = []


def test_image_processor_rejects_non_16_by_9_box_on_4_by_3_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class NonSixteenNineFactory(FakeImageFactory):
        @classmethod
        def new_from_file(cls, filename: str, **kwargs: object) -> FakeVipsImage:
            del filename, kwargs
            image = FakeVipsImage()
            image.width = 1200
            image.height = 900
            return image

    module = ModuleType("pyvips")
    module.Image = NonSixteenNineFactory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyvips", module)

    source = tmp_path / "landscape.jpg"
    source.write_bytes(b"image")
    with pytest.raises(UnsafeImageError, match="crop_must_be_16_9"):
        EventImageProcessor().process(
            source,
            tmp_path / "event.webp",
            NormalizedCrop(x=0, y=0, width=1, height=1),
        )


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
        NormalizedCrop(x=0.25, y=0.25, width=0.5, height=0.5),
    )

    assert RotatingImage.rotated
    left, top, width, height = FakeVipsImage.crop_calls[0]
    assert left >= 0 and top >= 0
    assert left + width <= 3200
    assert top + height <= 1800
    assert abs((width / height) - (16 / 9)) < 0.001
    FakeVipsImage.crop_calls = []
