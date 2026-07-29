# Architecture changelog

Все даты указаны в часовом поясе Europe/Moscow.

## 2026-07-29 — принят G4.16: Public-profile projection

### Принято

- Утверждена owner-local публичная profile projection со случайным неизменяемым
  восьмизначным public ID и collision-safe выдачей.
- Зафиксированы разные anonymous/authenticated/crawler projections,
  organizer-only indexing и запрет раскрытия участия через профиль.
- Принят общий пустой системный avatar и безопасный pipeline
  decode/crop/`256×256 WebP` без EXIF и публикации original.
- Утверждены exact authenticated lookup, enumeration controls, cache/privacy
  boundaries, fail-closed safety hide и асинхронное получение безопасных
  event/reputation summaries.

### Изменения системы

- Документ `docs/g4/16-public-profile-projection.md` переведён из `DRAFT` в
  `ACCEPTED`.
- Public-profile пункт в `IMPLEMENTATION_PLAN.md` отмечен завершённым.
- Production API/code/migrations не создавались; ReputationPolicy port
  остаётся следующим пунктом G4.

## 2026-07-29 — принят G4.15: Map legend, accessibility и approximate markers

### Принято

- Утверждён постоянный доступный map legend, различающий exact и approximate
  markers формой, подписью и screen-reader semantics, а не только цветом.
- Зафиксированы keyboard/touch/list parity, SSR text fallback и требования
  WCAG 2.2 AA без выбора production palette.
- Принят детерминированный street midpoint по канонической геометрии без
  использования скрытой event point, fake house или route.
- Утверждены fail-closed публикация при отсутствии valid street geometry,
  cache/privacy boundaries и пересчёт после обновления геоданных.

### Изменения системы

- Документ
  `docs/g4/15-map-legend-accessibility-and-approximate-markers.md` переведён
  из `DRAFT` в `ACCEPTED`.
- Map legend/approximate-marker пункт в `IMPLEMENTATION_PLAN.md` отмечен
  завершённым.
- Production UI/code/migrations не создавались; public-profile projection
  остаётся следующим пунктом G4.

## 2026-07-29 — принят G4.14: Exact-location projection и reveal matrix

### Принято

- Утверждены три режима location visibility: `STREET_ONLY`,
  `EXACT_PARTICIPANTS` и `EXACT_PUBLIC`, с caller-safe street/exact
  projections и явным подтверждением первичной публичной публикации.
- Зафиксирован participant reveal receipt на каждый participation episode:
  interest, waitlist и offer не дают exact access, а выход, исключение и отмена
  закрывают дальнейшую выдачу немедленно.
- Принят fail-closed public-hide barrier до смены owner mode, исключающий окно
  раскрытия через устаревшую discovery projection.
- Утверждены cache/provider/SEO/notification boundaries, street-only
  reminders, безопасный audit и street-only итоговая публичная карточка.

### Изменения системы

- Документ `docs/g4/14-exact-location-projection-and-reveal.md` переведён из
  `DRAFT` в `ACCEPTED`.
- Exact-location пункт в `IMPLEMENTATION_PLAN.md` отмечен завершённым.
- Production code/migrations не создавались; legend/accessibility contract и
  deterministic street anchor остаются G4.15.

## 2026-07-29 — принят G4.13: Admin authentication flow

### Принято

- Утверждена отдельная `trust_safety` staff identity/password boundary для
  `moderator` и `admin`, не связанная с Telegram user identity.
- Зафиксированы one-time bootstrap command, 24-часовые invitations,
  30-минутные password resets, Argon2id profile и password policy.
- Приняты PostgreSQL-authoritative admin sessions с 8-часовым absolute и
  30-минутным idle timeout, отдельным host-only cookie/CSRF namespace и
  пятиминутным action-bound re-auth.
- Утверждены durable throttling, generic anti-enumeration errors,
  last-active-admin guard, immediate revocation и append-only security audit.

### Изменения системы

- Документ `docs/g4/13-admin-authentication-flow.md` переведён из `DRAFT` в
  `ACCEPTED`.
- Admin authentication пункт в `IMPLEMENTATION_PLAN.md` отмечен завершённым.
- Production auth code/migrations и MFA не создавались; exact-location
  projection/reveal matrix остаётся следующим пунктом G4.

## 2026-07-29 — принят G4.12: Telegram identity, session и replay model

### Принято

- Утверждена owner-local модель `accounts.telegram_identity`, физически
  уточняющая conceptual `ExternalIdentity` без отдельной пользовательской
  Telegram domain identity.
- Зафиксированы application AEAD для provider user IDs и versioned
  domain-separated HMAC для equality lookup; raw provider/session/CSRF/auth
  artifacts не сохраняются.
- Приняты раздельные website/Mini sessions, PostgreSQL-authoritative
  validation, rotation/revocation, OIDC claim fence, Mini bootstrap/replay
  guard и короткие сроки retention.
