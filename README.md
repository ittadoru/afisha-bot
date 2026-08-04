# AfishaBot

Afisha — социальная карта бесплатных безопасных офлайн-событий для городов
Дагестана. G0–G5 приняты; G6 технически проверен на VPS и ожидает отдельного
подтверждения владельца. Продуктовые функции ещё не реализованы; текущий
frontend — демонстрационный лендинг и карта Stage A.

## Источники

- [актуальный обзор](CURRENT_SPECIFICATION_V1.md);
- [продуктовые решения](PRODUCT_DECISIONS.md);
- [ADR](DECISIONS.md);
- [семь документов G4](docs/g4);
- [облегчённый G5](docs/g5/01-lightweight-mvp-backlog.md);
- [принятый UI/UX-контракт](docs/ui/01-ui-ux-decisions.md);
- [текущий план](IMPLEMENTATION_PLAN.md);
- [риски](RISKS.md);
- [исходная спецификация](SOURCE_SPECIFICATION.md) и
  [traceability](REQUIREMENTS_TRACEABILITY.md).

Приоритет: PD → ADR → G4 → незаменённая исходная спецификация.

## Правило разработки

MacBook используется только для редактирования, просмотра diff и разрешённой
Git-доставки. `uv`, Python, тесты, Docker, migrations и image downloads
запускаются только на resettable Ubuntu 24.04 `linux/amd64` VPS.

Внутренний Nginx всегда доступен только через `127.0.0.1:8080`. После зелёного
G6 Stage A добавляет отдельный host Nginx и HTTPS по инструкции
[Stage A — VPS и HTTPS](docs/deployment/stage-a-vps.md).

## Подготовка на VPS

В clean checkout:

```bash
cp .env.example .env
bash scripts/vps/preflight.sh
bash scripts/vps/pin_images.sh /tmp/afisha-image-digests.env
```

Заполнить `.env` только staging values; файл не коммитить. Полученные на VPS
digests перенести из временного файла в локальный
`deploy/image-digests.env`. Проверить и закоммитить `uv.lock` и digest-файл
локально, отправить `main`, затем выполнить на VPS только fast-forward pull.
Если lock-файл требуется пересоздать, `refresh_lock.sh` запускается на VPS уже
после появления закоммиченного digest-файла; полученный `uv.lock` также сначала
переносится и коммитится локально.
`verify_g6.sh` требует чистый checkout, совпадение `HEAD` с upstream и
закоммиченные immutable digests.

## Authoritative gate

```bash
bash scripts/vps/verify_g6.sh
```

Скрипт проверяет locked dependencies, Ruff, Pyright strict, tests/coverage,
architecture, migrations/PostGIS, Redis/Celery, Nginx boundaries, security
scans, SBOM и container/Compose smoke. Evidence пишется в ignored
`artifacts/g6`.

GitHub Actions выполняет только дополнительный secret-free subset. После
зелёного VPS gate владелец отдельно принимает G6; затем начинается Slice 1.
