from afishabot.modules.accounts.infrastructure.metadata import (
    metadata as accounts_metadata,
)
from afishabot.modules.communication.infrastructure.metadata import (
    metadata as communication_metadata,
)
from afishabot.modules.discovery.infrastructure.metadata import (
    metadata as discovery_metadata,
)
from afishabot.modules.events.infrastructure.metadata import metadata as events_metadata
from afishabot.modules.media.infrastructure.metadata import metadata as media_metadata
from afishabot.modules.reputation.infrastructure.metadata import (
    metadata as reputation_metadata,
)
from afishabot.modules.trust_safety.infrastructure.metadata import (
    metadata as trust_safety_metadata,
)


def test_each_module_owns_exactly_one_empty_schema() -> None:
    metadata = [
        accounts_metadata,
        communication_metadata,
        discovery_metadata,
        events_metadata,
        media_metadata,
        reputation_metadata,
        trust_safety_metadata,
    ]

    assert {item.schema for item in metadata} == {
        "accounts",
        "communication",
        "discovery",
        "events",
        "media",
        "reputation",
        "trust_safety",
    }
    assert all(not item.tables for item in metadata)
