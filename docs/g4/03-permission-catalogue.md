# G4.3 — Permission catalogue для moderator/admin и admin adapter

## Статус, цель и границы

- Статус: `ACCEPTED`
- Горизонт: MVP/alpha
- Владелец staff identity, permissions и privileged audit: `trust_safety`

Документ задаёт нормативные permission names, базовые role templates,
resource/scoping guards, re-authentication, separation of duties и правила
закрытого admin adapter.

Здесь не определяются UI закрытой панели, HTTP routes/status codes, ER-модель,
точные state machines moderation/appeal/attendance, production anti-fraud
policy, staffing schedule или полный security DFD. Permission разрешает
вызвать use case, но не заменяет guards состояния агрегата и бизнес-решение
модуля-владельца.

## Источники и приоритет

Источники применяются в порядке:

1. [PRODUCT_DECISIONS.md](../../PRODUCT_DECISIONS.md) — `PD-001…PD-019`;
2. [DECISIONS.md](../../DECISIONS.md) — принятые ADR;
3. [SOURCE_SPECIFICATION.md](../../SOURCE_SPECIFICATION.md) — только
   незаменённые части исходной спецификации.

[REQUIREMENTS_TRACEABILITY.md](../../REQUIREMENTS_TRACEABILITY.md) используется
для проверки покрытия, а
[CURRENT_SPECIFICATION_V1.md](../../CURRENT_SPECIFICATION_V1.md) — как читаемая
сводка. При новом конфликте двух `ACCEPTED` решений затронутая часть G4
останавливается до решения владельца.

## Нормативная модель авторизации

### Staff identity

- Staff identity не является пользовательской Telegram identity и не использует
  `accounts.User` для входа.
- Staff account имеет неизменяемый `staff_id`, отдельный login, Argon2id password
  hash, lifecycle, role label, versioned grants/revokes и timestamps.
- В MVP role label принимает только `moderator` или `admin`, но use cases не
  проверяют `role == ...`; они проверяют точный permission.
- Новая роль после MVP собирается из существующих permission names и scopes без
  изменения доменных use cases.
- Саморегистрации нет. Первый admin создаётся одноразовой server command,
  последующие сотрудники — только через приглашение активного admin.

### Permission decision

Каждое административное действие получает решение по кортежу:

```text
staff_id
+ active staff/session state
+ exact permission
+ current permission_version
+ scope
+ target/object guards
+ separation-of-duties guards
+ re-auth proof, если требуется
= allow или deny
```

Default — `deny`. Отсутствующий, неизвестный или отозванный permission никогда не
интерпретируется как более широкий. Wildcard grants вида `*` в persistence и
runtime запрещены.

### Effective permissions

```text
effective = baseline(role_template_version) + explicit_grants - explicit_revokes
```

- Role templates являются versioned server-side configuration.
- Explicit grant может ссылаться только на permission из этого каталога.
- Explicit revoke всегда сильнее baseline/grant.
- Изменение grants, revokes, role, scope или lifecycle увеличивает
  `permission_version` и немедленно инвалидирует sessions целевого staff.
- Admin не может менять собственные role/permissions или снять с себя
  ограничения; это делает другой active admin.
- Нельзя отключить последнего active admin с permission
  `staff.permissions.manage`.

## Scope model

Permission assignment содержит один из scopes:

| Scope | Значение |
|---|---|
| `self` | Только собственная staff session/credentials/audit |
| `case` | Только объект и связанные evidence, явно привязанные к назначенному moderation/appeal/dispute case |
| `city_set` | Только ресурсы указанных `city_id`; пустой набор ничего не разрешает |
| `global` | Все поддерживаемые города и очереди в рамках exact permission |

Baseline moderator grants могут быть ограничены `city_set`; baseline admin
grants имеют `global`. Permission с `case` не даёт права искать или просматривать
другие объекты того же пользователя. Scope сужает permission и не расширяет его.

## Staff authentication и sessions