- Утверждены atomic identity resolution, one-to-one Telegram binding,
  fail-closed conflict, `/start` без создания User и запрет перезаписи Profile
  Telegram claims.

### Изменения системы

- Документ `docs/g4/12-telegram-identity-session-replay-model.md` переведён из
  `DRAFT` в `ACCEPTED`.
- Telegram identity/session/replay пункт в `IMPLEMENTATION_PLAN.md` отмечен
  завершённым.
- Production migrations/code и staff authentication не создавались;
  отдельный admin authentication flow остаётся следующим пунктом G4.

## 2026-07-29 — принят G4.11: Web и Mini App authentication flow

### Принято

- Утверждены раздельные website OIDC Authorization Code + `S256` PKCE и
  Mini App `initData` flows, разрешаемые в один immutable internal `user_id`.
- Зафиксированы single-use `state`/nonce/code, JWKS/claims validation,
  HMAC/freshness/replay guards и отсутствие доверия к `initDataUnsafe`.
- Приняты отдельные website/Mini session types и cookie namespaces:
  website — rolling idle 30 дней и absolute 90 дней, Mini App — absolute
  24 часа с обновлением только через новое valid `initData`.
- Утверждены exact Origin + session-bound CSRF, безопасный return intent без
  auto-action, fail-closed identity conflict и запрет перезаписи публичного
  профиля Telegram claims.

### Изменения системы

- Документ `docs/g4/11-web-mini-app-authentication-flow.md` переведён из
  `DRAFT` в `ACCEPTED`.
- Web/Mini App auth-flow пункт в `IMPLEMENTATION_PLAN.md` отмечен завершённым.
- Physical identity/session/replay tables, production auth code и admin flow
  не создавались; Telegram identity model остаётся следующим пунктом G4.

## 2026-07-29 — принят G4.10: deployment topology, backups и migration

### Принято

- Утверждены этапы размещения на одном, двух и трёх core servers, а также
  отдельный post-MVP geo server при переходе с hosted tiles на собственный
  vector tile stack.
- Зафиксированы Docker/private network boundaries: только reverse proxy
  публикует `80/443`, а application, data, operations и backup flows остаются
  в закрытом контуре.
- Принят ежедневный restore point с инкрементальным/deduplicated media backup
  вместо ежедневной полной копии, 14-дневным хранением, еженедельной проверкой
  и ежеквартальным restore drill; alpha targets — `RPO ≤ 24 часа`,
  `RTO ≤ 24 часа`.
- Утверждены staged migrations `1 → 2 → 3`, восстановление Redis из
  authoritative PostgreSQL/outbox, переключение media через adapter,
  fencing, validation gates и rollback conditions.

### Изменения системы

- Документ `docs/g4/10-deployment-topology-and-migration.md` переведён из
  `DRAFT` в `ACCEPTED`.
- Deployment topology пункт в `IMPLEMENTATION_PLAN.md` отмечен завершённым.
- Production infrastructure, providers, domains и auth flows не создавались;
  Web/Mini App authentication остаётся следующим самостоятельным пунктом G4.

## 2026-07-29 — принят G4.9: Kafka-readiness matrix

### Принято

- Подтверждено отсутствие Kafka в MVP и сохранение PostgreSQL
  state+outbox transaction как единственной producer atomic boundary.
- Утверждены transport-neutral `EventPublisherPort`, one-publication-per-stream,
  per-consumer inbox/ack и at-least-once semantics без ложного exactly-once.
- Зафиксированы topic-family/privacy/order/ACL principles и current/previous
  schema compatibility без выбора production vendor/topology.
- Приняты обязательные prerequisites и шесть измеримых demand triggers для
  отдельного Kafka adoption ADR.
- Утверждены shadow, analytics canary, sequential single-writer cutover,
  safety-critical gate, route fencing, rollback, replay и reconciliation.

### Изменения системы

- Документ `docs/g4/09-kafka-readiness-matrix.md` переведён из `DRAFT` в
  `ACCEPTED`.
- Kafka-readiness пункт в `IMPLEMENTATION_PLAN.md` отмечен завершённым.
- Kafka cluster/topics/ACLs/code/migrations не создавались; deployment
  architecture остаётся следующим самостоятельным пунктом G4.

## 2026-07-29 — принят G4.8: dead-letter operations и безопасные alerts

### Принято

- Утверждены безопасный dead-letter admin read model без raw payload, PII,
  secrets и provider bodies, а также отдельные permissions для read и retry.
- Зафиксирован только одиночный owner-controlled retry с re-auth,
  current-state/version/hash/order guards, идемпотентностью и privileged audit;
  bulk/edit/manual resolve отсутствуют.
- Operations bot остаётся outbound-only, имеет отдельные credentials,
  namespaces и personal-chat enrollment через одноразовый outbound challenge.
