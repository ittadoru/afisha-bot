# AfishaBot

Afisha — социальная карта бесплатных безопасных офлайн-событий для городов
Дагестана. G0–G5 приняты; G6 skeleton подготовлен, но ожидает VPS verification.
Продуктовые функции и frontend ещё не реализованы.

## Источники

- [актуальный обзор](CURRENT_SPECIFICATION_V1.md);
- [продуктовые решения](PRODUCT_DECISIONS.md);
- [ADR](DECISIONS.md);
- [семь документов G4](docs/g4);
- [облегчённый G5](docs/g5/01-lightweight-mvp-backlog.md);
- [текущий план](IMPLEMENTATION_PLAN.md);
- [риски](RISKS.md);
- [исходная спецификация](SOURCE_SPECIFICATION.md) и
  [traceability](REQUIREMENTS_TRACEABILITY.md).

Приоритет: PD → ADR → G4 → незаменённая исходная спецификация.

## Правило разработки

MacBook используется только для редактирования, просмотра diff и разрешённой
Git-доставки. `uv`, Python, тесты, Docker, migrations и image downloads
запускаются только на resettable Ubuntu 24.04 `linux/amd64` VPS.

G6 не открывает production `80/443`, domains или TLS. Nginx доступен только
через `127.0.0.1:8080` и SSH tunnel.

## Подготовка на VPS

В clean checkout:

```bash
cp .env.example .env
bash scripts/vps/preflight.sh
bash scripts/vps/pin_images.sh
bash scripts/vps/refresh_lock.sh
```

Заполнить `.env` только staging values; файл не коммитить. Проверить и
закоммитить `uv.lock` и `deploy/image-digests.env`, затем создать новый clean
checkout получившегося exact commit.

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