| Контроль | Нормативное поведение |
|---|---|
| Origin/cookies | Admin использует отдельный origin, cookie name/session namespace и authentication flow |
| Password | Хранится только Argon2id hash; raw password запрещён в logs, audit и events |
| Invite | Single-use opaque token, срок не более 24 часов, хранится только hash; повтор/истечение отклоняются |
| Login errors | Одинаковое внешнее сообщение для неизвестного login и неверного password |
| Rate limit | Применяется по account/IP risk context; Redis может ускорять, но durable lock/audit не зависит только от Redis |
| Session lifetime | Absolute timeout 8 часов, idle timeout 30 минут |
| Cookie | `Secure`, `HttpOnly`, подходящий `SameSite`; state-changing requests защищены CSRF |
| Current state | Каждый запрос проверяет active staff, session, permission version и revoke state |
| Password change/reset | Завершает все sessions целевого staff и увеличивает credential/session version |
| Logout/revoke | Отзыв действует немедленно и fail-closed, даже если cache недоступен |

Точный password policy и transport/API-форма будут определены в security/API
контракте. G4.3 не вводит MFA и не заменяет обязательный password re-auth.

### Re-authentication

Опасная операция требует повторного ввода password после проверки основной
session.

Re-auth proof:

- живёт не более 5 минут;
- связан со `staff_id`, session, permission/action family и target либо
  idempotent batch;
- не переносится в другую session и не расширяет permissions;
- после password/session/permission change становится недействительным;
- отмечается в privileged audit только ID/время/результат, без password;
- для irreversible/override действия потребляется одним idempotent command.

Недоступность re-auth проверки означает deny. Опасную операцию нельзя сначала
выполнить, а потом «дописать» re-auth.

## Role templates

Обозначения:

- `B` — baseline grant role template;
- `G` — grantable отдельно active admin с `staff.permissions.manage`;
- `—` — роль не может получить permission в MVP.

| Permission group | Moderator | Admin | Основная граница |
|---|---:|---:|---|
| Собственная session/credentials/audit | `B` | `B` | Только `self` |
| Moderation queues и reversible decisions | `B` | `B` | `case` + optional `city_set` |
| Attendance disputes | `B` | `B` | Назначенный case |
| Safety appeals | `G` | `B` | Не исходный reviewer; override только admin |
| Temporary containment/restrictions | `B` | `B` | Предопределённые обратимые меры |
| Permanent restrictions/audited override | `—` | `B` | Re-auth + reason + audit |
| Staff lifecycle/permissions | `—` | `B` | Другой staff; last-admin guard |
| Catalog, official events и feature flags | `—` | `B` | Owner module guard + re-auth |
| Reconciliation/operations actions | `—` | `B` | IDs/versions, no raw payload |
| Operations bot alerts | `—` | `G` | Только active admin с явным grant |

Admin baseline не обходит object/state guards, retention, privacy или
fail-closed safety. Наличие admin role не означает универсальный read/export.

## Нормативный permission catalogue

Колонки:

- `Role` — допустимый template/grant;
- `Scope` — максимальный scope;
- `Re-auth` — требуется password re-auth;
- `Audit` — `basic`, `privileged` или `security`;
- `Owner` — application port, принимающий окончательное business decision.

### Собственная staff account и directory

| Permission | Role | Scope | Re-auth | Audit | Owner и допустимое действие |
|---|---|---|---:|---|---|
| `staff.session.read_self` | moderator `B`, admin `B` | `self` | нет | basic | `trust_safety`: показать собственные active sessions без cookie/token |
| `staff.session.revoke_self` | moderator `B`, admin `B` | `self` | нет | security | `trust_safety`: завершить выбранную или все собственные sessions |
| `staff.credentials.change_self` | moderator `B`, admin `B` | `self` | да | security | `trust_safety`: сменить собственный password и отозвать sessions |
| `staff.directory.safe_read` | moderator `B`, admin `B` | `global` | нет | basic | `trust_safety`: только `staff_id`, display label, role label и active state для assignment/conflict guard |
| `staff.audit.read_self` | moderator `B`, admin `B` | `self` | нет | basic | `trust_safety`: собственные security/privileged entries без чужих private details |

### Staff administration

