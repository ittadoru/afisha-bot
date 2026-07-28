# Risks and specification audit

## Шкала

- `Critical` — возможен существенный вред людям/данным либо фундаментально неверная модель; блокирует проектирование.
- `High` — вероятна дорогая переделка, злоупотребление или системный сбой; правило нужно определить до соответствующего vertical slice.
- `Medium` — можно отложить при явном ограничении MVP и feature flag.
- `Low` — локальный долг с понятной коррекцией.

## Состояние рисков после решений 2026-07-28

| Риск | Новое состояние | Что уже решено | Что осталось |
|---|---|---|---|
| R-001 | `High`, accepted residual risk | адрес пользователя отсутствует; участники скрыты; место события настраивается | `EXACT_PUBLIC` выбран default, поэтому нужны заметный режим и предупреждение о необратимости раскрытия |
| R-002 | `Medium`, model resolved | interest, participation, waitlist и attendance разделены; confirmation удалено | формально утвердить ER/state machines в G4 |
| R-003 | `High`, частично снижен | РФ, три launch city, 14+, самодекларация, adult-only события запрещены | самодекларация не доказывает возраст; нужен safety/legal review до production |
| R-004 | `High`, accepted residual risk | SLA tiers, санкции, appeals и prohibited content определены | fallback через 3 часа проверяет только запрещённые слова; одна Emergency-жалоба не скрывает контент; нужны staffing и tooling |
| R-006 | `Medium`, mitigated | пороги приняты; место сохраняется; обязательное критическое уведомление | обеспечить revision/audit и заметный unread banner |
| R-007 | `Medium`, policy resolved | одна проверка через 6 часов; 3 разных лайка или 1 вступление; исключение для поздней публикации; per-city flag | измерять ошибочные скрытия и влияние на cold start |
| R-008 | `CLOSED for MVP` | minimum удалён | не реализовывать minimum trigger и UI |
| R-009 | `High`, технический | FIFO/timeout/rejoin правила приняты | обеспечить атомарность последнего места и waitlist offer |
| R-010 | `CLOSED` | minimum и confirmation notifications удалены | при переносе отправлять уведомление без CTA |
| R-011 | `High`, accepted residual risk | права чата и удаление через 24 часа после события приняты | даже открытая жалоба не продлевает текст; позднее расследование может остаться без доказательств |
| R-013 | `High`, policy resolved | два role-specific уровня, score 0–100, thresholds, sample и compensating signals определены | production weights и anti-abuse tuning после появления данных |
| R-015/R-016 | `High`, accepted residual risk | код действует start–end, 5 попыток, hash, one redemption и 24-часовой dispute | общий код разрешён для события любого размера и может быть передан внешним каналом |
| R-019 | `High`, accepted residual risk | конкретные сроки хранения и compaction определены | 24 часа для chat evidence, 90 дней для moderation audit и 14 дней backup требуют privacy/legal/restore проверки |
| R-020 | `CLOSED` | только организатор/модератор видят список; другие видят count; история участия непублична | negative authorization tests |

Раздел ниже сохраняет исходные findings аудита; приоритеты в таблице выше являются текущими.

## Исходный Critical/High baseline: продукт и предметная область

