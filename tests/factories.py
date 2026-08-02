from dataclasses import dataclass
from uuid import UUID, uuid4

from factory.base import Factory
from factory.declarations import LazyFunction
from faker import Faker

fake = Faker("ru_RU")
Faker.seed(20260801)


@dataclass(frozen=True, slots=True)
class UserFixture:
    user_id: UUID
    pseudonym: str


@dataclass(frozen=True, slots=True)
class EventFixture:
    event_id: UUID
    owner_id: UUID
    title: str
    city: str


class UserFactory(Factory[UserFixture]):
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = UserFixture

    user_id = LazyFunction(uuid4)
    pseudonym = LazyFunction(lambda: fake.user_name()[:24])


class EventFactory(Factory[EventFixture]):
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = EventFixture

    event_id = LazyFunction(uuid4)
    owner_id = LazyFunction(uuid4)
    title = LazyFunction(lambda: fake.sentence(nb_words=4)[:60])
    city = "Махачкала"
