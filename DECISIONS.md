# Decisions

Статусы: `ACCEPTED`, `PROPOSED`, `REJECTED`, `SUPERSEDED`. Реализуются только
`ACCEPTED`. Консолидация текста не меняет смысл или статус решений.

## ADR-000 — сначала анализ, затем согласование

- Статус: `ACCEPTED`
- Production-код разрешён только после принятых G4/G5 и отдельной однозначной
  команды владельца; начало этапа фиксируется в changelog.
- До разрешения допустимы docs и изолированные prototypes, не импортируемые
  production packages.
- Необходимое security/infrastructure исправление без business logic возможно
  только с зафиксированной причиной.
- Владелец разрешил начать G6 2026-07-30; Slice 1 требует отдельного clean G6.

## ADR-001 — неизменный источник требований

- Статус: `ACCEPTED`
- Исходный DOCX не изменяется без прямого разрешения владельца; полная
  безопасная Markdown-копия хранится в `SOURCE_SPECIFICATION.md`.
- Новое `ACCEPTED` решение заменяет только конкретную конфликтующую часть.
  Остальное исходное требование продолжает действовать.
- Конфликт двух `ACCEPTED` решений останавливает затронутую работу до ответа
  владельца; дата или тип PD/ADR не определяют победителя.
- `REQUIREMENTS_TRACEABILITY.md` связывает 28 пакетов требований с решениями.
  `CURRENT_SPECIFICATION_V1.md` — читаемый обзор, не новый источник.
- Перед slice требования превращаются в acceptance criteria/tests без
  додумывания. Нерешённое противоречие фиксируется новым `OPEN_QUESTIONS.md`;
  пустой файл постоянно не хранится.
- Secrets, PII и закрытые anti-fraud/reputation rules не попадают в Git.

## ADR-010 — модульный монолит

- Статус: `ACCEPTED`
- Один deployable backend, общий PostgreSQL и явные application ports.
- Каждый модуль владеет schema/migrations; чужие таблицы и ORM недоступны.
- Ведущий use case атомарно изменяет owner state и пишет outbox fact; реакции
  после commit идемпотентны.
- Shared kernel содержит только IDs, время, ошибки, envelope и transaction
  protocols, без общих business rules.
- Несколько API/worker/beat containers не являются микросервисами. Выделение
  сервиса допускается только по независимому масштабу или команде.

## ADR-011 — семь модулей MVP

- Статус: `ACCEPTED`
- Модули: `accounts`, `discovery`, `events`, `communication`, `trust_safety`,
  `reputation`, `media`.
- Admin — закрытый adapter; business logic остаётся у owner-модулей.
- Роли MVP: `moderator` и `admin`, но backend проверяет permissions/scope, а не
  только role.
- Achievements/challenges не смешиваются с reputation и после MVP получают
  отдельную границу.
- Public map читает safe discovery projection; safety hide закрывает её
  fail-closed.
- Только `trust_safety` блокирует/ограничивает; `reputation` лишь вычисляет.
- Object owner хранит attachment ID/role/order, а media владеет file lifecycle.

## ADR-012 — разделённое участие

- Статус: `ACCEPTED`
- Interest, participation episode, waitlist entry/offer, attendance redemption
  и attendance decision — отдельные записи.
- Confirmation/reconfirmation отсутствует; join сразу занимает место.
- Одновременно разрешён один active episode для user/event; повторный join
  создаёт новый episode, но reputation outcome события остаётся один.
- Освободившиеся `N` мест атомарно резервируются первым `N` подходящим FIFO
  entries отдельными timed offers.
- Без code возникает preliminary no-show без немедленного штрафа. Dispute —
  24 часа; moderator решает `confirmed`, `neutral` или `no_show`.

## ADR-013 — Event revisions

- Статус: `ACCEPTED`
- Event хранит lifecycle, существенные изменения — immutable `EventRevision`.
- После publication дата/начало/окончание суммарно меняются не более одного раза.
  Point/address/category неизменяемы; visibility того же адреса менять можно.
- Participation сохраняется при revision; critical change уведомляется без
  reconfirmation.
