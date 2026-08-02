# G4 — система и модули

Статус: `ACCEPTED`. Документ объединяет прежние G4.1 и G4.2 без изменения
принятых PD/ADR. При конфликте действуют `PRODUCT_DECISIONS.md`, затем
`DECISIONS.md`.

## Карта консолидации

| Прежний G4 | Новый документ |
|---|---|
| 1–2 | система, containers, модули и ports |
| 3, 5, 11–14, 16 | API, user/staff auth, permissions, profile и location reveal |
| 4 | данные, state machines, retention и compaction |
| 6–8 | facts, outbox/inbox, delivery, dead-letter и reconciliation |
| 9–10, 20–21 | triggers, deployment, observability, migrations и quality gates |
| 15, 18 | карта, geo providers и media boundary |
| 17, 19 | reputation, Trust & Safety, privacy и threat controls |

## Контекст и контейнеры

Afisha предоставляет публичный адаптивный сайт, Telegram Mini App,
Telegram-уведомления и отдельную закрытую admin-панель. Все клиенты используют
один backend API. PostgreSQL/PostGIS остаётся источником бизнес-истины.

| Контейнер | Назначение | Доступ |
|---|---|---|
| Public web | карта, список, карточки и публичные профили | anonymous/read-only и authenticated actions |
| Mini App | полный пользовательский интерфейс внутри Telegram | только после проверки `initData` |
| Admin web | moderation и operations | отдельная staff identity |
| API | HTTP/application orchestration | единственная бизнес-граница клиентов |
| Worker/beat | фоновые и периодические application commands | внутренняя сеть |
| PostgreSQL/PostGIS | owner schemas, транзакции, outbox и audit | только backend/migration runner |
| Redis | Celery broker, rate limits и короткий cache | не источник бизнес-истины |
| Nominatim | закрытый reverse geocoding | только backend |
| Local media | оригиналы в quarantine и безопасные производные | API/worker, без прямой раздачи |

Внешние системы: Telegram Bot API/OIDC, OpenFreeMap и off-server backup
provider. Браузер получает tiles напрямую, но event markers и защищённые
координаты — только через API.

## Семь owner-модулей

| Модуль | Владеет |
|---|---|
| `accounts` | Telegram identity, внутренний User, profile, preferences и user sessions |
| `discovery` | публичные projections, карта, категории, поиск, LookingPost и его Q&A |
| `events` | Event, revisions, location visibility, interest, participation, waitlist и attendance |
| `communication` | чат, объявления, центр уведомлений, Telegram delivery и reminders |
| `trust_safety` | staff identity, permissions, moderation, жалобы, ограничения, appeals и audit |
| `reputation` | signal ledger, projections, уровни и private policy adapter |
| `media` | upload, quarantine, обработка, storage lifecycle и attachment state |

`admin` — delivery adapter, а не восьмой доменный модуль. API, worker, beat и
Telegram webhook вызывают application ports и не владеют бизнес-правилами.

Диаграммы:

- [владение модулями](diagrams/02-module-ownership.mmd);
- [разрешённые синхронные зависимости](diagrams/02-sync-dependency-dag.mmd).

## Внутренний каркас модуля

Каждый модуль содержит:

- `public` — стабильные команды, запросы, DTO и события для других модулей;
- `application` — use cases и transaction boundary;
- `domain` — агрегаты, value objects, guards и domain facts;
- `infrastructure` — ORM, repositories и внешние adapters.

Другой модуль импортируется только через `public`. Запрещены чужие ORM-модели,
таблицы, repositories, `domain`, `application` и `infrastructure`. Domain не
импортирует FastAPI, SQLAlchemy, Celery, Redis или Telegram SDK.

`shared_kernel` содержит только идентификаторы, время, базовые ошибки,
event envelope и transaction protocols. Общие бизнес-правила в нём запрещены.

## Межмодульное взаимодействие

- Ведущий use case изменяет только owner-state и пишет outbox-факт в одной
  PostgreSQL-транзакции.
- Нужный синхронный ответ получается через чужой `public` port без чтения
  чужих таблиц.
- Последующие projections/уведомления выполняются после commit и идемпотентны.
- Safety hide и отзыв доступа должны закрывать публичную/защищённую выдачу
  fail-closed, даже если обычная projection отстаёт.
- Redis/Celery outage не отменяет committed business operation; outbox остаётся
  доступным для повторной доставки.

Основные public capabilities:

| Owner | Capabilities |
|---|---|
| `accounts` | resolve identity, load safe profile/session subject |
| `discovery` | publish/hide projection, query city viewport/list |
| `events` | create/revise/cancel, join/leave/waitlist, attendance |
| `communication` | authorize chat, enqueue notification/announcement |
| `trust_safety` | authorize staff, moderation decision, restriction lookup |
| `reputation` | accept finalized signal, return safe level projection |
| `media` | create upload, process, approve/reject, delete attachment |

## Неподвижные границы

1. Один модуль и одна PostgreSQL schema владеют каждой бизнес-записью.
2. Cross-schema FK/JOIN/view/trigger и foreign ORM relationship запрещены.
3. Route выполняет transport validation и вызывает один application use case.
4. Authorization проверяется на сервере для действия и конкретного объекта.
5. Внешние SDK остаются в adapters; все вызовы имеют timeout и bounded retry.
6. Business state никогда не выводится только из cache, Celery или клиента.
7. Новые сервисы/серверы появляются только по измеримым triggers из ADR.
