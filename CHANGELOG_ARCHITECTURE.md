# Architecture changelog

Краткая история принятых решений. Детальные предыдущие формулировки доступны в
Git history. Даты указаны в часовом поясе Europe/Moscow.

## 2026-08-01 — принят UI/UX-контракт и синхронизированы продуктовые правила

- Создан единый UI-документ для сайта, Mini App и admin-панели с разделами
  MVP/Post-MVP, навигацией, ключевыми экранами, состояниями и accessibility.
- Принят `PD-020`: LookingPost Q&A, safe anonymous preview, новые text limits,
  report-based moderation и связанные уведомления.
- Persistent Event drafts удалены из активного G4/G5/retention: форма живёт
  только в открытом клиенте, а сервер принимает полный финальный submit.
- Deep links закреплены как ссылки на object/action без передачи permission;
  Telegram write access не запрашивается.
- Код, макеты, ветки и commits этим изменением не создавались.

## 2026-07-30 — документация сокращена без изменения решений

- 22 принятых документа G4 объединены в семь тематических файлов.
- Повторные checklists, traceability, текстовые копии диаграмм, исследования
  уже сделанного выбора и подробный исторический журнал удалены.
- Сохранены PD, все ADR, требования, guards, transitions, privacy/auth,
  retention, delivery/recovery и release gates.
- Отдельные Mermaid-файлы оставлены только для существенно полезных связей.
- Продукт, API, данные, код и статус G6 не изменились.

## Основные этапы

| Дата | Этап | Результат |
|---|---|---|
| 2026-07-26 | G0 | Исходная спецификация перенесена в Markdown, заведены traceability, вопросы и риски |
| 2026-07-26–28 | G1–G3 | Проведён аудит, закрыты product blockers, приняты `PD-001…PD-019` |
| 2026-07-28 | ADR audit | Уточнены `ADR-000`, `ADR-001`, `ADR-010…ADR-020` |
| 2026-07-29 | G4.1–G4.4 | Приняты C4, модули, permissions, данные и state machines |
| 2026-07-29 | G4.5–G4.9 | Приняты API/security, facts, outbox/DLQ и Kafka triggers |
| 2026-07-29 | G4.10–G4.14 | Приняты deployment, user/staff auth и exact-location boundary |
| 2026-07-29 | G4.15–G4.18 | Приняты map/profile/reputation/geo contracts |
| 2026-07-29 | G4.19–G4.21 | Приняты threat model, observability и delivery gates |
| 2026-07-30 | G5 | Принят облегчённый backlog из девяти vertical slices |
| 2026-07-30 | ADR-021/G6 | Начат инженерный skeleton; authority перенесён на clean-VPS exact-commit gate |

## Ключевые решения

| Область | Принято |
|---|---|
| Продукт | бесплатные безопасные офлайн-события; три launch city; возраст 14+ |
| Доступ | public read-only web; Telegram OIDC/PKCE и Mini App initData |
| Identity | единый internal user; staff identity отдельно от Telegram |
| Архитектура | модульный монолит, семь owner-модулей и отдельные schemas |
| Данные | PostgreSQL/PostGIS truth, immutable revisions, compact final snapshots |
| Интерфейс | mobile map-first, desktop list/map/panel, shared UI contract без готовой design system |
| Async | transactional outbox, Celery/Redis, Kafka только по triggers |
| Карта | MapLibre + OpenFreeMap + закрытый regional Nominatim |
| Приватность | street/exact projections, fail-closed hide и минимизация telemetry |
| Media | безопасный re-encode без EXIF, local protected storage |
| Reputation | ledger/projections, private production policy, trust_safety блокирует |
| Operations | Stage 1 Compose, off-server backup позднее, ручной deployment |
| Quality | coverage ≥85%, security gates и authoritative clean-VPS verification |

## Текущий gate

G0–G5 приняты. G6 skeleton подготовлен, но остаётся `IN PROGRESS`, пока на VPS
не созданы и не закоммичены `uv.lock`/image digests, exact commit не прошёл
authoritative gate и владелец отдельно не подтвердил завершение.