- Получатель обязан одновременно быть active admin, иметь current
  `ops_alerts.receive`, verified binding и enabled subscription.
- Critical/action-required alerts отправляются сразу, informational — ежедневным
  digest; доставка ограничена восемью попытками, expiry и anti-recursion.

### Изменения системы

- Документ `docs/g4/08-dead-letter-operations-alerts.md` переведён из `DRAFT` в
  `ACCEPTED`.
- Dead-letter/operations alerts пункт в `IMPLEMENTATION_PLAN.md` отмечен
  завершённым.
- Operations-bot ingress/commands, bulk actions, production code/migrations и
  Kafka не создавались.

## 2026-07-29 — принят G4.7: transactional outbox/inbox и reconciliation

### Принято

- Утверждены owner-local `outbox_fact`, per-consumer `outbox_delivery`,
  `inbox_receipt`, ordering checkpoints и reconciliation metadata без
  cross-schema JOIN/transaction.
- Зафиксированы at-least-once delivery, атомарные producer/consumer
  транзакции, отдельный acknowledgement, lease/fencing и fair dispatcher с
  `FOR UPDATE SKIP LOCKED`.
- Приняты bounded retry defaults, terminal/dead-letter/replay guards,
  30/60/90-дневные retention windows и controlled consumer decommission.
- Каталогизированы reconciliation jobs для delivery/inbox/order,
  safety/public projections, LookingPost, attendance/reputation,
  notifications, media/compaction и account erasure.
- Redis/Celery остаются transport, PostgreSQL — authoritative state; временная
  недоступность transport/provider не откатывает owner transaction.

### Изменения системы

- Документ `docs/g4/07-outbox-inbox-and-reconciliation.md` переведён из
  `DRAFT` в `ACCEPTED`.
- Пункт transactional outbox/inbox и reconciliation в
  `IMPLEMENTATION_PLAN.md` отмечен завершённым.
- Dead-letter admin workflow, operations bot safe alerts, Kafka и production
  migrations/code не создавались.

## 2026-07-29 — принят G4.6: Domain Event Catalogue

### Принято

- Утверждены transport-neutral envelope v1, per-aggregate ordering,
  at-least-once delivery, inbox/domain deduplication и immutable compensation.
- Каталогизированы 69 typed domain facts/analytics observations для семи owner
  modules с producer, trigger, minimal payload v1, consumers, retry и retention.
- Зафиксированы bounded retry classes, expiry/stale/dead-letter/replay semantics
  и compatibility current/previous schema versions.
- Protected location, private text/media, credentials и production policy
  internals исключены; `EXACT_PUBLIC` point разрешён только public card
  projection.
- Analytics observations не получают command authority, а transfer интересов
  LookingPost выполняется отдельным идемпотентным fact на пользователя.

### Изменения системы

- Документ `docs/g4/06-domain-event-catalogue.md` переведён из `DRAFT` в
  `ACCEPTED`.
- Пункт Domain Event Catalogue в `IMPLEMENTATION_PLAN.md` отмечен завершённым.
- Physical outbox/inbox, reconciliation jobs, Kafka и production schemas не
  создавались.

## 2026-07-29 — принят G4.5: API contracts и request security

### Принято

- Утверждены логические public/user/admin/webhook route families и их mapping на
  public application ports без создания production OpenAPI или FastAPI-кода.
- Зафиксированы единый safe error envelope, stable error codes, cursor
  pagination, optimistic concurrency и обязательная idempotency mutations.
- Разделены anonymous, Website, Mini App, admin и Telegram webhook identity,
  session, CSRF/origin/replay и cache boundaries.
- Все 45 staff permissions сопоставлены admin route/protocol families с
  re-auth, scope, object/state guards и audit requirements.
- Exact location, safety и chat access работают fail-closed; user-bot webhook
  изолирован от operations bot.

### Изменения системы

- Документ `docs/g4/05-api-contracts-and-request-security.md` переведён из
  `DRAFT` в `ACCEPTED`.
- Пункт API contracts/error/idempotency/authorization matrix в
  `IMPLEMENTATION_PLAN.md` отмечен завершённым.
- Production-код, OpenAPI и domain-event payload schemas не создавались.

## 2026-07-29 — принят G4.4: data model, state machines, retention и compaction

### Принято

- Утверждены логическая ER-модель и schema ownership семи доменных модулей,
  canonical final Event snapshot и normalized ParticipationOutcome.
- Зафиксированы lifecycle, moderation visibility, participation/waitlist,
  attendance, moderation report и notification delivery автоматы; Challenge
  нормативно оставлен deferred до решения `Q-019`.
- Каждый переход имеет actor, guard, forbidden semantics, side effects/audit и
  recovery; PostgreSQL остаётся единственным authority для переходов.
- Приняты раздельные retention classes, account anonymization и идемпотентный
  compaction с final-state, dispute/legal-hold и reconciliation guards.
