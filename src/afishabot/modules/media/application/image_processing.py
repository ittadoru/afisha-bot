import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Self, cast
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


@dataclass(frozen=True, slots=True)
class ImageLimits:
    max_file_bytes: int = 12 * 1024 * 1024
    max_pixels: int = 40_000_000
    output_width: int = 1200
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

    def process(
        self, source: Path, destination: Path, crop: NormalizedCrop | None = None
    ) -> Path:
        self.process_variants(source, destination, None, None, crop)
        return destination

    def process_variants(
        self,
        source: Path,
        destination_1200: Path,
        destination_640: Path | None,
        destination_320: Path | None,
        crop: NormalizedCrop | None = None,
    ) -> tuple[Path, Path | None, Path | None]:
        if crop is not None:
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
            if crop is None:
                width = min(image.width, round(image.height * 4 / 3))
                height = round(width * 3 / 4)
                left = (image.width - width) // 2
                top = (image.height - height) // 2
            else:
                left = round(crop.x * image.width)
                top = round(crop.y * image.height)
                width = min(round(crop.width * image.width), image.width - left)
                height = min(round(crop.height * image.height), image.height - top)
                if width <= 0 or height <= 0:
                    raise UnsafeImageError("crop_is_empty")
                if abs((width / height) - (4 / 3)) > 0.03:
                    raise UnsafeImageError("crop_must_be_4_3")
            image = image.crop(left, top, width, height)
            image = image.thumbnail_image(
                self._limits.output_width,
                height=self._limits.output_height,
                size="force",
                crop="centre",
            )

            outputs = ((destination_1200, image, 82),)
            if destination_640 is not None:
                outputs += (
                    (
                        destination_640,
                        image.thumbnail_image(640, height=480, size="force"),
                        80,
                    ),
                )
            if destination_320 is not None:
                outputs += (
                    (
                        destination_320,
                        image.thumbnail_image(320, height=240, size="force"),
                        76,
                    ),
                )
            for destination, variant, quality in outputs:
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_name(
                    f".{destination.name}.{uuid4().hex}.tmp"
                )
                try:
                    variant.webpsave(str(temporary), Q=quality, effort=5, strip=True)
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
            if destination_640 is not None or destination_320 is not None:
                validate_webp_variant(destination_1200, width=1200, height=900)
                if destination_640 is not None:
                    validate_webp_variant(destination_640, width=640, height=480)
                if destination_320 is not None:
                    validate_webp_variant(destination_320, width=320, height=240)
        except UnsafeImageError:
            raise
        except Exception as exc:
            raise UnsafeImageError("image_decode_or_encode_failed") from exc
        finally:
            source.unlink(missing_ok=True)
        return destination_1200, destination_640, destination_320


class AvatarImageProcessor:
    """Create a metadata-free square WebP avatar from a client-selected crop."""

    def process(self, source: Path, destination: Path) -> Path:
        self.process_variants(source, destination, None)
        return destination

    def process_variants(
        self, source: Path, destination_256: Path, destination_64: Path | None
    ) -> tuple[Path, Path | None]:
        limits = ImageLimits(
            max_file_bytes=12 * 1024 * 1024,
            max_pixels=20_000_000,
            output_width=256,
            output_height=256,
        )
        if (
            not source.is_file()
            or source.is_symlink()
            or source.stat().st_size > limits.max_file_bytes
        ):
            source.unlink(missing_ok=True)
            raise UnsafeImageError("file_too_large")
        destinations = [destination_256]
        if destination_64 is not None:
            destinations.append(destination_64)
        try:
            import pyvips

            image = cast(
                VipsImage,
                pyvips.Image.new_from_file(  # pyright: ignore[reportUnknownMemberType]
                    str(source), access="sequential", fail_on="warning"
                ),
            )
            if (
                image.width <= 0
                or image.height <= 0
                or image.width * image.height > limits.max_pixels
            ):
                raise UnsafeImageError("invalid_dimensions")
            image = image.autorot()
            side = min(image.width, image.height)
            image = image.crop(
                (image.width - side) // 2, (image.height - side) // 2, side, side
            )
            image = image.thumbnail_image(256, height=256, size="force", crop="centre")
            outputs = ((destination_256, 256, 84),)
            if destination_64 is not None:
                outputs += ((destination_64, 64, 74),)
            for destination, size, quality in outputs:
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_name(
                    f".{destination.name}.{uuid4().hex}.tmp"
                )
                try:
                    variant = (
                        image
                        if size == 256
                        else image.thumbnail_image(
                            size, height=size, size="force", crop="centre"
                        )
                    )
                    variant.webpsave(str(temporary), Q=quality, effort=5, strip=True)
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
            validate_avatar_variant(destination_256, expected_size=256)
            if destination_64 is not None:
                validate_avatar_variant(destination_64, expected_size=64)
        except UnsafeImageError:
            for destination in destinations:
                destination.unlink(missing_ok=True)
            raise
        except Exception as exc:
            for destination in destinations:
                destination.unlink(missing_ok=True)
            raise UnsafeImageError("image_decode_or_encode_failed") from exc
        finally:
            source.unlink(missing_ok=True)
        return destination_256, destination_64


