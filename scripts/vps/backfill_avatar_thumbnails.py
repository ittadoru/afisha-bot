"""Idempotently create and register missing 64x64 avatar variants.

Run after deploying the avatar variant schema. Existing 256px source files remain
untouched; broken variant rows are repaired and missing rows are inserted.
"""

from __future__ import annotations

import asyncio
import hashlib
import shutil
from uuid import uuid4

from sqlalchemy import text

from afishabot.core.config import Settings
from afishabot.core.database import create_database_engine
from afishabot.modules.media.application.image_processing import AvatarImageProcessor


async def main() -> None:
    settings = Settings()
    engine = create_database_engine(settings.database_dsn())
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text(
                        """
                        SELECT DISTINCT
                          a.id,a.storage_key,v.storage_key AS thumbnail_key
                        FROM accounts.profiles p
                        JOIN media.assets a ON a.id=p.avatar_asset_id
                          AND a.state='ready' AND a.purpose='profile_avatar'
                        LEFT JOIN media.asset_variants v ON v.source_asset_id=a.id
                          AND v.variant_key='avatar_64'
                        ORDER BY a.id
                        """
                    )
                )
            ).mappings().all()

        repaired = 0
        skipped = 0
        for row in rows:
            source = settings.media_root / row["storage_key"]
            target_key = row["thumbnail_key"] or f"avatars/{row['id']}.64.webp"
            target = settings.media_root / target_key
            if target.is_file():
                skipped += 1
                continue
            if not source.is_file():
                print(f"skip missing source asset={row['id']}")
                continue

            work_id = uuid4()
            work_source = settings.media_root / "quarantine" / f"{work_id}.upload"
            work_256 = settings.media_root / "quarantine" / f"{work_id}.256.webp"
            work_source.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
            target.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
            shutil.copyfile(source, work_source)
            try:
                AvatarImageProcessor().process_variants(work_source, work_256, target)
                checksum = hashlib.sha256(target.read_bytes()).hexdigest()
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

        print(f"avatar thumbnails repaired={repaired} skipped={skipped}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