| Permission | Role | Scope | Re-auth | Audit | Owner и допустимое действие |
|---|---|---|---:|---|---|
| `staff.account.list` | admin `B` | `global` | нет | basic | `trust_safety`: paginated safe staff directory |
| `staff.account.invite` | admin `B` | `global` | да | privileged | `trust_safety`: создать single-use invitation для moderator/admin с явными grants/scopes |
| `staff.account.suspend` | admin `B` | `global` | да | privileged | `trust_safety`: suspend/reactivate другого staff и отозвать его sessions |
| `staff.password.reset` | admin `B` | `global` | да | security | `trust_safety`: reset другого staff; self-target запрещён |
| `staff.session.revoke_any` | admin `B` | `global` | да | security | `trust_safety`: отозвать sessions другого staff |
| `staff.permissions.manage` | admin `B` | `global` | да | privileged | `trust_safety`: изменить role template assignment/grants/revokes/scopes другого staff |
| `staff.audit.read_all` | admin `B` | `global` | да | privileged | `trust_safety`: paginated privileged/security audit с минимизацией полей |

`staff.permissions.manage` не разрешает создавать новые permission strings,
назначать wildcard, менять себя или нарушать last-active-admin guard.

### System principals

Celery worker, Beat, Telegram webhooks, moderation fallback и reconciliation jobs
не являются staff accounts и не получают роли `moderator`/`admin`. Они вызывают
только явно разрешённые internal entry ports с service identity, source fact/task
ID и idempotency key.

Трёхчасовой moderation fallback может выполнить только принятый узкий
автоматический use case из `PD-008`: проверить текст по запрещённым словам,
убедиться в отсутствии блокировки автора и опубликовать ожидающее событие.
Service identity не может использовать произвольный staff permission,
permanent restriction, override или sensitive-read port.

### Moderation queues, content и cases

| Permission | Role | Scope | Re-auth | Audit | Owner и допустимое действие |
|---|---|---|---:|---|---|
| `moderation.queue.read` | moderator `B`, admin `B` | `city_set/global` | нет | basic | `trust_safety`: читать назначенные premoderation/complaint queues и SLA metadata |
| `moderation.event.read_sensitive` | moderator `B`, admin `B` | `case` | нет | privileged | `events` через admin adapter: moderation revision, protected location только при необходимости case |
| `moderation.event.decide` | moderator `B`, admin `B` | `case` | нет | privileged | `trust_safety`: approve/reject/hold event revision с normalized reason |
| `moderation.media.read` | moderator `B`, admin `B` | `case` | нет | privileged | `media`: только безопасный processed variant, связанный с case |
| `moderation.media.decide` | moderator `B`, admin `B` | `case` | нет | privileged | `trust_safety`: moderation decision; не меняет technical media readiness |
| `moderation.complaint.read` | moderator `B`, admin `B` | `case` | нет | privileged | `trust_safety`: жалоба и минимально необходимые evidence references |
| `moderation.complaint.decide` | moderator `B`, admin `B` | `case` | нет | privileged | `trust_safety`: uphold/reject/escalate с severity/reason |
| `moderation.content.hide` | moderator `B`, admin `B` | `case` | нет | privileged | `trust_safety`: немедленное fail-closed hide с reversible enforcement fact |
| `moderation.restriction.temporary` | moderator `B`, admin `B` | `case` | нет | privileged | `trust_safety`: только предопределённая ограниченная по времени мера |
| `moderation.emergency.contain` | moderator `B`, admin `B` | `case` | нет | security | `trust_safety`: немедленное reversible hide/temporary containment и escalation |
| `moderation.restriction.permanent` | admin `B` | `global` | да | privileged | `trust_safety`: permanent ban/restriction после current-state guard |
| `moderation.override` | admin `B` | `global` | да | privileged | `trust_safety`: audited override допустимого workflow decision с обязательной категорией причины |

`moderation.override` не разрешает публиковать запрещённый контент, раскрывать
private location/evidence, менять чужие таблицы, удалять audit, обходить
retention/legal hold или исполнять неизвестный переход.

`moderation.emergency.contain` не требует re-auth, потому что Emergency должен
останавливаться немедленно. Он разрешает только обратимую fail-closed меру;
permanent/override действие остаётся admin + re-auth.

### Appeals и attendance disputes