- Утверждён минимальный analytics/quality contract без фиксации production
  event payloads или закрытых policy values.

### Изменения системы

- Документы `docs/g4/04-data-model-retention-compaction.md` и
  `docs/g4/04-state-machines.md` переведены из `DRAFT` в `ACCEPTED`.
- Связанные ER, state-machine, transition, analytics и compaction пункты в
  `IMPLEMENTATION_PLAN.md` отмечены завершёнными.
- Production-код, HTTP API schemas и domain-event payloads не создавались.

## 2026-07-29 — принят G4.3 permission catalogue

### Принято

- Утверждены 45 exact permissions для `moderator`/`admin`, versioned role
  templates, explicit grants/revokes и default-deny evaluation.
- Staff identity, password authentication и sessions полностью отделены от
  пользовательской Telegram identity.
- Зафиксированы scopes `self/case/city_set/global`, object/state guards,
  separation of duties и отсутствие wildcard/admin bypass.
- Опасные действия требуют связанного с session/action re-auth proof и
  append-only privileged audit; moderator ограничен обратимыми мерами.
- Admin adapter вызывает только public owner ports, а service principals и
  operations bot не получают staff permissions.

### Изменения системы

- Документ `docs/g4/03-permission-catalogue.md` переведён из `DRAFT` в
  `ACCEPTED`.
- Permission-catalogue пункт в `IMPLEMENTATION_PLAN.md` отмечен завершённым.
- Production-код, ER-модель, state machines и API-контракты не изменялись.

## 2026-07-29 — принят G4.2: модульные границы и public ports

### Принято

- Зафиксированы семь доменных модулей, их PostgreSQL schema ownership и единый
  минимальный каркас `public/application/domain/infrastructure/adapters`.
- Утверждён строгий ациклический граф синхронных межмодульных зависимостей;
  обратные реакции выполняются через versioned facts и идемпотентный inbox.
- `trust_safety` выдаёт единый итоговый safety decision, `admin` остаётся
  adapter, а analytics consumer не получает command authority.
- Каталогизированы внешние и межмодульные capability ports, правила read
  composition, shared kernel, owner transactions и fail-closed safety.
- Нормативный Markdown содержит текстовые альтернативы, а два отдельных Mermaid
  source-файла совпадают со встроенными диаграммами.

### Изменения системы

- Документ `docs/g4/02-module-boundaries-and-public-ports.md` переведён из
  `DRAFT` в `ACCEPTED`.
- Пункт модульных границ в `IMPLEMENTATION_PLAN.md` отмечен завершённым.
- Production-код, permission catalogue, ER-модель и state machines не
  изменялись.

## 2026-07-29 — принят G4.1 C4 System Context и Container

### Принято

- Архитектурные границы Afisha зафиксированы на уровнях C4 System Context и
  Container для MVP/alpha на одном физическом сервере.
- Public Web, Telegram Mini App и Admin Frontend являются отдельными containers
  с разными runtime/authentication boundaries.
- Reverse Proxy остаётся единственной публичной точкой входа; PostgreSQL/PostGIS,
  Redis, media storage и Nominatim находятся во внутренних защищённых зонах.
- Браузер получает только публичные style/vector tiles напрямую от OpenFreeMap;
  event payload, приватный контент и координаты событий провайдеру не передаются.
- Пользовательский и operations bots разделены по credentials и сценариям, а
  внешние backups покидают первый физический сервер только в зашифрованном виде.

### Изменения системы

- Документ `docs/g4/01-c4-context-containers.md` переведён из `DRAFT` в
  `ACCEPTED`.
- Пункт C4 в `IMPLEMENTATION_PLAN.md` отмечен завершённым.
- Production-код, ER-модель, API-контракты и state machines не изменялись.

## 2026-07-28 — завершён полный аудит ADR-000, ADR-001 и ADR-010…ADR-020

### Принято