| ID / приоритет | Проблема и почему важна | Последствия | Рекомендация | Изменение спецификации |
|---|---|---|---|---|
| R-001 `Critical` | Спецификация не различала адрес пользователя и место события. Публикация домашнего адреса или точной позиции пользователя опасна. | stalking, незваные участники, раскрытие дома/маршрута, физический вред | Отдельные модели user discovery location и event location; user location никогда не публична | Да, до модели/API |
| R-002 `Critical` | `EventMembership` объединяет лайк, занятое место, waitlist, отмену и посещение (§24.1–24.2, стр. 29–30). Эти факты отвечают на разные вопросы. | невозможные состояния, потеря истории, неверные capacity/rating, трудно доказать спор | Разделить `Interest`, `Participation`, `WaitlistEntry/Offer` и будущий `Attendance` | Да |
| R-003 `Critical` | Не определены возрастная политика, правила для несовершеннолетних, допустимые типы встреч и launch jurisdiction, при этом продукт организует офлайн-встречи незнакомых людей (§22.2, стр. 26). | физический вред, невозможная moderation policy, ошибочные privacy/retention решения | До public launch определить minimum age, guardian/consent model или запрет minors, prohibited events, emergency/escalation policy, юрисдикцию и legal review | Да |
| R-004 `Critical` | Trust & Safety описан функционально, но без SLA, staffing, escalation, emergency cases и default-deny поведения для опасного контента (§21–22). Обязательное фото и чат умножают UGC. | опасное событие остаётся публичным; перегруз модерации; непоследовательные санкции | Закрытая alpha, pre/post moderation tiers, risk-based holds, immutable moderator audit, abuse throttling, emergency playbook и измеримый SLA | Да/операционная политика |
| R-005 `High` | В Приложении A есть `RECONFIRMATION_REQUIRED` и `LEFT`, которых нет в enum §24.2; событие одновременно описано как `completed`, `completion_pending`, `archived`. | разные реализации frontend/backend/jobs, застрявшие переходы | Удалить reconfirmation, разделить event lifecycle и moderation visibility, утвердить исчерпывающие enums/transitions | Да |
| R-006 `High` | Исходная спецификация требовала переподтверждение после критического изменения времени/места (§7.6), но это правило отменено решением PD-005. | без заметного уведомления люди могут приехать не туда; спорный no-show | Место сохраняется без нового действия пользователя; версионировать событие, вести immutable change log, заменять задачи старой версии и отправлять критическое уведомление без CTA | Да |
| R-007 `High` | Архивация через 60 минут без первого участника (§11.4–11.6) не определяет, кто считается участником: interest, approved application или joined. В cold start правило скрывает и без того редкий контент. | пустая карта, отрицательная петля ликвидности, случайное восстановление ботами | Считать разные сигналы отдельно; сделать правило city/category feature flag; в alpha отключить или увеличить TTL; восстановление не считать доказательством «реального» человека | Да |
| R-008 `High` | В исходной спецификации minimum, desired, capacity и «событие состоится» не были связаны формальной формулой. | ложные ожидания и неверные уведомления | Для MVP minimum полностью удалён; остаётся только capacity | Да |
| R-009 `High` | Вступление, waitlist и последнее место не имеют конкурентной семантики. | oversubscription, два победителя на одно место, ручные конфликты | DB constraint + транзакция/row lock; monotonic waitlist position; идемпотентный join; concurrency tests | Нет, если это техническое уточнение; публичные правила waitlist — да |
| R-010 `High` | Исходная матрица уведомляла об открытии подтверждения, хотя confirmation удалено. | неработающий CTA и spam | Удалить confirmation notification; при переносе отправлять сообщение без CTA | Да |
| R-011 `High` | Исходная спецификация не задавала права ленты после выхода, исключения, бана и завершения. | IDOR/утечка participant-only общения, harassment | Явный `ChatAccessGrant`; приняты правила немедленного revoke и 24-часового окна после добровольного выхода | Да |
| R-012 `High` | LookingPost допускает личный отклик/контакт (§8–9), но consent, rate limits, block и anti-harassment не определены. | нежелательные контакты, массовый spam, обход event moderation | Ответ как модерируемый объект; скрыть прямые контакты; mutual consent, per-user limits, block/report; конверсия в событие не переносит права автоматически | Да |
| R-013 `High` | Публичная репутация опирается на структурированные сигналы, но формула, confidence, период, appeal и cold-start не определены (§13). Популярность может незаметно влиять на доверие. | токсичный «социальный балл», дискриминация новичков, retaliatory reports, накрутка | В alpha — внутренний trust ledger без публичного общего score; показывать объяснимые факты с minimum sample; separate organizer/participant/event quality/popularity | Да |
| R-014 `High` | Репутацию и достижения можно накрутить сетью аккаунтов, фиктивными событиями и передачей attendance code. | уровни доверия теряют смысл | Signal history, account/event age, anomaly limits, unique pairs, delayed update, manual review и reversal после апелляции | Да |
| R-015 `High` | Общий шестизначный attendance code можно передать отсутствующему пользователю. | ложное посещение и необоснованный рост репутации | Joined-only redemption, короткое окно, attempt limits, one redemption и dispute; residual risk принят ради простоты | Да |
| R-016 `High` | При большом событии code быстро распространяется вне места встречи. | массовое ложное посещение | Ограничить attendance-code механику небольшими/средними событиями до появления более сильного способа | Да |
| R-017 `High` | Обязательное фото события (§6.2) могло содержать скрытый GPS/EXIF, поддельный формат или чрезмерный размер. | утечка данных, image bomb, сбой обработки, неприемлемый контент | Pillow-compatible decode, pixel/size limits, orientation normalization, WebP/JPEG re-encode, EXIF removal и премодерация | Да/техническая политика |
| R-018 `High` | Organizer одновременно может менять условия, подтверждать посещение и влиять на репутацию; conflict-of-interest и заблокированный organizer не описаны. | revenge no-show, hostage event, невозможность продолжить событие | Раздельные permissions, appeal, co-organizer/ownership transfer или safe cancellation, moderator override с audit; organizer claim не окончательный | Да |
| R-019 `High` | Нет retention/delete policy для точных координат, сообщений, attendance evidence, жалоб, raw Telegram/provider payloads и backups. | чрезмерное хранение PII, невозможность корректного удаления, потеря доказательств спора | Data classification + per-class retention; account deletion workflow; legal hold; redact/anonymize where possible; backup expiry verified | Да/политика |
| R-020 `High` | Публичный профиль мог раскрывать участие в конкретном событии. | deanonymization, social pressure, safety incidents | Публично показывать count без identities и никогда не публиковать историю участия пользователя | Да |

