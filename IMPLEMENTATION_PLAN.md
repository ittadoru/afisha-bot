# Implementation plan

## Текущий gate

`PRODUCT AND ADR DECISIONS ACCEPTED / G4 AND G5 REQUIRED`

Актуальные `PD-001…PD-019` и все 13 существующих ADR согласованы. Production-реализация запрещена до готовности и отдельного подтверждения архитектурного пакета G4, подробного backlog G5 и моей однозначной команды начать разработку.

## Чек-лист этапов

### G0 — изучение источников

- [x] Полностью прочитать 39 страниц канонической спецификации.
- [x] Проверить DOCX визуальным рендером.
- [x] Прочитать полное пользовательское задание.
- [x] Изучить существующий репозиторий, зависимости и CI.
- [x] Зафиксировать source-of-truth и правила процесса.
- [x] Сохранить полную Markdown-копию спецификации в репозитории.
- [x] Связать все 28 пакетов исходных требований с актуальными PD/ADR.

Результат: созданы `SOURCE_SPECIFICATION.md` и `REQUIREMENTS_TRACEABILITY.md`; актуальный обзор проекта позднее вынесен в `CURRENT_SPECIFICATION_V1.md`, production-состояние не изменено.

### G1 — первичный аудит

- [x] Найти противоречия жизненных циклов и сущностей.
- [x] Проверить product/safety/cold-start/reputation/attendance abuse cases.
- [x] Выполнить STRIDE baseline.
- [x] Проверить concurrency, idempotency, partial-failure и recovery risks.
- [x] Проверить инженерный scaffold.
- [x] Назначить Critical/High/Medium/Low.

Результат: `RISKS.md`, предложения в `DECISIONS.md`.

### G2 — актуальное техническое исследование

- [x] Проверить Python 3.14 и основные библиотеки.
- [x] Сравнить Kafka/Celery/Redis/outbox.
- [x] Сравнить MapLibre/Leaflet/OpenLayers и tile hosting.
- [x] Сравнить Nominatim/Photon/Pelias/Geoapify/LocationIQ.
- [x] Проверить Telegram initData, write access, webhook, deep links и rate limits; LocationManager исключить вместе с «Рядом со мной».
- [x] Определить проверку Nominatim перед запуском: ручная проверка реальных точек администратором без формального числового порога.
- [ ] Выполнить performance prototype MapLibre в целевых Telegram clients.

Performance prototype MapLibre требует отдельного разрешения; импорт и ручная проверка Nominatim выполняются позже как launch-задача.

### G3 — продуктовые решения