- Все 13 существующих ADR последовательно уточнены и сохраняют статус `ACCEPTED`; отсутствующие номера `ADR-002…ADR-009` не создавались.
- Архитектурный gate требует и согласованного пакета `G4`, и подробного плана `G5`; production-код начинается только после отдельной однозначной команды, записанной в changelog.
- Репозиторий публичный. В Git разрешены только безопасные контракты, документация и примеры; секреты, production-конфигурация и закрытые anti-fraud/reputation правила остаются вне него.
- Модульный монолит получил правила владения PostgreSQL schemas/migrations, межмодульных портов, outbox-взаимодействия и минимального shared kernel.
- Уточнены participation episodes, одновременные FIFO offers, attendance dispute, одна ожидающая модерации revision, optimistic concurrency и 90-дневное сворачивание подробной истории переносов.
- Для геоданных закреплены city polygon, стабильная опорная точка улицы и защита точных координат через сеть, права, шифрование носителей/backups и redaction.
- Outbox проверяет актуальность версии, использует разные ограниченные retry policies и сроки dead-letter. JSON facts валидируются версионируемыми Pydantic-схемами.
- MVP/alpha работает через Docker Compose на одном сервере; media хранится в защищённой локальной директории за adapter, Nominatim — в отдельном закрытом контейнере. Приняты `RPO ≤ 24 часа` и `RTO ≤ 24 часа`.
- Nominatim обновляется вручную после обоснованных жалоб и перед добавлением города. Готовность города подтверждает ручная проверка администратора без обязательного числового порога.
- Website-сессия: rolling 30 дней с абсолютным пределом 90 дней; Mini App: 24 часа с обновлением через свежий `initData`.
- Запуск пользовательского бота не блокирует функции сайта. Сайт предлагает открыть его при первом важном действии, а до этого использует внутренний notification center и critical banners.
- Закрытая панель использует отдельные логины/пароли, одноразовые приглашения, Argon2id, восьмичасовую сессию, 30-минутный idle timeout, повторную проверку опасных операций и privileged audit.
- Создан читаемый актуальный снимок спецификации `v1.0`; исходная спецификация и источники отдельных PD/ADR не заменены.

### Изменения системы

- Изменены только Markdown-документы.
- Production-код и неизменяемая копия исходной спецификации не изменялись.
- Из `DECISIONS.md` удалён целиком заменённый снимок продуктовых решений от 2026-07-26; актуальные `PD-001…PD-019` сохранены без изменений в `PRODUCT_DECISIONS.md`.
- `OPEN_QUESTIONS.md` сокращён до незакрытых категорий и двух вопросов `DEFERRED`; закрытые ответы остаются в PD/ADR и истории.
- Удалён дублирующий `PROJECT_CONTEXT.md`, а его актуальная ссылка в матрице заменена на читаемую спецификацию v1.0.
- В `CURRENT_SPECIFICATION_V1.md` добавлены правила холодного старта и административного типа «Общественное событие».

## 2026-07-28 — полный аудит PD-001…PD-019

### Принято

- Актуальные продуктовые правила вынесены в `PRODUCT_DECISIONS.md`; снимок от 2026-07-26 сначала был помечен `SUPERSEDED`, а позднее удалён из активного `DECISIONS.md`.
- Исходная спецификация 0.9 сохранена целиком в `SOURCE_SPECIFICATION.md`; все 28 её разделов связаны с текущими решениями в `REQUIREMENTS_TRACEABILITY.md`.
- Исправлена нумерация: принятый выбор MapLibre, OpenFreeMap и собственного регионального Nominatim оформлен как `ADR-019`.
- Репозиторий публичный; production-секреты хранятся только в secret manager, а чувствительная policy не попадает в Git и не отдаётся клиенту.
- Первые города — Махачкала, Хасавюрт и Дербент; возраст 14+ подтверждается самодекларацией без даты рождения.
- Attendance-код, предварительная неявка, два публичных role-specific уровня, скрытые звёзды и автоочистка через 6 часов включены в MVP.
- Q&A заменён простым текстовым polling-чатом. Чат и объявления удаляются через 24 часа после окончания события.
- Для нового организатора принят ручной moderation path с автоматическим текстовым fallback через 3 часа.
- Утверждены конкретные retention-сроки, default `EXACT_PUBLIC`, web-сессия 30 дней и внутренняя first-party аналитика.
- Для стартового наполнения добавлен admin-only тип «Общественное событие» без вступления, чата, attendance и reputation.
- Уточнён ADR-013: после публикации место и категория неизменяемы; лимит двух переносов относится только к дате, началу и окончанию.

### Принятые остаточные риски

- Текстовый fallback не заменяет ручную проверку содержания и фотографий.
- Открытая жалоба не продлевает 24-часовое хранение чата.
- Точный адрес публичен по умолчанию и может быть сохранён или проиндексирован до последующего скрытия.
- Общий шестизначный код применяется к событиям любого размера и может быть передан внешним каналом.

## 2026-07-28 — единая Telegram identity

### Принято

- Mini App `initData` и website OIDC связываются с одним внутренним `user_id`; бизнес-таблицы не используют Telegram ID как primary identity.
- Обычный website-вход запрашивает только `openid` и `profile`; номер телефона и bot write access при входе не запрашиваются.
- Telegram name, username и picture не копируются в публичный профиль и не перезаписывают псевдоним/аватар Afisha.
- Отказ разрешить bot direct messages не блокирует приложение; используется внутренний notification center и banner fallback.
- В MVP нет ручного восстановления или переноса профиля на новый Telegram-аккаунт.
- Пользовательский и operations bots полностью разделены по tokens, webhook secrets, сценариям и deduplication; секреты и raw auth artifacts запрещены в логах и публичном Git.

