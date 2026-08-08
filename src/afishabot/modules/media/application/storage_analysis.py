"""Bounded, manual-only storage reporting for staff."""

import json
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

MAX_SAMPLE_FILES = 8
MAX_SAMPLE_BYTES = 16 * 1024 * 1024
MAX_SAMPLE_SECONDS = 10.0


async def inventory(engine: AsyncEngine) -> dict[str, Any]:
    async with engine.connect() as connection:
        totals = (
            (
                await connection.execute(
                    text("""
            SELECT count(*) AS file_count, COALESCE(sum(byte_size), 0) AS total_bytes,
                   count(*) FILTER (WHERE state='ready' AND delete_after IS NULL) AS permanent_file_count,
                   COALESCE(sum(byte_size) FILTER (WHERE state='ready' AND delete_after IS NULL), 0) AS permanent_bytes,
                   count(*) FILTER (WHERE delete_after IS NOT NULL) AS temporary_file_count,
                   COALESCE(sum(byte_size) FILTER (WHERE delete_after IS NOT NULL), 0) AS temporary_bytes
            FROM media.assets
        """)
                )
            )
            .mappings()
            .one()
        )
        formats = (
            (
                await connection.execute(
                    text("""
            SELECT COALESCE(mime_type, 'unknown') AS name, count(*) AS file_count,
                   COALESCE(sum(byte_size), 0) AS total_bytes
            FROM media.assets GROUP BY 1 ORDER BY total_bytes DESC, name LIMIT 8
        """)
                )
            )
            .mappings()
            .all()
        )
        purposes = (
            (
                await connection.execute(
                    text("""
            SELECT purpose AS name, count(*) AS file_count, COALESCE(sum(byte_size), 0) AS total_bytes
            FROM media.assets GROUP BY purpose ORDER BY total_bytes DESC, purpose LIMIT 8
        """)
                )
            )
            .mappings()
            .all()
        )
        directories = (
            (
                await connection.execute(
                    text("""
            WITH grouped AS (
              SELECT split_part(storage_key, '/', 1) AS name, count(*) AS file_count,
                     COALESCE(sum(byte_size), 0) AS total_bytes
              FROM media.assets GROUP BY 1 ORDER BY total_bytes DESC, name
            ) SELECT * FROM grouped
        """)
                )
            )
            .mappings()
            .all()
        )
    total = int(totals["total_bytes"])
    top = [dict(row) for row in directories[:8]]
    remainder = directories[8:]
    if remainder:
        top.append(
            {
                "name": "other",
                "file_count": sum(int(row["file_count"]) for row in remainder),
                "total_bytes": sum(int(row["total_bytes"]) for row in remainder),
            }
        )
    return {
        "collected_at": datetime.now(UTC).isoformat(),
        "source": "database",
        **{key: int(value) for key, value in totals.items()},
        "formats": [dict(row) for row in formats],
        "purposes": [dict(row) for row in purposes],
        "directories": [
            {
                **row,
                "percent": round(
                    (int(row["total_bytes"]) / total * 100) if total else 0, 1
                ),
            }
            for row in top
        ],
    }


async def save_inventory(engine: AsyncEngine, value: dict[str, Any]) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("""
            INSERT INTO media.storage_analysis (id, inventory_collected_at, inventory, updated_at)
            VALUES (1, now(), :inventory, now())
            ON CONFLICT (id) DO UPDATE SET inventory_collected_at=EXCLUDED.inventory_collected_at,
              inventory=EXCLUDED.inventory, updated_at=now()
        """),
            {"inventory": json.dumps(value, ensure_ascii=False, separators=(",", ":"))},
        )


async def latest(engine: AsyncEngine) -> dict[str, Any] | None:
    async with engine.connect() as connection:
        row = (
            (
                await connection.execute(
                    text("""
            SELECT inventory, estimate_status, estimate_job_id, estimate_collected_at, estimate
            FROM media.storage_analysis WHERE id=1
        """)
                )
            )
            .mappings()
            .one_or_none()
        )
    if row is None or row["inventory"] is None:
        return None
    result = json.loads(cast(str, row["inventory"]))
    result["estimate_status"] = row["estimate_status"]
    result["estimate_job_id"] = (
        str(row["estimate_job_id"]) if row["estimate_job_id"] else None
    )
    result["estimate_collected_at"] = row["estimate_collected_at"]
    result["estimate"] = (
        json.loads(cast(str, row["estimate"])) if row["estimate"] else None
    )
    return result


