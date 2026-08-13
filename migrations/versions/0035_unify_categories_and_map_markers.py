"""Reduce user categories and normalize category presentation."""
# ruff: noqa: RUF001 -- Russian catalog values are intentional.

from collections.abc import Sequence

from alembic import op

revision: str = "0035_unify_categories_and_map_markers"
down_revision: str | None = "0034_staff_case_moderation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _execute_statements(sql: str) -> None:
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    _execute_statements(
        """
        -- sort_order is unique, so free the target range before assigning 1..9.
        UPDATE discovery.categories SET sort_order = sort_order + 100;

        UPDATE events.events AS event SET category_id = target.id
        FROM discovery.categories AS source
        JOIN discovery.categories AS target ON target.slug = CASE source.slug
          WHEN 'cafe' THEN 'meetups' WHEN 'entertainment' THEN 'meetups'
          WHEN 'walks' THEN 'tourism' WHEN 'work' THEN 'education' END
        WHERE event.category_id = source.id
          AND source.slug IN ('cafe','entertainment','walks','work');

        UPDATE discovery.looking_posts AS post SET category_id = target.id
        FROM discovery.categories AS source
        JOIN discovery.categories AS target ON target.slug = CASE source.slug
          WHEN 'cafe' THEN 'meetups' WHEN 'entertainment' THEN 'meetups'
          WHEN 'walks' THEN 'tourism' WHEN 'work' THEN 'education' END
        WHERE post.category_id = source.id
          AND source.slug IN ('cafe','entertainment','walks','work');

        UPDATE discovery.categories SET name = values.name, icon_key = values.icon_key,
          color_key = values.color_key, sort_order = values.sort_order,
          is_active = true, organizer_selectable = true
        FROM (VALUES
          ('sport', 'Спорт', 'dumbbell', 'red', 1),
          ('games', 'Игры', 'gamepad', 'violet', 2),
          ('meetups', 'Встречи', 'users', 'orange', 3),
          ('tourism', 'Прогулки и поездки', 'mountain', 'teal', 4),
          ('education', 'Обучение и работа', 'graduation-cap', 'blue', 5),
          ('creativity', 'Творчество', 'palette', 'magenta', 6),
          ('cars', 'Автомобили', 'car', 'slate-blue', 7),
          ('volunteering', 'Волонтёрство', 'hand-heart', 'emerald', 8),
          ('other', 'Другое', 'shapes', 'graphite', 9)
        ) AS values(slug, name, icon_key, color_key, sort_order)
        WHERE discovery.categories.slug = values.slug;

        UPDATE discovery.categories SET is_active = false, organizer_selectable = false
        WHERE slug IN ('cafe','entertainment','walks','work');
        """
    )


def downgrade() -> None:
    # Upgrade intentionally collapses historical references. A backup is required
    # for a lossless data rollback; this restores only the catalog presentation.
    _execute_statements(
        """
        UPDATE discovery.categories SET sort_order = sort_order + 100;

        UPDATE discovery.categories SET name = values.name, icon_key = values.icon_key,
          color_key = values.color_key, sort_order = values.sort_order,
          is_active = values.is_active,
          organizer_selectable = values.organizer_selectable
        FROM (VALUES
          ('special', 'Особое', 'shapes', 'gray', 1, false, false),
          ('sport', 'Спорт', 'dumbbell', 'emerald', 2, true, true),
          ('games', 'Игры', 'gamepad', 'violet', 3, true, true),
          ('meetups', 'Сходки', 'users', 'blue', 4, true, true),
          ('cinema', 'Кино', 'shapes', 'gray', 5, false, false),
          ('cafe', 'Кафе', 'coffee', 'amber', 6, true, true),
          ('tourism', 'Туризм', 'mountain', 'teal', 7, true, true),
          ('education', 'Обучение', 'graduation-cap', 'indigo', 8, true, true),
          ('creativity', 'Творчество', 'palette', 'rose', 9, true, true),
          ('cars', 'Автомобили', 'car', 'slate-blue', 10, true, true),
          ('volunteering', 'Волонтёрство', 'hand-heart', 'cyan', 11, true, true),
          ('work', 'Работа', 'briefcase', 'brown', 12, true, true),
          ('entertainment', 'Развлечения', 'party-popper', 'orange', 13, true, true),
          ('music', 'Музыка', 'shapes', 'gray', 14, false, false),
          ('walks', 'Прогулки', 'footprints', 'moss', 15, true, true),
          ('other', 'Другое', 'shapes', 'gray', 16, true, true)
        ) AS values(
          slug, name, icon_key, color_key, sort_order,
          is_active, organizer_selectable
        )
        WHERE discovery.categories.slug = values.slug;
        """
    )
