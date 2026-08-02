import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Self, cast
from uuid import uuid4


class UnsafeImageError(Exception):
    """The quarantined file cannot safely become a published derivative."""


@dataclass(frozen=True, slots=True)
class NormalizedCrop:
    x: float
    y: float
    width: float
    height: float

    def validate(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if any(value < 0 or value > 1 for value in values):
            raise UnsafeImageError("crop_out_of_bounds")
        if self.width <= 0 or self.height <= 0:
            raise UnsafeImageError("crop_is_empty")
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise UnsafeImageError("crop_out_of_bounds")
        if abs((self.width / self.height) - (16 / 9)) > 0.03:
            raise UnsafeImageError("crop_must_be_16_9")


@dataclass(frozen=True, slots=True)
class ImageLimits:
    max_file_bytes: int = 12 * 1024 * 1024
    max_pixels: int = 40_000_000
    output_width: int = 1600
    output_height: int = 900


class VipsImage(Protocol):
    width: int
    height: int

    def autorot(self) -> Self: ...

    def crop(self, left: int, top: int, width: int, height: int) -> Self: ...

    def thumbnail_image(self, width: int, **kwargs: object) -> Self: ...

    def webpsave(self, filename: str, **kwargs: object) -> None: ...


class EventImageProcessor:
    """Decode, orient, crop and re-encode one quarantined Event image."""

    def __init__(self, limits: ImageLimits | None = None) -> None:
        self._limits = limits or ImageLimits()

    def process(self, source: Path, destination: Path, crop: NormalizedCrop) -> Path:
        crop.validate()
        if not source.is_file() or source.is_symlink():
            raise UnsafeImageError("source_is_not_a_regular_file")
        if source.stat().st_size > self._limits.max_file_bytes:
            raise UnsafeImageError("file_too_large")

        try:
            import pyvips

            image = cast(
                VipsImage,
                pyvips.Image.new_from_file(  # pyright: ignore[reportUnknownMemberType]
                    str(source), access="sequential", fail_on="warning"
                ),
            )
            if image.width <= 0 or image.height <= 0:
                raise UnsafeImageError("invalid_dimensions")
            if image.width * image.height > self._limits.max_pixels:
                raise UnsafeImageError("too_many_pixels")

            image = image.autorot()
            left = round(crop.x * image.width)
            top = round(crop.y * image.height)
            width = min(round(crop.width * image.width), image.width - left)
            height = min(round(crop.height * image.height), image.height - top)
            if width <= 0 or height <= 0:
                raise UnsafeImageError("crop_is_empty")
            image = image.crop(left, top, width, height)
            image = image.thumbnail_image(
                self._limits.output_width,
                height=self._limits.output_height,
                size="force",
                crop="centre",
            )

            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
            try:
                image.webpsave(str(temporary), Q=82, effort=5, strip=True)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        except UnsafeImageError:
            raise
        except Exception as exc:
            raise UnsafeImageError("image_decode_or_encode_failed") from exc
        finally:
            source.unlink(missing_ok=True)
        return destination