## Critical и High: безопасность и архитектура

| ID / приоритет | Проблема | Последствие | Контроль | Изменение спецификации |
|---|---|---|---|---|
| R-101 `Critical` | Доверие к `initDataUnsafe` или Telegram user id с клиента | account takeover, IDOR | Server-side signature verification, `auth_date` TTL, replay/session binding, internal user id | Нет; security requirement |
| R-102 `Critical` | Broken object-level authorization для event/chat/media/moderation endpoints | чтение точных мест и приватных сообщений, privilege escalation | Deny-by-default policy service; ownership/membership/version checks; negative permission tests | Нет |
| R-103 `High` | Webhook без secret/dedup | forged/duplicate updates, повторные команды | Secret header, allowlisted update types, unique `(bot_id, update_id)`, inbox record | Нет |
| R-104 `High` | Нет атомарной связи между state change и уведомлением/начислением | потерянное уведомление или двойной award | Transactional outbox, consumer inbox, unique business keys, reconciliation | Нет |
| R-105 `High` | Join, capacity, waitlist offer и edit могут выполняться конкурентно | два человека получают последнее место или одна резервация выдаётся дважды | transaction + lock/version check + constraint; scheduler rechecks state/version at execution | Нет |
| R-106 `High` | Deep link может ошибочно стать bearer-token | обход приватности или автоматическое вступление | Публичная ссылка только открывает публичную карточку, не несёт права/PII и не выполняет действие | Решено PD-015 |
| R-107 `High` | Фото/URL и AI/provider integrations создают SSRF/file risks | доступ к metadata/internal network, resource exhaustion | Не принимать arbitrary fetch URL; egress allowlist; size/time limits; sandboxed processing | Нет |
| R-108 `High` | XSS в описаниях/чатах внутри Telegram WebView | session/API abuse, phishing | Plain-text by default, allowlist sanitizer, CSP, output encoding, no raw HTML | Нет |
| R-109 `High` | Админка и moderation override без immutable audit | скрытое злоупотребление привилегиями | MFA/strong auth outside initData alone, least privilege, append-only audit, dual control for destructive actions | Нет |
| R-110 `High` | Telegram, геокодер и tile provider используются напрямую из domain/use-case | vendor lock-in и cascading failures | Ports/adapters, timeout, circuit breaker, cache/fallback, provider health metrics | Нет |
| R-111 `High` | Celery и Redis добавляются в MVP, а Kafka готовится архитектурно | двойная доставка outbox/task, потерянные задачи, две несогласованные retry-модели | PostgreSQL остаётся source of truth; outbox перед enqueue, стабильный idempotency key, тонкие Celery adapters, bounded retry/DLQ, Kafka отсутствует до ADR-017 trigger | Нет |
| R-112 `High` | Raw PII/координаты/token попадают в логи, traces и error tracking | необратимая утечка через observability | Structured allowlist logging, field redaction, pseudonymous IDs, sampling and access control | Нет |
| R-113 `High` | Резервные копии есть, но restore не тестируется | ложная уверенность; длительная потеря данных | Encrypted backups, isolated restore drills, measured RPO/RTO, alert on backup age | Нет |
| R-114 `High` | Supply-chain и container images не фиксированы | compromised dependency/build drift | uv lock, hashes where available, Dependabot/audit, SAST, secret scan, SBOM, pinned base digest, container scan | Нет |
| R-115 `High` | Шестизначный attendance code имеет только 1 млн комбинаций и может быть передан через другой мессенджер | brute force или ложное посещение | случайный server-generated code, joined-only access, короткое окно, ≤5 попыток на пользователя, per-IP/account rate limit, hash storage, one redemption; residual risk принят | Да |
| R-116 `High` | Cleanup удаляет детали до фиксации итогов репутации, апелляции или расследования | необратимая потеря доказательств и неверная статистика | compaction только после конечного state и применимого dispute window; транзакционный snapshot/outcomes, legal hold, idempotent deletion, reconciliation и audit удаления | Нет; data lifecycle control |
| R-117 `High` | На старте API, worker, Redis и PostgreSQL находятся на одном физическом сервере | одна поломка останавливает весь продукт и может уничтожить локальные backups | отдельные контейнеры/volumes, resource limits, наружу только 80/443, encrypted off-server backups, restore drill; разнос по ADR-018 | Нет; accepted staged deployment |
| R-118 `High` | Web OIDC и Mini App initData могут создать дубли профиля или принять поддельную identity | account takeover, разделённая история одного пользователя | официальный Telegram OIDC Code+PKCE, state/nonce/JWKS/iss/aud/exp validation; initData validation; единый identity-linking use case и unique Telegram subject | Нет |
| R-119 `High` | Точный адрес публичен по default или раскрыт нежелательному участнику | адрес можно сохранить/проиндексировать; последующее скрытие не возвращает секретность | заметный режим, manual visibility change, reminders, irreversible warning, no waitlist/interest access и audit | Да; residual risk принят |
| R-120 `High` | Публичная негативная отметка строится на малой выборке, ложных жалобах или одном инциденте | травля, ошибочная стигматизация и злоупотребление репутацией | role-specific level, minimum sample, finalized facts only, Bayesian smoothing, capped impact, decay/recovery, appeal/reversal и moderation override audit | Да, до reputation slice |
| R-121 `High` | Точная reputation/anti-fraud policy раскрывается через клиент, API, логи или публикацию в открытом репозитории | пользователи подстраивают поведение под thresholds и обходят защиту | policy port, защищённая production config вне Git, least-privilege access, redaction, secret scan и review изменений | Да |
| R-122 `High` | Закрытая admin-панель использует пароль без второго фактора | украденный пароль даёт доступ к moderation и privileged actions | закрытая саморегистрация, одноразовые приглашения, Argon2id, rate limit, generic errors, отдельные secure cookies, 8-часовой absolute/30-минутный idle timeout, re-auth опасных операций и privileged audit | Да; отсутствие MFA в MVP принято осознанно |

