"""Create cities and the managed category catalog."""

# ruff: noqa: E501 -- catalog rows stay one-per-line for safe review.

from collections.abc import Sequence

from alembic import op

revision: str = "0010_discovery_foundation"
down_revision: str | None = "0009_accounts_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE discovery.cities (
            id uuid PRIMARY KEY,
            slug varchar(64) NOT NULL UNIQUE,
            name varchar(100) NOT NULL,
            timezone varchar(64) NOT NULL,
            boundary geography(MultiPolygon, 4326),
            is_active boolean NOT NULL DEFAULT false,
            low_activity_cleanup_enabled boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        );
        CREATE INDEX ix_discovery_cities_boundary
            ON discovery.cities USING gist(boundary);

        CREATE TABLE discovery.categories (
            id uuid PRIMARY KEY,
            slug varchar(64) NOT NULL UNIQUE,
            name varchar(64) NOT NULL UNIQUE,
            sort_order smallint NOT NULL UNIQUE CHECK (sort_order > 0),
            is_special boolean NOT NULL DEFAULT false,
            organizer_selectable boolean NOT NULL DEFAULT true,
            is_active boolean NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK (NOT is_special OR NOT organizer_selectable)
        );

        INSERT INTO discovery.cities
            (id, slug, name, timezone, is_active)
        VALUES
            ('10000000-0000-4000-8000-000000000001', 'makhachkala', 'Махачкала', 'Europe/Moscow', true),
            ('10000000-0000-4000-8000-000000000002', 'khasavyurt', 'Хасавюрт', 'Europe/Moscow', true),
            ('10000000-0000-4000-8000-000000000003', 'derbent', 'Дербент', 'Europe/Moscow', true);

        INSERT INTO discovery.categories
            (id, slug, name, sort_order, is_special, organizer_selectable)
        VALUES
            ('20000000-0000-4000-8000-000000000001', 'special', 'Особое', 1, true, false),
            ('20000000-0000-4000-8000-000000000002', 'sport', 'Спорт', 2, false, true),
            ('20000000-0000-4000-8000-000000000003', 'games', 'Игры', 3, false, true),
            ('20000000-0000-4000-8000-000000000004', 'meetups', 'Сходки', 4, false, true),
            ('20000000-0000-4000-8000-000000000005', 'cinema', 'Кино', 5, false, true),
            ('20000000-0000-4000-8000-000000000006', 'cafe', 'Кафе', 6, false, true),
            ('20000000-0000-4000-8000-000000000007', 'tourism', 'Туризм', 7, false, true),
            ('20000000-0000-4000-8000-000000000008', 'education', 'Обучение', 8, false, true),
            ('20000000-0000-4000-8000-000000000009', 'creativity', 'Творчество', 9, false, true),
            ('20000000-0000-4000-8000-000000000010', 'cars', 'Автомобили', 10, false, true),
            ('20000000-0000-4000-8000-000000000011', 'volunteering', 'Волонтёрство', 11, false, true),
            ('20000000-0000-4000-8000-000000000012', 'work', 'Работа', 12, false, true),
            ('20000000-0000-4000-8000-000000000013', 'entertainment', 'Развлечения', 13, false, true),
            ('20000000-0000-4000-8000-000000000014', 'music', 'Музыка', 14, false, true),
            ('20000000-0000-4000-8000-000000000015', 'walks', 'Прогулки', 15, false, true),
            ('20000000-0000-4000-8000-000000000016', 'other', 'Другое', 16, false, true);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE discovery.categories")
    op.execute("DROP TABLE discovery.cities")
