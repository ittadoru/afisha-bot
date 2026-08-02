from dataclasses import dataclass
from uuid import UUID, uuid4

import factory
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


class UserFactory(factory.Factory):
    class Meta:
        model = UserFixture

    user_id = factory.LazyFunction(uuid4)
    pseudonym = factory.LazyFunction(lambda: fake.user_name()[:24])


class EventFactory(factory.Factory):
    class Meta:
        model = EventFixture

    event_id = factory.LazyFunction(uuid4)
    owner_id = factory.LazyFunction(uuid4)
    title = factory.LazyFunction(lambda: fake.sentence(nb_words=4)[:60])
    city = "Махачкала"