- Одновременно одна pending moderation revision; публична последняя approved.
- Edit передаёт expected version; stale update возвращает conflict.
- Old/new details хранятся 90 дней, затем остаются compact move facts.

## ADR-014 — PostgreSQL/PostGIS с первого slice

- Статус: `ACCEPTED`
- PostgreSQL — truth; event point — `geography(Point,4326)` + GiST.
- Point, provider suggestion, normalized address, provider/place ID,
  locale/precision, visibility и canonical street geometry различаются.
- Выбранная marker point — truth; Nominatim только объясняет адрес. Ручного
  ввода/текстового address search в MVP нет.
- Publish разрешён внутри approved city polygon.
- User location/«Рядом со мной» в MVP отсутствуют.
- Street marker строится без hidden event point; exact выдаётся caller-specific
  projection.

## ADR-015 — transactional outbox

- Статус: `ACCEPTED — MVP-контур упрощён решением PD-021`
- Business state и outbox fact пишутся одной PostgreSQL-транзакцией.
- MVP-контур: одна таблица `notification_outbox`; unique business key на
  `notification_id` исключает дубли; consumer — bounded retry с TTL и удаление
  успешной строки; восстановление после сбоя — повторный идемпотентный запуск.
- Inbox/dedup-таблицы, dead-letter и reconciliation-задачи в MVP не вводятся.
- Celery выполняет jobs через Redis broker; Redis и task state не являются
  business authority.
- FastAPI BackgroundTasks допустимы только для безопасно теряемого короткого
  эффекта.
- Publisher port остаётся transport-neutral для возможной Kafka.

## ADR-016 — compact history вместо полного event sourcing

- Статус: `ACCEPTED — очистка упрощена решением PD-021`
- CRUD/current state остаётся обычным; event sourcing не является общей моделью.
- Immutable revisions, audit, outbox и reputation signals сохраняются только
  там, где нужна доказуемость/rebuild.
- Итоговые факты хранятся в операционных таблицах: строка Event, одна
  последняя одобренная revision и строки участия не удаляются.
- Очистка — простой идемпотентный sweep: повторяемые `DELETE` батчами по
  `delete_after`/срокам; legal-hold и защита споров/жалоб — условие
  `NOT EXISTS` по открытым case. Отдельный compaction-механизм с расписками,
  агрегатами и reconciliation не вводится.

## ADR-017 — Kafka-ready без Kafka

- Статус: `ACCEPTED`
- В MVP Kafka отсутствует; PostgreSQL outbox + Celery/Redis достаточно.
- Envelope имеет stable IDs/type/version, aggregate ordering,
  correlation/causation и typed JSON payload.
- Kafka требует ≥2 независимых consumers или доказанный replay/analytics,
  измеримый lag/load, capacity plan, operations owner и отдельный ADR.
- Kafka не используется как Celery broker; cutover/rollback проектируются
  только после trigger.

## ADR-018 — поэтапная инфраструктура

- Статус: `ACCEPTED`
- Development/integration и MVP/alpha используют Compose; Kubernetes — только
  при нескольких instances/servers и реальной scheduling/HA потребности.
- Stage 1: proxy/frontends/API/worker/beat/PostgreSQL/PostGIS/Redis/Nominatim/
  local media на одном физическом сервере в раздельных containers/networks.
- Наружу в production только `80/443`; data services private.
- На этапе A внешний host Nginx принимает `80/443` и передаёт `podvval.xyz`
  во внутренний Nginx на `127.0.0.1:8080`. Маршруты: `/` — лендинг,
  `/app` — демонстрация Mini App, `/api` — пользовательский API.
- `admin.podvval.xyz` получает HTTPS, но до реализации admin отвечает `404`.
  Telegram bot, Nominatim и monitoring на этапе A не запускаются.
- Media — protected local filesystem через replaceable adapter, не DB binary.
- Alpha `RPO/RTO ≤24h`; encrypted backup database/media хранятся локально на VPS
  7 дней (PD-021) и проходят restore drill; off-server требование отложено и
  зафиксировано как остаточный риск `R-113`.
- Следующий server появляется по DB RAM/IO/failure domain, worker/media
  CPU/RAM либо API connections/CPU, а не по календарю.