## STRIDE threat model: минимальный baseline

| Категория | Основные угрозы | Обязательные меры |
|---|---|---|
| Spoofing | forged initData/webhook, stolen session, подбор attendance-кода | signature/secret validation, expiry/replay controls, rate limits и one-redemption attendance |
| Tampering | изменение event version, attendance code/evidence/provider response, moderation decision | immutable revisions/evidence/audit, hashed code, rate limits, DB constraints |
| Repudiation | organizer отрицает перенос/отметку; moderator отрицает override | append-only audit with actor/time/request/event IDs |
| Information disclosure | exact coordinates, chat, EXIF, logs, attendee identity | field-level authorization, visibility projection, EXIF stripping, redaction, retention |
| Denial of service | autocomplete storms, map viewport abuse, bot broadcast, image bombs | per-key/risk rate limits, bbox/limit, backpressure, size/pixel caps, bounded queues |
| Elevation of privilege | IDOR, mass assignment, admin misuse, stale chat grant | explicit command DTOs, policy checks, deny-by-default RBAC/ABAC, revocation |

## Надёжность: failure catalogue

| Сбой | Симптом/последствие | Предотвращение и обработка | Восстановление/monitoring/тест |
|---|---|---|---|
| PostgreSQL недоступен | API writes fail; source of truth unavailable | readiness false, short timeouts, no unsafe local writes, connection backoff | DB availability/pool alerts; restore/failover drill |
| Redis недоступен | Celery enqueue/delivery останавливается; cache/rate-limit degradation | business transaction и outbox остаются в PostgreSQL; bounded reconnect, local conservative fallback или fail-closed для abuse-sensitive action | broker/error/outbox-age alert; restart Redis and replay test |
| Kafka недоступна (future) | outbox backlog grows | commit business tx to DB; publisher bounded retry; no request rollback after commit | outbox age/size alert; broker restore then replay |
| Worker остановлен | jobs/notifications delayed | heartbeat, leases with expiry, idempotent handlers | queue/outbox age alert; restart and replay test |
| Telegram API недоступен/429 | delayed/failed notifications | per-chat and global token buckets, honor `retry_after`, aggregation, bounded retry | delivery metrics/DLQ; replay before relevance deadline |
| Геокодер недоступен | не показывается подпись адреса выбранной точки | метку можно двигать; публикация блокируется до получения обязательного street/exact address; cached results и provider circuit breaker | provider health/error alert; recovery test |
| Tile provider недоступен | blank basemap | конфигурируемый provider, cached style, список событий с доступным адресом | synthetic map probe; failover test |
| AI provider недоступен | AI search fails | AI outside MVP/optional; structured search always available | error budget; fallback test |
| Upload interrupted | orphan multipart/quarantine object | staged upload session, checksum, expiry cleanup | orphan gauge; resume/cleanup test |
| Event saved, notification missing | users unaware | transactional outbox | reconciliation job; crash-after-commit test |
| Reputation/achievement twice | inflated trust | unique `(rule_version, subject, source_event)` and ledger | duplicate metric; replay property test |
| Проверка низкой активности одновременно с join | событие скрыто при фактическом участнике | lock/version check и повторная проверка participation/interest в одной транзакции | invariant monitor; concurrent integration test |
| Last place taken twice | capacity exceeded | atomic counter/constraint + lock; waitlist transaction | capacity invariant alert; two-client test |
| Invite reused | unauthorized joins | explicit reusable/single-use policy, atomic redemption, expiry/revoke | redemption audit; concurrent replay test |
| Event time changes после join | пользователь не заметил новые условия | immutable revision, критическое уведомление; дальнейшее поведение зависит от Q-005 | revision/change race test |
| Too many map markers | slow WebView/memory crash | bbox, zoom-dependent server cap/clusters/vector tiles | payload/latency metrics; dense-city load test |
| Autocomplete storm | quota/cost exhaustion | debounce, minimum chars, per-user quota, normalized cache, cancellation | provider quota alert; rapid-typing test |
| Hot city overload | DB/cache hot partitions | spatial index, query budget, cache tiles/clusters, city load metrics | p95 by city; skewed-load test |
| Broadcast spike | Telegram 429/backlog | priority classes, aggregation, schedule spreading, backpressure | backlog age/429 alert; mass-send simulation |
| Consumer redelivery | duplicate side effect | inbox/dedup key, idempotent state transition | redelivery counter; same-message test |
| Clock skew | wrong expiry/window | UTC server time, NTP monitoring, DB time for critical decisions, tolerance | clock-offset alert; skew test |
| Old task after cancellation | stale reminder/archive/checkin | task carries event revision; handler rechecks current lifecycle/version | stale-task metric; cancel-then-run test |