## 2026-07-28 — надёжная доставка и operations bot

### Принято

- Изменение бизнес-состояния и outbox event записываются одной транзакцией PostgreSQL; временная недоступность Redis/Celery/Telegram не откатывает успешное действие.
- Просроченные уведомления не отправляются, retry ограничены, а неисправимые актуальные задачи переходят в dead-letter и доступны только в закрытой admin-панели.
- Отдельный закрытый operations bot немедленно сообщает о критических/action-required dead-letter и объединяет некритические случаи в digest.
- Оповещения получают только активные `admin` с permission `ops_alerts.receive`; bot не выполняет административные команды.
- Alert DTO не содержит PII, точных адресов, приватного контента, секретов или полного payload. Токен хранится только в secret storage/runtime environment вне публичного Git.

## 2026-07-28 — карты и региональный геокодер

### Принято

- В MVP MapLibre работает в браузере и получает vector tiles напрямую с публичного OpenFreeMap; event markers приходят только с моего API.
- Принимаются ограничения OpenFreeMap: attribution, отсутствие SLA/поддержки/гарантий и возможность прекращения сервиса без уведомления. Style URL остаётся заменяемой конфигурацией.
- Nominatim с данными Дагестана разворачивается как мой закрытый внутренний сервис на первом сервере. До запуска выполняются региональный импорт и ручная проверка реальных точек администратором.
- Место выбирается центральной event marker без ручного ввода адреса; reverse geocoding запускается через 500 мс после остановки карты.
- После MVP собственные региональные vector tiles размещаются на отдельном сервере. Переключение выполняется конфигурацией без изменения бизнес-логики.
- Photon отложен до подтверждённой необходимости текстового поиска с подсказками.

## 2026-07-28 — карта города и комплексный холодный старт

### Принято

- «Рядом со мной», адрес и геолокация пользователя исключены из MVP; хранится только выбранный город, на котором открывается карта.
- Скрытые события одной улицы показываются общей street marker-плашкой, а не случайными точками отдельных событий.
- Обычные и street markers не кластеризуются в MVP даже на масштабе города; кластеризация добавляется только при измеримой плотности.
- Холодный старт решается комплексно через LookingPost, предварительное привлечение настоящих организаторов, поэтапное продвижение городов, историю завершённых событий, показ всего города и полезное пустое состояние.
- Поддельные события и искусственная активность запрещены; здоровье предложения измеряется отдельно по городам, категориям и периодам.

## 2026-07-28 — итоговая проекция событий и LookingPost

### Принято

- Текущая запись события после завершения становится итоговой; отдельная полная архивная копия не создаётся.
- Точный итоговый адрес сохраняется с прежними правами доступа и не заменяется геоячейкой.
- Для отклонённых и заблокированных объектов долгосрочно остаются факт и нормализованная причина решения, но не фотографии и другой тяжёлый контент.
- Для LookingPost сохраняются итог, полезные действия и связь с созданным событием; текст, media и временные записи удаляются по срокам.
- Compaction выполняется повторяемо и проверяет, что итоговые факты и аналитические агрегаты не потеряны.

## 2026-07-28 — единый стандарт качества данных

### Принято

- Значимые действия во всех частях продукта сохраняются по единым версионируемым контрактам, а не в виде несогласованных логов.
- Запись содержит точное время, actor/subject, источник, результат и причину, связи запросов, версию схемы и при необходимости прежние/новые существенные значения.
- Дубли блокируются, исправления оформляются компенсирующими записями, а агрегаты получают версию расчёта и могут быть сверены с исходными фактами.
- Операционные данные, security audit и аналитика разделяются по назначению и срокам хранения.
- Высокое качество данных не отменяет минимизацию: приватные координаты, PII, raw payloads, технический шум и тяжёлые файлы не копируются и не хранятся бессрочно без необходимости.
- Контракты готовы к будущей передаче через Kafka и в отдельное аналитическое хранилище; в MVP источником истины остаётся PostgreSQL с outbox.

## 2026-07-28 — версии и переносы события

### Принято

- После публикации место неизменяемо; дату, начало и окончание можно переносить суммарно не более двух раз, а одно сохранение нескольких временных полей считается одним переносом.
- После второго переноса дальнейшее изменение даты, времени и места запрещено. Раскрытие уже сохранённого точного адреса не считается сменой места.
- Категория опубликованного события неизменяема.
- Предыдущие версии описания временно сохраняются только для модерации и жалоб и не показываются пользователям.
- Уведомление об изменении отправляется через Telegram-бота, а внутренний центр остаётся резервом на случай недоставки.

## 2026-07-28 — модульный монолит

### Принято

- Backend реализуется как одно развёртываемое приложение с семью изолированными доменными модулями, общим PostgreSQL и явными application-портами.
- API, Celery worker и scheduler могут запускаться отдельными процессами или контейнерами, но остаются частями одного проекта.
- Отдельные микросервисы выделяются позднее только при подтверждённой независимой нагрузке или организационной необходимости.

