import pytest

from afishabot.modules.media.application.image_processing import (
    NormalizedCrop,
    UnsafeImageError,
)


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
