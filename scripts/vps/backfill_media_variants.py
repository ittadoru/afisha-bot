"""Check or idempotently repair event and profile-background image variants."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import shutil
from pathlib import Path
from typing import TypedDict, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from afishabot.core.config import Settings
from afishabot.core.database import create_database_engine
from afishabot.modules.media.application.image_processing import (
    EventImageProcessor,
    ProfileBackgroundImageProcessor,
    UnsafeImageError,
    validate_webp_variant,
)


class AssetRow(TypedDict):
    id: UUID
    purpose: str
    storage_key: str


class VariantRow(TypedDict):
    variant_key: str
    storage_key: str
    byte_size: int
    checksum_sha256: str


VariantSpec = tuple[str, int, int]
MissingVariant = tuple[str, int, int, Path]


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid(
    path: Path, width: int, height: int, size: int | None, digest: str | None
) -> bool:
    try:
        validate_webp_variant(path, width=width, height=height)
    except UnsafeImageError:
        return False
    return (size is None or path.stat().st_size == size) and (
        digest is None or checksum(path) == digest
    )


async def upsert(
    engine: AsyncEngine,
    asset_id: UUID,
    key: str,
    storage_key: str,
    path: Path,
    width: int,
    height: int,
) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text("""
            INSERT INTO media.asset_variants
              (id,source_asset_id,variant_key,storage_key,mime_type,width,height,
               byte_size,checksum_sha256)
            VALUES (:id,:asset,:variant,:key,'image/webp',:width,:height,
                    :size,:checksum)
            ON CONFLICT (source_asset_id,variant_key) DO UPDATE SET
              storage_key=excluded.storage_key,width=excluded.width,height=excluded.height,
              byte_size=excluded.byte_size,checksum_sha256=excluded.checksum_sha256,
              updated_at=now()
            """),
            {
                "id": uuid4(),
                "asset": asset_id,
                "variant": key,
                "key": storage_key,
                "width": width,
                "height": height,
                "size": path.stat().st_size,
                "checksum": checksum(path),
            },
        )


async def run(*, repair: bool) -> int:
    settings = Settings()
    engine = create_database_engine(settings.database_dsn())
    healthy = repaired = broken = 0
    try:
        async with engine.connect() as connection:
            raw_assets = (
                (
                    await connection.execute(
                        text("""
                SELECT id,purpose,storage_key FROM media.assets
                WHERE state='ready' AND purpose IN ('event_photo','profile_background')
                ORDER BY id
            """)
                    )
                )
                .mappings()
                .all()
            )
            assets = [cast(AssetRow, dict(row)) for row in raw_assets]
        for asset in assets:
            source = settings.media_root / asset["storage_key"]
            specs: tuple[VariantSpec, VariantSpec] = (
                (("event_640", 640, 480), ("event_320", 320, 240))
                if asset["purpose"] == "event_photo"
                else (("background_768", 768, 432), ("background_320", 320, 180))
            )
            async with engine.connect() as connection:
                raw_rows = (
                    await connection.execute(
                        text("""
                    SELECT variant_key,storage_key,byte_size,checksum_sha256
                    FROM media.asset_variants WHERE source_asset_id=:asset
                """),
                        {"asset": asset["id"]},
                    )
                ).mappings().all()
                rows: dict[str, VariantRow] = {
                    str(row["variant_key"]): cast(VariantRow, dict(row))
                    for row in raw_rows
                }
            missing: list[MissingVariant] = []
            for key, width, height in specs:
                row = rows.get(key)
                path = settings.media_root / (
                    row["storage_key"]
                    if row
                    else f"{Path(asset['storage_key']).with_suffix('')}.{width}.webp"
                )
                if valid(
                    path,
                    width,
                    height,
                    row["byte_size"] if row else None,
                    row["checksum_sha256"] if row else None,
                ):
                    healthy += 1
                else:
                    missing.append((key, width, height, path))
            if not missing:
                continue
            try:
                if asset["purpose"] == "event_photo":
                    validate_webp_variant(source, width=1200, height=900)
                else:
                    validate_webp_variant(source, width=1280, height=720)
            except UnsafeImageError:
                broken += len(missing)
                print(f"unrecoverable source asset={asset['id']}")
                continue
            if not repair:
                broken += len(missing)
                names = ",".join(item[0] for item in missing)
                print(f"needs-repair asset={asset['id']} variants={names}")
                continue
            work = settings.media_root / "quarantine" / f"{uuid4()}.upload"
            work.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
            shutil.copyfile(source, work)
            targets: dict[str, Path] = {key: path for key, _, _, path in missing}
            for path in targets.values():
                path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
            temporary_full = source.with_name(f".{uuid4()}.full.tmp.webp")
            if asset["purpose"] == "event_photo":
                EventImageProcessor().process_variants(
                    work,
                    temporary_full,
                    targets.get("event_640"),
                    targets.get("event_320"),
                )
            else:
                ProfileBackgroundImageProcessor().process_variants(
                    work,
                    temporary_full,
                    targets.get("background_768"),
                    targets.get("background_320"),
                )
            temporary_full.unlink(missing_ok=True)
            for key, width, height, path in missing:
                storage_key = str(path.relative_to(settings.media_root))
                await upsert(engine, asset["id"], key, storage_key, path, width, height)
                repaired += 1
        print(f"media variants healthy={healthy} repaired={repaired} broken={broken}")
        return 1 if broken else 0
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(repair=args.repair)))


if __name__ == "__main__":
    main()