## Репутация и рекомендации: отдельные показатели

Нельзя сводить к одному числу:

| Показатель | Публичность на старте | Основание |
|---|---|---|
| Репутация организатора | ограниченные объяснимые факты после minimum sample | состоявшиеся события, точность описания, переносы, upheld complaints |
| Надёжность участника | после 5 событий; точный trust score приватен | своевременные/поздние отмены, неявки, confidence attendance |
| Качество события | агрегировано после minimum sample | оценки участников, moderation-adjusted feedback |
| Популярность | только discovery feature, не trust | views/interests/joins с anti-abuse |
| Персональная релевантность | внутренне | category/time/distance/preferences/feedback |
| Attendance confidence | сторонам спора и trust engine | независимые evidence signals |
| Challenge leaderboard | участникам челленджа | только challenge-specific verified progress |

Первый алгоритм рекомендаций должен быть детерминированным: eligibility/safety filter → selected city/time/category match → freshness → capacity/availability → bounded quality signals → diversity. Новичкам выделяется exploration quota; popularity не становится proxy доверия. Для будущего ML собираются impression/open/interest/join/attend/dismiss signals с position, candidate set, timestamp, city, consent и retention; embeddings используются только для semantic matching, не для trust score.

## Attendance: упрощённая модель MVP

- QR и geofence не используются.
- После начала события сервер создаёт случайный шестизначный code и хранит только его hash.
- Организатор сообщает code присутствующим голосом; participant-only лента уже read-only.
- Ввести code может только вступивший до начала пользователь.
- Code действует от начала до окончания; доступно пять попыток и один успешный ввод.
- Организатор не создаёт и не заменяет code.
- Остановка внутренней ленты не мешает передать code внешним способом, поэтому механизм намеренно считается менее надёжным.
- Отсутствие code создаёт предварительную неявку; dispute длится 24 часа.
- Attendance evidence хранится 30 дней после закрытия спора.

