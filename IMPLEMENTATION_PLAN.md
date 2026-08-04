# Implementation plan

## Текущий gate

`G0–G5 ACCEPTED — G6 IN PROGRESS`

G6 начат владельцем 2026-07-30. MacBook используется только для редактирования
и Git-доставки; authoritative проверки выполняются на clean resettable VPS.

## Завершённые этапы

| Этап | Результат |
|---|---|
| G0 | Изучены источники; созданы source copy и traceability |
| G1 | Проведены product/security/architecture audits, создан risk register |
| G2 | Проверены технологии, Telegram, geo и инфраструктурные варианты |
| G3 | Приняты `PD-001…PD-020`, включая UI-связанные product contracts |
| G4 | Принята архитектура; 22 исходных документа позднее объединены в семь |
| G5 | Принят облегчённый backlog из девяти slices |

## G6 — инженерный каркас

Готово в working tree:

- [x] `ADR-021`: authoritative VPS gate и optional secret-free GitHub CI;
- [x] CPython 3.14.6, bounded dependencies, Pyright strict и coverage 75%;
- [x] FastAPI app factory, health/readiness/metrics и lifecycle;
- [x] семь модулей и architecture import boundaries;
- [x] одна Alembic chain: PostGIS + семь owner schemas;
- [x] Stage 1 Compose: core, geo/import, ops и protected local media;
- [x] Nginx loopback-only, monitoring и VPS scripts;
- [x] baseline unit/architecture/migration/integration tests;
- [x] README, G4, G5, risks и changelog синхронизированы.

Осталось:

- [ ] создать окончательный `uv.lock` на VPS;
- [ ] получить и закоммитить immutable image digests;
- [ ] повторить authoritative gate на новом clean exact commit;
- [ ] закрыть applicable Critical/High findings;
- [ ] получить отдельное подтверждение владельца о завершении G6.

G6 evidence: commit SHA, image digests, migration head, проверки и result без
secrets/PII. Optional GitHub CI не заменяет VPS gate.

## Stage A — решения, каркас, VPS и HTTPS

Статус: `IN PROGRESS`, начат владельцем 2026-08-04.

- [x] Принятые продуктовые правила синхронизированы без изменения
  `SOURCE_SPECIFICATION.md`.
- [x] Подготовлены необязательный Telegram proxy, HTTPS-адреса, настоящий
  маршрут `/app`, серверные тесты и host Nginx templates.
- [ ] Ветка Stage A должна пройти полный G6 на точном опубликованном commit.
- [ ] После зелёного gate выполнить fast-forward в `main`, обновить evidence и
  повторить gate на окончательном `main`.
- [ ] Запустить только PostgreSQL, Redis, migrations, API, worker, beat,
  frontend и внутренний Nginx.
- [ ] После появления публичного DNS выпустить сертификат на `podvval.xyz` и
  `admin.podvval.xyz`, включить redirect и проверить внешний контур.

Bot, Nominatim, geo-import и monitoring в Stage A не запускаются. Текущее
`/app` является демонстрацией, не готовым MVP; новые product tables и auth не
добавляются.

## G7 — порядок реализации

После clean G6 выполняются девять срезов из
[G5](docs/g5/01-lightweight-mvp-backlog.md):

1. инженерный доступ и единая identity;
2. публичная карта/list/cards/profile;
3. admin, outbox/worker и media;
4. создание/moderation/revision/cancellation Event;
5. interest/participation/waitlist/chat;
6. internal/Telegram notifications и permission-safe deep links;
7. LookingPost, Q&A и cold start;
8. attendance и reputation;
9. cleanup, backup/restore и выпуск.

MVP-0 = G6 + Slice 1–4 в непубличном окружении. Первый публичный выпуск требует
все девять срезов. Post-demand/data-dependent scope запускается только по G5.

## Обязательный цикл среза

Перед началом: accepted sources, owner module, acceptance, risk, tests и
rollback/flag. В реализации: migration, permissions, idempotency,
observability и tests одним изменением. После: green exact-commit gate,
residual risks и краткое обновление документации.