## ADR-019 — MapLibre и региональный геокодер

- Статус: `ACCEPTED`
- Map UI — MapLibre; browser получает OpenFreeMap vector tiles с attribution,
  configurable URL и list fallback. Public `tile.openstreetmap.org` запрещён.
- Event markers приходят только из API; hidden coordinates не уходят provider.
- Reverse geocoding — закрытый Nominatim 5.3.x с региональным extract по bbox
  трёх городов и запасом примерно 20 км (PD-021); browser обращается через
  backend.
- Перед launch вручную проверяются реальные точки трёх cities. Updates —
  проверяемые ручные после жалоб/нового city с rollback набора.
- Через 500 мс после `moveend` выполняется reverse lookup; новое движение
  отменяет pending, stale response игнорируется.
- Нет text search; Photon рассматривается только при доказанной потребности.
- Собственные regional tiles — post-MVP на отдельном server и включаются config.

## ADR-020 — Telegram identity, не domain model

- Статус: `ACCEPTED`
- Все domain records используют internal immutable `user_id`; Telegram
  identity хранится отдельно с unique Telegram ID.
- Server проверяет signed initData, auth_date и replay/session binding;
  webhook — secret header + update dedup.
- В MVP user identity создаётся или находится только по проверенному Mini App
  `initData`. Website OIDC отложен за рамки MVP; публичный сайт не создаёт
  пользовательскую сессию.
- Telegram profile fields не перезаписывают публичный Afisha profile.
- Запуск/блокировка bot не запрещает действия; internal center/banner остаются
  fallback. Deep link не несёт PII/право.
- Identity transfer/recovery на новый Telegram account отсутствует в MVP.
- Mini App session живёт 24 часа.
- Staff auth отдельно: invite/bootstrap/reset, Argon2id, 8h absolute/30m idle,
  action re-auth, CSRF/rate limit/audit.
- Первый владелец с логином `Atari` один раз создаётся из `.env`, затем хранится
  в PostgreSQL. Пароль добавляется только вместе с реализацией admin-панели и
  позднее меняется через неё; moderators создаются и хранятся в базе.
- User и operations bots имеют разные tokens/webhook secrets.

## ADR-021 — authoritative G6 gate на clean VPS

- Статус: `ACCEPTED`
- Authority — versioned script на clean exact-commit checkout resettable Ubuntu
  24.04 `linux/amd64` VPS.
- Gate проверяет locked dependencies, format/lint/types/tests/coverage,
  architecture, migrations/PostGIS, Redis/Celery, Nginx boundaries, security,
  Compose smoke. Coverage alpha — не ниже 60%; SBOM и container scan выполняются
  только перед первым публичным выпуском (PD-021).
- Safe manifest связывает commit SHA, image digests, migration head, checks и
  result без env/secrets/PII/private policy.
- Финальные lock/digests создаются на VPS, коммитятся, затем проверяется новый
  clean exact commit.
- GitHub Actions — optional secret-free subset без deployment authority.
- Deployment manual-only; G6 не открывает traffic, public `80/443`, domains/TLS.
- Остальные migration/security/coverage/immutable-artifact правила G4 сохранены.

## ADR-022 — Stage A: конфигурация и серверный выпуск

- Статус: `ACCEPTED`
- Локальная машина используется только для правок файлов, просмотра diff и
  Git-операций. Dependencies, builds, tests, migrations и Compose запускаются
  только на Ubuntu 24.04 VPS.
- Проверяемые адреса задаются как `AFISHA_PUBLIC_BASE_URL=https://podvval.xyz`,
  `AFISHA_MINI_APP_URL=https://podvval.xyz/app` и
  `AFISHA_ADMIN_BASE_URL=https://admin.podvval.xyz`.
- `TG_PROXY_URL` необязателен: пустое значение означает прямое подключение к
  Telegram, заполненное — подключение через указанный proxy.
- `.env` не хранится в Git, переносится на VPS отдельно и доступен только root.
- Stage A не добавляет product tables, user auth, настоящий admin или bot
  runtime. Его назначение — clean exact-commit G6, core Compose и HTTPS-каркас.
