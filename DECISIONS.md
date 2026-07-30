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
- После publication дата/начало/окончание суммарно меняются не более двух раз.
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

- Статус: `ACCEPTED`
- Business state и versioned outbox fact пишутся одной PostgreSQL-транзакцией.
- Consumer использует inbox/dedup, idempotent transition, bounded retry,
  dead-letter и reconciliation.
- Celery выполняет jobs через Redis broker; Redis и task state не являются
  business authority.
- FastAPI BackgroundTasks допустимы только для безопасно теряемого короткого
  эффекта.
- Publisher port остаётся transport-neutral для возможной Kafka.

## ADR-016 — compact history вместо полного event sourcing

- Статус: `ACCEPTED`
- CRUD/current state остаётся обычным; event sourcing не является общей моделью.
- Immutable revisions, audit, outbox и reputation signals сохраняются только
  там, где нужна доказуемость/rebuild.
- Terminal Event/LookingPost получает compact snapshot и normalized outcomes.
- Heavy intermediate text/provider payload/media удаляются по retention после
  dispute/legal-hold guards.
- Compaction/cleanup идемпотентны, наблюдаемы и проверяются reconciliation.

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
- Media — protected local filesystem через replaceable adapter, не DB binary.
- Alpha `RPO/RTO ≤24h`; encrypted backup database/media обязан уходить
  off-server и проходить restore drill.
- Следующий server появляется по DB RAM/IO/failure domain, worker/media
  CPU/RAM либо API connections/CPU, а не по календарю.

## ADR-019 — MapLibre и региональный геокодер

- Статус: `ACCEPTED`
- Map UI — MapLibre; browser получает OpenFreeMap vector tiles с attribution,
  configurable URL и list fallback. Public `tile.openstreetmap.org` запрещён.
- Event markers приходят только из API; hidden coordinates не уходят provider.
- Reverse geocoding — закрытый Nominatim 5.3.x с regional Dagestan extract;
  browser обращается через backend.
- Перед launch вручную проверяются реальные точки трёх cities. Updates —
  проверяемые ручные после жалоб/нового city с rollback набора.
- Через 500 мс после `moveend` выполняется reverse lookup; новое движение
  отменяет pending, stale response игнорируется.
- Нет text search; Photon рассматривается только при доказанной потребности.
- Собственные regional tiles — post-MVP на отдельном server и включаются config.

## ADR-020 — Telegram identity, не domain model

- Статус: `ACCEPTED`
- Все domain records используют internal immutable `user_id`; Telegram
  identity хранится отдельно с unique Telegram ID и OIDC issuer+subject.
- Server проверяет signed initData, auth_date и replay/session binding;
  webhook — secret header + update dedup.
- Website использует Telegram OIDC Code+PKCE с JWKS/iss/aud/exp/state/nonce и
  scopes `openid profile`; phone/write access не запрашиваются.
- Website/Mini App разрешаются одним identity use case; Telegram profile fields
  не перезаписывают публичный Afisha profile.
- Запуск/блокировка bot не запрещает действия; internal center/banner остаются
  fallback. Deep link не несёт PII/право.
- Identity transfer/recovery на новый Telegram account отсутствует в MVP.
- Website session rolling 30/absolute 90 дней; Mini — 24 часа.
- Staff auth отдельно: invite/bootstrap/reset, Argon2id, 8h absolute/30m idle,
  action re-auth, CSRF/rate limit/audit.
- User и operations bots имеют разные tokens/webhook secrets.

## ADR-021 — authoritative G6 gate на clean VPS

- Статус: `ACCEPTED`
- Authority — versioned script на clean exact-commit checkout resettable Ubuntu
  24.04 `linux/amd64` VPS.
- Gate проверяет locked dependencies, format/lint/types/tests/coverage,
  architecture, migrations/PostGIS, Redis/Celery, Nginx boundaries, security,
  SBOM/container/Compose smoke.
- Safe manifest связывает commit SHA, image digests, migration head, checks и
  result без env/secrets/PII/private policy.
- Финальные lock/digests создаются на VPS, коммитятся, затем проверяется новый
  clean exact commit.
- GitHub Actions — optional secret-free subset без deployment authority.
- Deployment manual-only; G6 не открывает traffic, public `80/443`, domains/TLS.
- Остальные migration/security/coverage/immutable-artifact правила G4 сохранены.