| Permission | Role | Scope | Re-auth | Audit | Owner и допустимое действие |
|---|---|---|---:|---|---|
| `moderation.appeal.read` | moderator `G`, admin `B` | `case` | нет | privileged | `trust_safety`: appeal и минимальные связанные решения/evidence |
| `moderation.appeal.decide` | moderator `G`, admin `B` | `case` | да | privileged | `trust_safety`: uphold/reverse/remand, по возможности не исходный reviewer |
| `attendance.dispute.read` | moderator `B`, admin `B` | `case` | нет | privileged | `events`: normalized attendance evidence без маршрута пользователя |
| `attendance.dispute.decide` | moderator `B`, admin `B` | `case` | нет | privileged | `events`: final `attended`/`neutral`/`no_show` с reason и expected version |

Если существует другой active staff с нужным permission/scope, исходный
moderation decision maker не решает appeal. Если его нет, только admin с
`moderation.override`, re-auth и объяснением может завершить case, чтобы workflow
не завис навсегда.

### Case-bound sensitive reads

| Permission | Role | Scope | Re-auth | Audit | Owner и допустимое действие |
|---|---|---|---:|---|---|
| `accounts.subject_safe_summary.read` | moderator `B`, admin `B` | `case` | нет | privileged | `accounts`: безопасный профиль/status без Telegram identity и private preferences |
| `events.private_location.read` | moderator `B`, admin `B` | `case` | да | privileged | `events`: точная location только если она необходима назначенному case |
| `communication.evidence.read` | moderator `B`, admin `B` | `case` | нет | privileged | `communication`: существующий retained text только по evidence reference |
| `reputation.private_summary.read` | moderator `B`, admin `B` | `case` | нет | privileged | `reputation`: разрешённый summary без weights, thresholds, raw signals и anti-fraud rules |

Эти permissions не разрешают bulk search/export. Открытая жалоба не продлевает
retention чата; отсутствующее по сроку evidence не восстанавливается из logs или
backup ради интерфейса модератора.

### Catalog, official events и configuration

| Permission | Role | Scope | Re-auth | Audit | Owner и допустимое действие |
|---|---|---|---:|---|---|
| `catalog.category.manage` | admin `B` | `global` | да | privileged | `discovery`: create/update/disable category с expected catalog version |
| `catalog.city.manage` | admin `B` | `global` | да | privileged | `discovery`: city/polygon/street configuration с validation/version |
| `catalog.geodata.verify` | admin `B` | `city_set/global` | нет | privileged | `discovery`: записать ручной результат проверки реальных точек |
| `events.public_event.manage` | admin `B` | `city_set/global` | да | privileged | `events`: создать/edit/cancel настоящий тип «Общественное событие» |
| `events.low_activity_flag.manage` | admin `B` | `city_set/global` | да | privileged | `events`: изменить per-city low-activity lifecycle flag |
| `reputation.reconcile` | admin `B` | `global` | да | privileged | `reputation`: запустить idempotent rebuild по subject/range/version |
| `reputation.policy.activate` | admin `B` | `global` | да | security | `reputation`: активировать заранее загруженный защищённый policy version только по ID |

Admin panel не читает и не редактирует production weights/thresholds или
anti-fraud rules. `reputation.policy.activate` работает только с opaque version
ID, доступным из защищённого deployment process.

### Operations

| Permission | Role | Scope | Re-auth | Audit | Owner и допустимое действие |
|---|---|---|---:|---|---|
| `ops.dead_letter.read` | admin `B` | `global` | нет | privileged | `communication`/owner query ports: safe metadata без полного payload/PII |
| `ops.dead_letter.retry` | admin `B` | `global` | да | privileged | Owner application port: retry по owner ID/version после current-state check |
| `ops.cleanup.retry` | admin `B` | `global` | да | privileged | Owner application port: идемпотентно повторить cleanup/compaction use case |
| `ops.nominatim.update` | admin `B` | `city_set/global` | да | security | Infrastructure adapter: запустить проверяемое regional update/rollback workflow |
| `ops.backup_status.read` | admin `B` | `global` | нет | privileged | Operations adapter: только status/age/result без credentials или backup contents |
| `ops_alerts.receive` | admin `G` | `global` | нет | security | `communication`: получать safe action-required alerts operations bot |

Operations bot не принимает административные команды. Permission
`ops_alerts.receive` только фильтрует получателей alerts и не выдаёт доступ к
admin panel или operations use cases.

