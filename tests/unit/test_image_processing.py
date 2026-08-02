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

    def autorot(self) -> Self:
        return self

    def crop(self, left: int, top: int, width: int, height: int) -> Self:
        del left, top
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
        NormalizedCrop(x=0, y=0, width=1, height=1),
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
        NormalizedCrop(x=0, y=0, width=1, height=0.5625),
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
                NormalizedCrop(x=0, y=0, width=1, height=0.5625),
            )
        assert not source.exists()
    finally:
        FakeVipsImage.fail_save = False