def validate_avatar_variant(path: Path, *, expected_size: int) -> None:
    """Re-open an encoded avatar so a partial/corrupt WebP is never published."""
    if not path.is_file() or path.is_symlink() or path.stat().st_size <= 0:
        raise UnsafeImageError("avatar_variant_missing")
    try:
        import pyvips

        image = cast(
            Any,
            pyvips.Image.new_from_file(  # pyright: ignore[reportUnknownMemberType]
                str(path), access="sequential", fail_on="warning"
            ),
        )
        if image.width != expected_size or image.height != expected_size:
            raise UnsafeImageError("avatar_variant_dimensions_invalid")
    except UnsafeImageError:
        raise
    except Exception as exc:
        raise UnsafeImageError("avatar_variant_invalid") from exc


def validate_webp_variant(path: Path, *, width: int, height: int) -> None:
    """Re-open a generated WebP and verify its exact dimensions."""
    if not path.is_file() or path.is_symlink() or path.stat().st_size <= 0:
        raise UnsafeImageError("image_variant_missing")
    try:
        import pyvips

        image = cast(
            Any,
            pyvips.Image.new_from_file(  # pyright: ignore[reportUnknownMemberType]
                str(path), access="sequential", fail_on="warning"
            ),
        )
        if image.width != width or image.height != height:
            raise UnsafeImageError("image_variant_dimensions_invalid")
    except UnsafeImageError:
        raise
    except Exception as exc:
        raise UnsafeImageError("image_variant_invalid") from exc


class ProfileBackgroundImageProcessor:
    """Create a metadata-free, center-cropped 16:9 WebP profile background."""

    def process(self, source: Path, destination: Path) -> Path:
        self.process_variants(source, destination, None, None)
        return destination

    def process_variants(
        self,
        source: Path,
        destination_1280: Path,
        destination_768: Path | None,
        destination_320: Path | None,
    ) -> tuple[Path, Path | None, Path | None]:
        limits = ImageLimits(
            max_file_bytes=12 * 1024 * 1024,
            max_pixels=40_000_000,
            output_width=1280,
            output_height=720,
        )
        if (
            not source.is_file()
            or source.is_symlink()
            or source.stat().st_size > limits.max_file_bytes
        ):
            source.unlink(missing_ok=True)
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
            if image.width * image.height > limits.max_pixels:
                raise UnsafeImageError("too_many_pixels")
            image = image.autorot()
            width = min(image.width, round(image.height * 16 / 9))
            height = round(width * 9 / 16)
            image = image.crop(
                (image.width - width) // 2,
                (image.height - height) // 2,
                width,
                height,
            )
            image = image.thumbnail_image(
                limits.output_width,
                height=limits.output_height,
                size="force",
                crop="centre",
            )
            outputs = ((destination_1280, image, 82),)
            if destination_768 is not None:
                outputs += (
                    (
                        destination_768,
                        image.thumbnail_image(768, height=432, size="force"),
                        80,
                    ),
                )
            if destination_320 is not None:
                outputs += (
                    (
                        destination_320,
                        image.thumbnail_image(320, height=180, size="force"),
                        76,
                    ),
                )
            for destination, variant, quality in outputs:
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_name(
                    f".{destination.name}.{uuid4().hex}.tmp"
                )
                try:
                    variant.webpsave(str(temporary), Q=quality, effort=5, strip=True)
                    os.replace(temporary, destination)
                finally:
                    temporary.unlink(missing_ok=True)
            if destination_768 is not None or destination_320 is not None:
                validate_webp_variant(destination_1280, width=1280, height=720)
                if destination_768 is not None:
                    validate_webp_variant(destination_768, width=768, height=432)
                if destination_320 is not None:
                    validate_webp_variant(destination_320, width=320, height=180)
        except UnsafeImageError:
            raise
        except Exception as exc:
            raise UnsafeImageError("image_decode_or_encode_failed") from exc
        finally:
            source.unlink(missing_ok=True)
        return destination_1280, destination_768, destination_320