- [x] Закрыть все `BLOCKING` вопросы, включая отсутствие confirmation/reconfirmation.
- [x] Зафиксировать явно принятые изменения спецификации в служебных документах.
- [x] Согласовать MVP-границы attendance/reputation, moderation и location privacy.
- [x] Согласовать состав MVP и deferred scope.
- [x] Принять раздельные retention classes и конкретные сроки MVP.
- [x] Принять компактную долгосрочную историю итоговых фактов без полного event sourcing и бессрочного media storage.
- [x] Зафиксировать безопасность запросов и минимизацию пользовательских действий как обязательные принципы.
- [x] Зафиксировать публичный read-only web без входа и Telegram OIDC для любых действий.
- [x] После Telegram-входа предоставить полноценный адаптивный web-интерфейс наравне с Mini App.
- [x] Зафиксировать публичный профиль, восьмизначный public ID и avatar pipeline `256×256 WebP` без оригинала/EXIF.
- [x] Зафиксировать два уровня точности и три общих режима раскрытия: street-only, exact для участников, exact для всех.
- [x] Зафиксировать постоянную легенду карты и разные формы approximate/exact markers.
- [x] Принять четыре публичных уровня репутации; `Новый пользователь` остаётся отдельным статусом.
- [x] Разделить публичный ReputationPolicy contract и закрытую production-конфигурацию.
- [x] Принять семь доменных модулей, отдельный admin adapter и две административные роли.
- [x] Вынести reputation в самостоятельный MVP-модуль, а игровые achievements оставить отдельным post-MVP модулем.
- [x] Принять ручную премодерацию событий новых организаторов с текстовым fallback через 3 часа.
- [x] Снимать её после трёх успешных событий и возвращать при низкой надёжности/upheld safety complaint.
- [x] Зафиксировать только скрытую оценку события `1–5` без тегов/текста как слабый reputation signal.
- [x] Зафиксировать неизменяемые revisions, общий лимит двух переносов даты/времени и запрет смены категории, точки и адреса после публикации.
- [x] Принять единый стандарт аналитических событий, версий схем, причин, дедупликации, privacy и контроля качества для всех продуктовых сценариев.
- [x] Принять итоговую проекцию Event/LookingPost без полной архивной копии: точный адрес остаётся защищённым, тяжёлый контент в долгую историю не входит.
- [x] Убрать «Рядом со мной» и геолокацию пользователя из MVP; сохранять только выбранный город.
- [x] Зафиксировать street markers для скрытых событий и отключить кластеризацию до появления измеримой плотности.
- [x] Принять комплексную программу холодного старта с реальным предложением, полезным пустым состоянием и метриками здоровья городов.
- [x] Принять MapLibre + публичный OpenFreeMap + собственный региональный Nominatim для MVP и отдельный собственный tile server после MVP.
- [x] Принять transactional outbox, ограниченные retry/dead-letter и отдельного operations bot для безопасных оповещений назначенных администраторов.
- [x] Принять единый internal user для Mini App/OIDC, минимальные Telegram scopes без phone и отсутствие account recovery/identity transfer в MVP.
- [x] Последовательно уточнить все 13 существующих ADR и синхронизировать противоречащие сводки.
- [x] Зафиксировать отдельную password-authentication модель закрытой панели, сроки пользовательских и административных сессий и необязательный запуск бота для website.
- [x] Включить Celery/Redis в MVP и принять Kafka-ready outbox без Kafka.
- [x] Зафиксировать поэтапную топологию от одного физического сервера.

Exit criteria: ни один Critical риск не остаётся без owner/mitigation/accepted residual risk.

### G4 — архитектурный пакет

После G3 подготовить, но ещё не реализовывать:

- [x] C4 context/container diagrams.
- [x] Модульные границы, публичные порты и dependency rules.
- [ ] Permission catalogue для `moderator`/`admin`, admin adapter и будущего расширения ролей.
- [ ] ER/data model с final event snapshot, normalized participation outcomes, delete/archive/versioning/retention semantics.
- [ ] Полные state machines:
  - [ ] LookingPost;
  - [ ] Event lifecycle + moderation visibility;
  - [ ] Interest, participation, waitlist entry/offer;
  - [ ] Participation lifecycle без confirmation;
  - [ ] Attendance code redemption/decision/dispute — обязательный автомат MVP;
  - [ ] Challenge — отложенный автомат;
  - [ ] Moderation report;
  - [ ] Telegram notification delivery.
