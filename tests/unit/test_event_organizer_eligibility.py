from uuid import uuid4

import pytest

from afishabot.modules.events.application.create_event import (
    EventCreationError,
    _eligible_organizer_status,  # pyright: ignore[reportPrivateUsage]
)


def test_organizer_must_have_selected_city() -> None:
    with pytest.raises(EventCreationError, match="city_selection_required"):
        _eligible_organizer_status("new", None, uuid4())


def test_event_city_must_match_profile_city() -> None:
    with pytest.raises(EventCreationError, match="profile_city_mismatch"):
        _eligible_organizer_status("trusted", uuid4(), uuid4())


@pytest.mark.parametrize("status", [None, "blocked"])
def test_organizer_must_be_eligible(status: str | None) -> None:
    city_id = uuid4()
    with pytest.raises(EventCreationError, match="organizer_not_eligible"):
        _eligible_organizer_status(status, city_id, city_id)


@pytest.mark.parametrize("status", ["new", "trusted"])
def test_eligible_organizer_keeps_status(status: str) -> None:
    city_id = uuid4()
    assert _eligible_organizer_status(status, city_id, city_id) == status
