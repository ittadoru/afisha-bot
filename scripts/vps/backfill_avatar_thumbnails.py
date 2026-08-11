"""Check or idempotently repair 64x64 avatar variants."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import shutil
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from afishabot.core.config import Settings
from afishabot.core.database import create_database_engine
from afishabot.modules.media.application.image_processing import (
    AvatarImageProcessor,
    UnsafeImageError,
    validate_avatar_variant,
)


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _valid_variant(path: Path, *, byte_size: int | None, checksum: str | None) -> bool:
    try:
        validate_avatar_variant(path, expected_size=64)
    except UnsafeImageError:
        return False
    return not (
        (byte_size is not None and path.stat().st_size != byte_size)
        or (checksum is not None and _checksum(path) != checksum)
    )


async def run(*, repair: bool) -> int:
    settings = Settings()
    engine = create_database_engine(settings.database_dsn())
    try:
        async with engine.connect() as connection:
            rows = (
                (
                    await connection.execute(
                        text(
                            """
                        SELECT DISTINCT a.id,a.storage_key,
                          v.storage_key AS thumbnail_key,
                          v.byte_size AS thumbnail_size,
                          v.checksum_sha256 AS thumbnail_checksum
                        FROM accounts.profiles p
                        JOIN media.assets a ON a.id=p.avatar_asset_id
                          AND a.state='ready' AND a.purpose='profile_avatar'
                        LEFT JOIN media.asset_variants v ON v.source_asset_id=a.id
                          AND v.variant_key='avatar_64'
                        ORDER BY a.id
                        """
                        )
                    )
                )
                .mappings()
                .all()
            )

        healthy = repaired = broken = 0
        for row in rows:
            source = settings.media_root / row["storage_key"]
            target_key = row["thumbnail_key"] or f"avatars/{row['id']}.64.webp"
            target = settings.media_root / target_key
            if _valid_variant(
                target,
                byte_size=row["thumbnail_size"],
                checksum=row["thumbnail_checksum"],
            ):
                healthy += 1
                continue
            try:
                validate_avatar_variant(source, expected_size=256)
            except UnsafeImageError:
                broken += 1
                print(f"unrecoverable source asset={row['id']}")
                continue
            if not repair:
                broken += 1
                print(f"needs-repair asset={row['id']}")
                continue

            work_id = uuid4()
            work_source = settings.media_root / "quarantine" / f"{work_id}.upload"
            work_256 = settings.media_root / "quarantine" / f"{work_id}.256.webp"
            work_64 = settings.media_root / "quarantine" / f"{work_id}.64.webp"
            work_source.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
            target.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
            shutil.copyfile(source, work_source)
            try:
                AvatarImageProcessor().process_variants(work_source, work_256, work_64)
                os.replace(work_64, target)
                checksum = _checksum(target)
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO media.asset_variants
                              (id,source_asset_id,variant_key,storage_key,mime_type,
                               width,height,byte_size,checksum_sha256)
                            VALUES
                              (:id,:asset,'avatar_64',:key,'image/webp',64,64,:size,:checksum)
                            ON CONFLICT (source_asset_id,variant_key) DO UPDATE SET
                              storage_key=excluded.storage_key,
                              mime_type=excluded.mime_type,
                              width=excluded.width,
                              height=excluded.height,
                              byte_size=excluded.byte_size,
                              checksum_sha256=excluded.checksum_sha256,
                              updated_at=now()
                            """
                        ),
                        {
                            "id": uuid4(),
                            "asset": row["id"],
                            "key": target_key,
                            "size": target.stat().st_size,
                            "checksum": checksum,
                        },
                    )
                repaired += 1
            except Exception:
                target.unlink(missing_ok=True)
                raise
            finally:
                work_source.unlink(missing_ok=True)
                work_256.unlink(missing_ok=True)
                work_64.unlink(missing_ok=True)

        print(
            f"avatar thumbnails healthy={healthy} repaired={repaired} broken={broken}"
        )
        return 1 if broken else 0
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="only report problems")
    mode.add_argument("--repair", action="store_true", help="repair recoverable rows")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(repair=bool(args.repair))))


if __name__ == "__main__":
    main()
