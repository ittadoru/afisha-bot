# ruff: noqa: RUF001 -- Russian catalog values are intentional.

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from afishabot.modules.discovery.public.service_area import SERVICE_AREA_RADIUS_METERS

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "accounts": {"users", "telegram_identities", "profiles", "sessions"},
    "communication": {"messages", "notifications", "chat_message_requests"},
    "discovery": {"cities", "categories", "street_anchors"},
    "events": {
        "events",
        "event_photos",
        "event_revisions",
        "participation_episodes",
        "event_interests",
        "waitlist_entries",
        "creation_requests",
        "staff_creation_requests",
        "change_requests",
    },
    "media": {"assets"},
    "trust_safety": {
        "event_reviews",
        "profile_reports",
        "staff_accounts",
        "staff_credentials",
        "staff_sessions",
        "staff_login_limits",
        "staff_permissions",
        "staff_audit_log",
    },
    "reputation": {"organizer_profiles"},
}


def required_database_url() -> str:
    value = os.environ.get("AFISHA_DATABASE_URL")
    if value is None:
        pytest.skip("AFISHA_DATABASE_URL is provided only by the VPS gate")
    return value


async def test_foundation_tables_exist_in_their_owner_schemas() -> None:
    engine = create_async_engine(required_database_url())
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                text(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_schema = ANY(:schemas)
                    """
                ),
                {"schemas": list(EXPECTED_TABLES)},
            )
        actual = {(row.table_schema, row.table_name) for row in rows}
        for schema, tables in EXPECTED_TABLES.items():
            assert {(schema, table) for table in tables} <= actual
    finally:
        await engine.dispose()


async def test_initial_cities_and_categories_are_seeded() -> None:
    engine = create_async_engine(required_database_url())
    try:
        async with engine.connect() as connection:
            cities = await connection.execute(
                text(
                    """
                    SELECT name, boundary IS NOT NULL AS has_boundary,
                           boundary_source
                    FROM discovery.cities
                    ORDER BY name
                    """
                )
            )
            categories = await connection.execute(
                text(
                    """
                    SELECT name, is_special, organizer_selectable
                    FROM discovery.categories
                    ORDER BY sort_order
                    """
                )
            )
        city_rows = list(cities)
        assert {row.name for row in city_rows} == {
            "Дербент",
            "Махачкала",
            "Хасавюрт",
        }
        assert all(row.has_boundary for row in city_rows)
        assert all(row.boundary_source.startswith("osm:relation:") for row in city_rows)
        category_rows = list(categories)
        assert len(category_rows) == 16
        assert tuple(category_rows[0]) == ("Особое", True, False)
    finally:
        await engine.dispose()


async def test_known_city_points_are_inside_managed_boundaries() -> None:
    engine = create_async_engine(required_database_url())
    try:
        async with engine.connect() as connection:
            covered = await connection.scalar(
                text(
                    """
                    WITH expected(slug, longitude, latitude) AS (
                        VALUES
                            ('makhachkala', 47.5047, 42.9831),
                            ('khasavyurt', 46.5850, 43.2500),
                            ('derbent', 48.2890, 42.0570)
                    )
                    SELECT count(*)
                    FROM expected
                    JOIN discovery.cities USING (slug)
                    WHERE ST_Covers(
                        boundary::geometry,
                        ST_SetSRID(ST_Point(longitude, latitude), 4326)
                    )
                    """
                )
            )
        assert covered == 3
    finally:
        await engine.dispose()


async def test_supported_cities_allow_points_within_the_service_radius() -> None:
    engine = create_async_engine(required_database_url())
    try:
        async with engine.connect() as connection:
            allowed = await connection.scalar(
                text(
                    """
                    SELECT count(*)
                    FROM discovery.cities
                    WHERE is_active
                      AND ST_DWithin(
                        boundary,
                        ST_Project(
                            ST_PointOnSurface(boundary::geometry)::geography,
                            15_000,
                            0
                        ),
                        :radius_meters
                      )
                    """
                ),
                {"radius_meters": SERVICE_AREA_RADIUS_METERS},
            )
        assert allowed == 3
    finally:
        await engine.dispose()