- [ ] Для каждого перехода: actor, guard, forbidden transitions, side effects, audit event, recovery.
- [ ] Для каждого продуктового сценария: analytics contract, schema version, source, outcome/reason, retention class, data owner и quality checks.
- [ ] Compaction/cleanup flow: final-state guard, dispute/legal hold, aggregate update, media lifecycle deletion, idempotency и reconciliation.
- [ ] API contracts, error model, idempotency and authorization matrix.
- [ ] Domain event catalogue с producer/consumer/payload/schema version/order/dedup/retry/replay.
- [ ] Transactional outbox/inbox design и reconciliation jobs.
- [ ] Dead-letter admin view, permission `ops_alerts.receive`, отдельный operations bot, safe alert DTO и expiry/retry policy.
- [ ] Kafka-readiness matrix: event envelope, schema evolution, publisher port, lag/fan-out/replay triggers.
- [ ] Deployment diagrams для этапов 1/2/3 серверов, Docker networks, exposed ports, backups и migration steps.
- [ ] Web/Mini App auth flow: Telegram initData + Telegram OIDC/PKCE → единый internal user; website 30/90 дней, Mini App 24 часа.
- [ ] Telegram identity table: unique user ID, OIDC issuer/subject, bot-start/delivery state, session/replay controls и запрет profile overwrite.
- [ ] Admin authentication flow: invitation/reset/bootstrap, Argon2id, отдельные cookies, 8-часовой absolute и 30-минутный idle timeout, re-auth, CSRF/rate limit/audit.
- [ ] Exact-location projection/reveal matrix: street/public/participant modes, reminders, audit, cache isolation и irreversible disclosure warning.
- [ ] Map legend/accessibility contract и deterministic approximate-marker placement по street geometry.
- [ ] Public-profile projection: random public ID, avatar processing, anonymous/authorized visibility и enumeration limits.
- [ ] ReputationPolicy port: public signal/projection contracts, demo policy и external production configuration без weights/thresholds в Git.
- [ ] Geo provider ports, canonical DTOs, caching/privacy projections.
- [ ] Threat model/data-flow diagrams и security controls.
- [ ] Observability model, SLO/RPO/RTO, dashboards/alerts.
- [ ] CI/CD pipeline, migration discipline и Definition of Done.

Exit criteria: владелец продукта отдельно подтверждает архитектуру, стек и модель данных.

### G5 — план MVP и backlog

- [x] Разделить scope на MVP-0, first release, post-demand и data-dependent.
- [ ] Для каждой функции определить hypothesis, dependencies, acceptance criteria, safety gate, metrics и rollback/feature flag.
- [ ] Составить epics/features/tasks с тестами и рисками.
- [ ] Оценить ресурсы выбранного Nominatim, публичного OpenFreeMap и будущего собственного tile server; зафиксировать безопасный rollout ручного OSM update.
- [ ] Согласовать backlog и release criteria.

Exit criteria: владелец продукта отдельно подтверждает MVP и спорные продуктовые решения.

### G6 — подготовка инженерного каркаса

Начинается только после полного G4/G5 approval.

- [ ] Исправить README: Python 3.14, uv, Pyright, закрыть code fence.
- [ ] Исправить pytest coverage target на `afishabot`, добавить `pytest-cov`.
- [ ] Переключить Pyright на strict.
- [ ] Зафиксировать runtime dependencies и supported patch versions.
- [ ] Добавить compose для PostgreSQL/PostGIS, Redis, Celery worker/beat и object storage emulator.
- [ ] Создать application/module skeleton без бизнес-функций.
- [ ] Добавить lint/type/unit/integration/migration/security CI stages.
- [ ] Зафиксировать baseline tests и architecture import rules.

Exit criteria: clean CI на пустом архитектурном skeleton.

### G7 — последовательная реализация vertical slices

Предлагаемый порядок, ожидающий согласования MVP:

1. Telegram Mini App authentication + website OIDC/PKCE + internal account/profile/private city setting.
2. Public responsive map/event/organizer-profile pages; all actions require Telegram login, after login the full web UI is available.
3. Public profile projection + random eight-digit ID + `256×256 WebP` avatar pipeline.
4. Redis broker + Celery worker/beat + transactional outbox foundation.
5. Reputation ledger/projection + public levels + private production policy adapter.
6. Geo provider adapter + MapLibre/OpenFreeMap map/list/cards/categories + marker-based reverse geocoding через собственный Nominatim.
7. Media checks + очередь премодерации + текстовый fallback событий новых организаторов.
8. Event draft/publish/revision/cancel + street/exact projections + participant/public reveal modes + public deep link.
9. Like-interest, join/cancel/capacity/FIFO waitlist with concurrency tests.
10. Participant-only simple text chat + public announcements + access/retention windows.
11. In-app center + Telegram classes, 30-minute chat aggregation and hidden-address reminders.
12. LookingPost TTL 72 hours, likes and conversion with interest transfer.
13. Six-digit attendance code, five-attempt redemption, preliminary no-show and 24-hour dispute.
14. Internal stars + final reputation projections and recovery/appeal signals.
15. Six-hour low-activity check behind per-city feature flag.
16. Admin-only public civic events without join/chat/attendance.
17. Post-MVP: challenges/achievements as a separate module.
18. Semantic/AI search and ML recommendations after sufficient data.