## 2026-07-28 — скрытая оценка события

### Принято

- После события доступна только добровольная оценка `1–5` звёзд; текст и теги отсутствуют.
- Звёзды и среднее значение не показываются пользователям и слабо влияют на reputation/event quality.
- До attendance-code учитывается оценка пользователя, занимавшего место на старте, с меньшим confidence; позднее больший вес имеет подтверждённый посетитель.

## 2026-07-28 — правила премодерации организатора

### Принято

- В MVP остаются только moderator и admin; будущие дополнительные роли пока не вводятся.
- Обязательная премодерация нового организатора снимается после 3 успешных событий без серьёзных подтверждённых нарушений.
- Она возвращается при уровне «Низкая надёжность» или upheld safety complaint независимо от рейтинга.
- Количество отзывов влияет на confidence публичного уровня, но не на снятие обязательной премодерации.
- Формат event review вынесен в Q-031.

## 2026-07-28 — принят ADR-011

### Принято

- MVP состоит из семи доменных модулей: accounts, discovery, events, communication, trust_safety, reputation и media.
- Admin — отдельный закрытый adapter без собственной копии бизнес-логики.
- В MVP две роли: moderator и admin; внутри используются granular permissions для будущего расширения.
- События новых организаторов обязательно проходят премодерацию.
- Reputation входит в MVP отдельным модулем; игровые achievements/challenges остаются отдельным post-MVP модулем.

## 2026-07-28 — легенда карты и четыре уровня репутации

### Принято

- Под главной картой всегда отображаются triangle/approximate и rounded/exact markers с текстовым объяснением.
- Approximate marker стабильно выбирается по street geometry и hash события/улицы; случайный номер чужого дома не создаётся.
- Публичных уровней репутации четыре: низкая, обычная, надёжная и высокая; `Новый пользователь` — отдельный статус.
- Репутация хранится как типизированный числовой component vector + materialized projection, а не embedding.
- Public repository содержит ReputationPolicy port и demo policy; production thresholds/weights и sensitive anti-fraud rules остаются вне Git.

## 2026-07-28 — два уровня адреса и публичные псевдонимы

### Принято

- У места остаются только два уровня отображения: улица без дома и точный адрес; район/город как отдельные режимы удалены.
- Организатор переключает общий режим: street-only, exact для всех вступивших или exact для всех посетителей.
- Индивидуальной выдачи адреса нет; будущий вступивший автоматически следует текущему режиму события.
- Предварительное направление UI: triangle для approximate street marker и rounded pin для exact location; алгоритм approximate marker остаётся Q-028.
- Имя сначала генерируется случайно, затем меняется пользователем; дубликаты разрешены, имя автора сообщения видно другим.

## 2026-07-27 — полноценный web, публичный профиль и раскрытие адреса

### Принято

- До входа доступны карта, события, invite link и профиль организатора; после Telegram-авторизации сайт предоставляет полный пользовательский функционал.
- Публичный профиль содержит имя, `256×256 WebP` avatar без EXIF/original, случайный восьмизначный ID, bio, reputation level и будущие medals.
- Организатор обязательно задаёт точный адрес и выбирает публичную проекцию: город, район, улица или exact; venue/landmark отображается отдельной понятной подписью.
- Exact location раскрывается вручную только текущим участникам; automatic reveal отсутствует.
- При скрытом exact location Celery напоминает организатору за 3 часа, 1 час и 15 минут проверить участников и решить вопрос раскрытия.
- Полный participant list видят только организатор и moderator.
- Требование заметной негативной reputation mark принято, но названия, minimum sample и границы вынесены в Q-026 из-за риска ошибочной стигматизации.

## 2026-07-27 — Kafka-ready, Celery и поэтапное развёртывание

### Принято

- Kafka не входит в MVP, но domain-event envelope, transactional outbox и publisher port позволяют подключить её без изменения бизнес-логики.
- Решение о Kafka принимается по outbox lag/fan-out, числу независимых consumers, replay и нагрузке PostgreSQL; обычная медленная операция сама по себе не является trigger.
- Celery 5.6 и Redis broker включены в MVP для уведомлений, media processing, cleanup и periodic jobs.
- На старте все компоненты запускаются в отдельных контейнерах на одном физическом сервере; затем PostgreSQL, worker и API разносятся по измеримой причине.
- Анонимный посетитель адаптивного сайта может просмотреть публичное событие. Любые действия требуют Telegram Login.
- Для сайта выбран официальный Telegram OIDC Authorization Code Flow с PKCE; Mini App и сайт создают один внутренний профиль.
- Публичный сайт, интерактивное приложение/API и закрытая панель модератора разделяются по origin/subdomain.

## 2026-07-27 — компактная долгосрочная история

### Принято