Dead-letter retry не разрешает редактировать payload, recipient или системные
IDs. Bulk retry в MVP отсутствует; будущий batch потребует отдельного permission,
подтверждения и архитектурного решения.

## Admin adapter

Admin Frontend и backend admin adapter:

1. используют только отдельный admin origin/cookie/session namespace;
2. получают current `StaffAuthorizationContext` у `trust_safety`;
3. сопоставляют route/action с одним exact permission;
4. передают typed staff context, decision ID, permission version, scope,
   target ID, expected object version, reason и idempotency key;
5. вызывают один command port модуля-владельца;
6. могут компоновать несколько разрешённых query DTO, но не выполнять
   cross-schema SQL/ORM;
7. не копируют permission/policy rules во frontend;
8. не считают скрытую кнопку средством авторизации;
9. не принимают arbitrary table/model/action names;
10. не создают универсальный «admin bypass».

Frontend может использовать safe permission summary только для UX. Backend
повторно принимает решение на каждом request.

## Object и state guards

Permission является необходимым, но недостаточным условием. Owner port также
проверяет:

- target существует и относится к разрешённому scope/case/city;
- expected aggregate version актуальна;
- переход разрешён текущим state machine;
- decision reason входит в нормализованный catalogue;
- evidence ещё существует по retention и разрешён case;
- staff не является запрещённым original reviewer/self-target;
- irreversible action имеет re-auth;
- duplicate idempotency key возвращает прежний outcome, а не повторяет эффект;
- safety-sensitive dependency failure даёт deny/fail-closed.

Admin не может менять event/participation/reputation/media state прямым SQL.
Audited override остаётся application use case владельца и не создаёт
произвольный новый transition.

## Privileged audit

### События

Обязательно audit-ируются:

- login success/failure, logout, rate-limit/lock decision;
- invitation, password change/reset, session revoke;
- staff lifecycle, role/permission/scope change;
- re-auth success/failure;
- sensitive read и каждый moderation/appeal/attendance decision;
- temporary/permanent restriction, emergency containment и override;
- configuration, official event, reconciliation и operations action;
- denied privileged action, если запись безопасна и не создаёт abuse oracle.

### Минимальный audit record

| Поле | Правило |
|---|---|
| `audit_id`, time | Неизменяемый ID и server time |
| staff/session | `staff_id`, non-secret session reference, role/permission version |
| authorization | exact permission, scope, decision ID, re-auth used/time |
| action/target | normalized action, target type/internal ID/version |
| reason | normalized reason category; ограниченный safe comment при необходимости |
| outcome | allowed/denied/succeeded/failed + normalized reason |
| trace | request/correlation/causation/idempotency IDs |
| change | безопасный before/after summary или hashes, но не raw content/secrets |

Audit append-only. Исправление создаёт связанную compensating entry. Application
code не имеет permission удалить или переписать audit. Retention moderation и
privileged audit — 90 дней согласно `PD-014`; последующее удаление учитывает
legal hold и будет детализировано в data/retention G4.

Для privileged command audit гарантируется без общей межмодульной транзакции:

1. `trust_safety.StaffAccessCommands` атомарно записывает authorization
   decision/attempt и выдаёт `decision_id`;
2. owner command проверяет typed `StaffAuthorizationContext` и записывает
   business outcome + outbox fact с тем же `decision_id`;
3. `trust_safety` идемпотентно завершает audit по owner outcome fact;
4. reconciliation находит незавершённые decisions и сверяет их с owner facts.

Если первый audit decision или owner outbox невозможно надёжно записать,
privileged mutation не выполняется. Задержка финального consumer не откатывает
уже committed owner transaction, потому что outcome сохранён в outbox.

Запрещено записывать password, hash/token invite, session cookie, CSRF token,
raw Telegram auth artifacts, bot/client secrets, private message body без
необходимости, точные координаты как свободный текст, production reputation
weights или полный dead-letter payload.

## Failure semantics