Для каждого slice:

- до начала — ссылка на plan/ADR, файлы/модули, risks, unresolved questions;
- во время — migrations, permissions, idempotency, observability и tests в одном scope;
- после — changed files, tests, deviations, residual risks, обновление служебных документов.

## Обязательная стратегия тестирования

| Уровень | Обязательное покрытие |
|---|---|
| Unit/property | state guards, value objects, scoring/ranking rules, normalization |
| Integration DB | constraints, PostGIS queries, transactions, locks, outbox/inbox |
| API contract | validation, errors, pagination, idempotency, version conflict |
| Permissions/security | BOLA/IDOR, chat grants, exact-location projection, moderator/admin |
| Concurrency | last place, duplicate join, waitlist offer, deep-link handling, low-activity-check-vs-join |
| External adapters | Telegram/geocoder/object storage timeout, 429, malformed response, failover |
| Migration | upgrade on empty/current snapshot, model/schema diff, forward-fix/rollback plan |
| E2E | Telegram auth → discover → event → join → lifecycle notification |
| E2E | event → chat cutoff → attendance code → preliminary no-show/dispute → reputation projection |
| Load | dense map bbox, hot city, polling chat, broadcast and cleanup queues |
| Recovery | crash after commit, duplicate webhook/event/task, worker lease expiry, restore drill |
| Request security | forged initData, IDOR/BOLA, duplicate command, mass assignment, rate limit, secret/coordinate log redaction |

## Предлагаемый CI pipeline после G6

1. Formatting check.
2. Ruff.
3. Pyright strict.
4. Unit/property tests.
5. Integration tests with PostgreSQL/PostGIS.
6. Alembic upgrade and model/schema consistency.
7. Dependency audit, secret scan and SAST.
8. Docker build with SBOM and container scan.
9. Smoke test.
10. Artifacts.
11. Deployment only from protected branch/environment after all gates.

## Architecture triggers вместо преждевременной инфраструктуры

| Компонент | Возврат к решению, когда |
|---|---|
| Redis | Уже выбран для MVP как Celery broker/rate limit/cache; разносить на отдельный сервер только по нагрузке/HA |
| Celery | Уже выбран для MVP; отдельный worker server появляется при измеримой CPU/RAM нагрузке |
| Kafka | ≥2 независимых consumers, нужен replay/analytics, измеримый outbox lag/fan-out/throughput и есть operations owner |
| Chat service | соединения/retention/moderation масштабируются независимо от core API |
| Recommendation service | отдельная модель deploy/feature computation и достаточный event dataset |
| Self-host maps/geocoder | hosted cost/SLA/data-residency/quality benchmark оправдывает operations |

## Следующее действие

Следующее действие — G4 без production-кода: C4-диаграммы, модули, ER-модель, state machines, API, request-security matrix, geo/media providers, outbox и окончательный стек. После отдельного согласования G4 выполняется backlog G5.

## Обязательный post-MVP backlog

Эти задачи не должны потеряться после выпуска MVP:

1. Полноценный real-time chat — только после проверки необходимости; WebSocket и отдельная moderation/retention модель.
2. Игровые achievements/challenges отдельным модулем, не смешанным с reputation.
3. Кластеризация карты — только после измеримой плотности.
4. Marketing notifications — только после отдельного продуктового и consent-решения.
5. Kafka — только после появления нескольких независимых consumers, replay/analytics и operations owner; publisher подключается к существующему outbox.
