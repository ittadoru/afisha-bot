"""Backfill privacy-safe OSM street anchors after migration 0022.

This script is intentionally not run by migrations. Run it on the VPS only
after Nominatim is available, then validate the deferred database constraint.
"""

import asyncio

from sqlalchemy import text

from afishabot.core.config import Settings
from afishabot.core.database import create_database_engine
from afishabot.modules.discovery.application.street_anchors import save_street_anchor
from afishabot.modules.discovery.infrastructure.nominatim import NominatimReverseGeocoder


async def main() -> None:
    settings = Settings()
    engine = create_database_engine(settings.database_dsn())
    geocoder = NominatimReverseGeocoder(
        settings.nominatim_url, settings.nominatim_timeout_seconds
    )
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT DISTINCT e.city_id,c.name AS city,r.street_name
                        FROM events.events e
                        JOIN events.event_revisions r ON r.event_id=e.id
                        JOIN discovery.cities c ON c.id=e.city_id
                        WHERE r.address_visibility<>'exact_public'
                          AND r.street_anchor_id IS NULL
                        ORDER BY c.name,r.street_name
                        """
                    )
                )
            ).mappings().all()
        for row in rows:
            candidate = await geocoder.street_anchor(
                street=row["street_name"], city=row["city"], locale="ru"
            )
            anchor_id = await save_street_anchor(
                engine,
                city_id=row["city_id"],
                street=row["street_name"],
                candidate=candidate,
            )
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        UPDATE events.event_revisions r SET street_anchor_id=:anchor
                        FROM events.events e
                        WHERE r.event_id=e.id AND e.city_id=:city
                          AND r.street_name=:street
                          AND r.address_visibility<>'exact_public'
                          AND r.street_anchor_id IS NULL
                        """
                    ),
                    {"anchor": anchor_id, "city": row["city_id"],
                     "street": row["street_name"]},
                )
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "ALTER TABLE events.event_revisions VALIDATE CONSTRAINT "
                    "event_revisions_hidden_anchor_check"
                )
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