async def queue_estimate(engine: AsyncEngine) -> UUID:
    job_id = uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            text("""
            INSERT INTO media.storage_analysis (id, estimate_status, updated_at)
            VALUES (1, 'idle', now()) ON CONFLICT (id) DO NOTHING
        """)
        )
        queued = await connection.scalar(
            text("""
            UPDATE media.storage_analysis SET estimate_status='queued', estimate_job_id=:job,
              estimate=NULL, estimate_collected_at=NULL, updated_at=now()
            WHERE id=1 AND estimate_status NOT IN ('queued','running') RETURNING id
        """),
            {"job": job_id},
        )
    if queued is None:
        raise RuntimeError("estimate_already_running")
    return job_id


def _safe_media_path(root: Path, key: str) -> Path | None:
    relative = Path(key)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    path = root / relative
    return path if path.is_file() and not path.is_symlink() else None


async def estimate_savings(
    engine: AsyncEngine, *, media_root: Path, job_id: UUID
) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("""
            UPDATE media.storage_analysis SET estimate_status='running', updated_at=now()
            WHERE id=1 AND estimate_job_id=:job AND estimate_status='queued'
        """),
            {"job": job_id},
        )
    try:
        async with engine.connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text("""
                SELECT storage_key, byte_size FROM media.assets
                WHERE state='ready' AND delete_after IS NULL AND mime_type='image/webp'
                ORDER BY checksum_sha256 NULLS LAST, id LIMIT 64
            """)
                    )
                )
                .mappings()
                .all()
            )
        started = time.monotonic()
        sampled = 0
        source_bytes = 0
        saved_bytes = 0
        for row in rows:
            if (
                sampled >= MAX_SAMPLE_FILES
                or source_bytes >= MAX_SAMPLE_BYTES
                or time.monotonic() - started >= MAX_SAMPLE_SECONDS
            ):
                break
            path = _safe_media_path(media_root, cast(str, row["storage_key"]))
            size = int(row["byte_size"] or 0)
            if path is None or size <= 0 or source_bytes + size > MAX_SAMPLE_BYTES:
                continue
            try:
                with tempfile.TemporaryDirectory() as temporary_directory:
                    import pyvips

                    temporary = Path(temporary_directory) / "recompressed.webp"
                    image = pyvips.Image.new_from_file(
                        str(path), access="sequential", fail_on="warning"
                    )
                    image.webpsave(str(temporary), Q=78, effort=4, strip=True)
                    candidate = temporary.stat().st_size
                source_bytes += size
                saved_bytes += max(0, size - candidate)
                sampled += 1
            except Exception:
                continue
        async with engine.connect() as connection:
            eligible = await connection.scalar(
                text("""
                SELECT COALESCE(sum(byte_size), 0) FROM media.assets
                WHERE state='ready' AND delete_after IS NULL AND mime_type='image/webp'
            """)
            )
        percent = (saved_bytes / source_bytes) if source_bytes else 0.0
        result = {
            "quality": 78,
            "sample_file_count": sampled,
            "sample_bytes": source_bytes,
            "sample_saved_bytes": saved_bytes,
            "sample_saved_percent": round(percent * 100, 1),
            "eligible_bytes": int(eligible or 0),
            "estimated_saved_bytes": round(int(eligible or 0) * percent),
        }
        async with engine.begin() as connection:
            await connection.execute(
                text("""
                UPDATE media.storage_analysis SET estimate_status='completed', estimate_collected_at=now(),
                  estimate=:estimate, updated_at=now() WHERE id=1 AND estimate_job_id=:job
            """),
                {"estimate": json.dumps(result, separators=(",", ":")), "job": job_id},
            )
    except Exception:
        async with engine.begin() as connection:
            await connection.execute(
                text("""
                UPDATE media.storage_analysis SET estimate_status='failed', updated_at=now()
                WHERE id=1 AND estimate_job_id=:job
            """),
                {"job": job_id},
            )
        raise