- Завершённое/отменённое событие хранит долгосрочно только итоговые факты и нормализованные связи, необходимые истории, репутации, достижениям и аналитике.
- Организатор, участники, outcomes вступления/посещения, отмены/неявки, финальные время/место/категория, отзывы и reputation links сохраняются без дублирования профилей.
- Черновики, несущественные текстовые revisions, временная геолокация, истёкшие technical records и media после заданного срока удаляются либо сворачиваются в агрегаты.
- Compaction запускается только после конечного состояния и применимого окна спора; moderation/security evidence и legal hold очищаются отдельно.
- Архив хранения завершённых событий не включает отключённую автоархивацию пустых событий и не раскрывает публично историю участия.
- Конкретные сроки остаются `BEFORE SLICE` и требуют privacy/legal review.

## 2026-07-27 — закрытие продуктового gate

### Принято

- Confirmation/reconfirmation полностью удалены; критический перенос не освобождает место и требует только заметного уведомления.
- «Рядом со мной»: приватный ввод адреса/места либо геолокация устройства; публичный домашний адрес отсутствует.
- Future attendance упрощён до случайного шестизначного code; QR и geofence удалены.
- Лента события становится read-only с момента начала события.
- Публичная репутация показывает только уровень; число, формула и метрики скрыты.
- Текущий reputation state материализуется в отдельной записи и обновляется по событиям; история сохраняется для аудита/пересчёта.
- Фото декодируется open-source библиотекой, ограничивается, сжимается, пересохраняется в WebP/JPEG и очищается от EXIF.
- Защита каждого запроса и минимизация пользовательских действий закреплены как обязательные принципы.
- Redis и Celery внесены в обязательный post-MVP backlog; Kafka оставлена за измеримым trigger.

### Geo recommendation

- MapLibre GL JS + публичный OpenFreeMap для tiles.
- Собственный Nominatim на региональном OSM extract для forward/reverse geocoding.
- Photon добавляется только при подтверждённой потребности в autocomplete.

### Gate

- Блокирующих продуктовых вопросов больше нет.
- Следующий разрешённый этап — архитектурный пакет G4 без production-кода.

## 2026-07-26 — ответы владельца продукта

### Принято

- Несколько городов Республики Дагестан, РФ, возраст 14+.
- Непубличное местоположение пользователя и непубличная история участия; настраиваемая видимость места события.
- Только бесплатные безопасные события и фиксированный список категорий.
- Minimum удалён из MVP; автоматическая архивация пустых событий выключена в alpha.
- Определены пороги критического переноса, FIFO waitlist, timeout, rejoin и поздняя отмена.
- Определены права participant-only ленты после выхода, исключения, бана и завершения.
- Приняты manual premoderation alpha, severity/SLA tiers, prohibited content, appeals и emergency flow.
- Attendance и публичная репутация отложены; принято направление будущей multi-signal проверки и пороги публичности рейтинга.
- Приняты классы уведомлений, отсутствие quiet hours и обязательный in-app fallback.
- Утверждён уменьшенный MVP и Python 3.14; Kafka, Celery и Redis отложены.

### Осталось

- Один конфликт: существует ли подтверждение участия и что происходит с местом после критического переноса.
- На тот момент оставались сроки хранения, реализация 14+ policy, frontend stack, способ проверки геоданных и storage фотографий; все эти пункты позднее закрыты отдельными решениями.

### Изменения системы

- Изменены только служебные Markdown-файлы.
- Production-код и каноническая спецификация не изменялись.

## 2026-07-26 — начальная фиксация аудита

### Состояние

- Каноническая спецификация полностью прочитана и визуально проверена.
- Изучен существующий каркас репозитория.
- Выполнена первичная проверка совместимости предлагаемого стека с Python 3.14.
- Выполнено исследование Telegram Mini Apps, карт, тайлов и геокодеров по первичным источникам.
- Production-код не создавался и не изменялся.

### Предложения, ожидающие согласования

- Модульный монолит как начальная архитектура.
- PostgreSQL + PostGIS как источник истины и географическое ядро.
- Обычная GIL-сборка CPython 3.14; не использовать `3.14t` в MVP.
- Transactional outbox с первого функционального вертикального среза.
- Не вводить Kafka и Celery в MVP без измеримой причины.
- Redis вводить только при появлении конкретной межпроцессной задачи.
- MapLibre GL JS и заменяемые порты для карт/геокодинга.
- Разделить намерение, заявку, участие, подтверждение и посещение на самостоятельные записи/состояния.

### Причина

Спецификация задаёт богатую предметную область, но часть жизненных циклов и правил безопасности не определена. Фиксация архитектуры до ответов на блокирующие вопросы создала бы скрытые продуктовые решения и дорогую переделку.

### Изменения исходной спецификации

Нет. Все найденные расхождения и предложения вынесены в служебные файлы.