## Telegram и безопасность запросов

- `initDataUnsafe` не является аутентификацией; `auth_date` нужно проверять, но допустимый TTL продуктом не задан.
- Пользователь может запретить write access или заблокировать бота; это нормальное terminal delivery state, а не бесконечный retry.
- Бесплатная массовая отправка ограничена примерно 30 msg/s; в одном чате следует избегать >1 msg/s, в группе — >20/min. Нужны приоритеты, aggregation и expiry уведомления.
- Deep-link payload ограничен и не должен нести права/PII; объект может быть удалён, скрыт или просрочен к моменту открытия.
- LocationManager зависит от версии клиента/разрешения; всегда нужен ручной выбор точки.
- Quiet hours решено не вводить; marketing в MVP отсутствует.
- Каждый endpoint получает пользователя только из проверенной серверной сессии/initData, затем отдельно проверяет право на запрошенный объект.
- Join, exit, waitlist, media upload и webhook должны быть идемпотентными: повтор одного запроса не создаёт вторую запись.

## Текущее состояние репозитория

| Приоритет | Наблюдение | Эффект |
|---|---|---|
| High | `pytest` не запускается: в `addopts` указан `--cov`, но `pytest-cov` отсутствует | CI создаёт ложное ожидание тестового контроля |
| High | coverage target — `my_project`, а пакет называется `afishabot` | даже после установки plugin метрика будет неверной |
| Medium | Pyright работает в `standard`, хотя целевой стандарт — strict | будущие ошибки Optional/Any будут пропущены |
| Low | `pyproject.toml` содержит placeholder `Add your description here` | metadata пакета не отражает назначение проекта |
| Informational | Ruff/format/Pyright и `uv lock --check` проходят только на почти пустом scaffold | это не подтверждает архитектуру или runtime integration |

README и документация приведены к Python 3.14. Оставшиеся настройки каркаса сознательно не меняются до отдельного разрешения на infrastructure/code changes.