| Ситуация | Результат |
|---|---|
| Staff/session inactive, expired или revoked | `staff_auth_required`; действие не начинается |
| Stale permission version | Session немедленно отклоняется и требует нового login |
| Permission отсутствует | `permission_denied`; target existence не раскрывается |
| Scope/case/city не совпадает | `scope_denied`; business data не возвращается |
| Требуется re-auth | `staff_reauth_required`; side effect отсутствует |
| Self/separation guard нарушен | `separation_of_duties`; side effect отсутствует |
| Target version/state устарели | `stale_version`/`conflict`; audit фиксирует safe outcome |
| Audit невозможно гарантировать для privileged command | Command fail-closed до owner mutation |
| Redis/cache недоступен | Current PostgreSQL staff/permission state остаётся authority |
| Owner module недоступен | Adapter не подменяет решение и не выполняет SQL fallback |

Ошибки являются внутренними typed results; HTTP mapping будет определён в
последующем API/security contract.

## Запрещённые возможности

- user Telegram identity как staff login;
- общий cookie/session namespace user/admin;
- authorization через role equality или видимость UI;
- wildcard permission и безусловный admin bypass;
- self-grant, self-role change или self-password reset через admin reset flow;
- отключение последнего active permission-managing admin;
- permanent restriction или override без re-auth/audit;
- bulk export private profiles, locations, messages, complaints или audit;
- чтение production reputation weights/anti-fraud rules из admin panel;
- прямые SQL/ORM/Redis mutations из admin adapter;
- удаление/перезапись privileged audit;
- administrative commands через operations bot.

## Traceability

| Область G4.3 | Источник |
|---|---|
| Две staff-роли, granular permissions, admin как adapter | `ADR-011`, `ADR-010` |
| Жалобы, премодерация, severity, sanctions и appeals | `PD-008`, `ADR-011` |
| Attendance dispute решает moderator | `PD-009`, `ADR-012` |
| Отдельная admin authentication boundary | `PD-013`, `PD-015`, `ADR-020` |
| Invitation, Argon2id, 8h/30m session, re-auth и audit | `ADR-020` |
| Internal user identity не заменяет staff identity | `PD-015`, `ADR-020` |
| Admin-only «Общественное событие» | `PD-003`, `PD-011` |
| City/geodata verification и Nominatim update | `PD-001`, `PD-017`, `ADR-014`, `ADR-019` |
| Fail-closed safety и владелец `trust_safety` | `PD-008`, `ADR-011` |
| Case-bound chat/location/profile privacy | `PD-002`, `PD-007`, `PD-017`, `ADR-014` |
| Reputation не блокирует и скрытая policy не раскрывается | `PD-009`, `PD-016`, `ADR-011` |
| Outbox/idempotency и отсутствие Redis authority | `PD-012`, `ADR-015`, `ADR-017` |
| Safe dead-letter/operations bot permissions | `PD-010`, `ADR-015` |
| 90-дневный moderation/privileged audit retention | `PD-014` |
| Public ports, staff context и owner transactions | `ADR-010`, [G4.2](02-module-boundaries-and-public-ports.md) |

## Acceptance checklist

- [x] Статус переведён в `ACCEPTED` после отдельного owner review.
- [x] Роли `moderator`/`admin` являются templates, а use cases проверяют exact
      permission.
- [x] Зафиксированы default deny, explicit grants/revokes и отсутствие wildcard.
- [x] Каждый permission имеет role, scope, re-auth, audit и owner action.
- [x] Moderator не получает permanent restriction, staff management или
      audited override.
- [x] Appeals поддерживают другого reviewer и безопасный admin fallback.
- [x] Admin не получает универсальный read/export/bypass.
- [x] Staff session отделена от user identity и ограничена 8h/30m.
- [x] Опасные действия используют 5-минутный bound re-auth proof.
- [x] Self-elevation, self-reset и удаление последнего admin запрещены.
- [x] Sensitive reads привязаны к case и минимизированы.
- [x] Admin adapter вызывает только public owner ports и не содержит SQL/ORM.
- [x] Privileged audit минимизирован, append-only и не содержит secrets.
- [x] Operations bot не выполняет admin commands.
- [x] Все ключевые правила имеют traceability к конкретным PD/ADR.
- [x] Не созданы ER-модель, state machines, HTTP API или production-код.
- [x] G4.3 checkbox и changelog принятия не изменялись до отдельного
      подтверждения владельца.
