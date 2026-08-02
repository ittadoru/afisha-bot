# G4 — события, доставка и восстановление

Статус: `ACCEPTED`. Документ объединяет прежние G4.6–G4.8 и сохраняет
transport-neutral границу ADR-015/ADR-017.

## Domain fact envelope

Каждый committed fact имеет:

| Поле | Правило |
|---|---|
| `event_id` | глобально уникальный ID факта |
| `event_type` | стабильное имя `{owner}.{fact}` |
| `schema_version` | положительная версия payload |
| `occurred_at` | UTC DB/server time |
| `aggregate_id/version` | owner aggregate и монотонная version |
| `correlation_id` | один пользовательский/операционный сценарий |
| `causation_id` | непосредственная команда/факт, если существует |
| `payload` | минимальный типизированный JSON без raw secrets/PII |

Payload schema additive внутри версии; breaking change получает новую версию.
Consumer обязан явно поддерживать версию или отправлять запись в controlled
dead-letter. Ordering гарантируется только для одного aggregate.

## Семейства фактов

- accounts: identity/profile/session lifecycle без credential contents;
- discovery: LookingPost, question/answer, conversion и safe projection lifecycle;
- events: publication/revision/cancellation, participation/waitlist/attendance;
- communication: notification/announcement/delivery terminal state;
- trust_safety: moderation/restriction/appeal safe facts;
- reputation: signal accepted/reversed и projection changed без policy internals;
- media: attachment ready/rejected/deleted.

Rejected command — analytics observation, а не committed domain fact.

## Outbox/inbox

Диаграммы:

- [outbox/inbox topology](diagrams/07-outbox-inbox-topology.mmd);
- [delivery state](diagrams/07-delivery-state.mmd).

Owner transaction атомарно записывает state и `outbox_fact`. Отдельные
`outbox_delivery` создаются по versioned routing registry для каждого
consumer. Dispatcher получает bounded batch через `FOR UPDATE SKIP LOCKED`,
lease/fencing token и fairness между priority classes.

Consumer:

1. проверяет envelope/version;
2. claim-ит unique inbox/dedup key;
3. применяет идемпотентное owner действие;
4. фиксирует receipt/checkpoint;
5. подтверждает delivery только после commit.

Crash до consumer commit повторяет работу; crash после commit определяется
inbox receipt и не повторяет side effect.

## Retry и dead-letter

- Retry bounded exponential backoff + jitter.
- Ошибка классифицируется как transient, permanent, expired или unsafe.
- Task всегда повторно проверяет aggregate lifecycle/version.
- Expired notification не отправляется после потери актуальности.
- Notification payload хранит только safe target reference; переход к object или
  action screen всегда заново проходит permission check.
- Permanent/исчерпавшая retry запись получает terminal dead-letter и safe
  reason code.
- Redis outage оставляет outbox pending; committed operation не откатывается.
- Celery task содержит ID/version, а не полную бизнес-запись.

Admin dead-letter projection не показывает payload по умолчанию. Moderator не
получает operations retry автоматически. Уполномоченный staff может retry
одну запись после re-auth и audit; bulk retry отсутствует в MVP.

Operations alert содержит только safe code, severity, component, timestamps,
count и opaque reference. Production Telegram receiver не настраивается в G6.

## Reconciliation

Reconciliation сравнивает owner truth с outbox/inbox/projection и создаёт
`issue`, а не молча переписывает бизнес-историю.

| Проверка | Безопасное восстановление |
|---|---|
| Owner state без expected fact | выпустить deterministic missing fact с unique key |
| Fact без consumer receipt | вернуть delivery в retry при истёкшем lease |
| Stale public projection | пересобрать из owner safe state |
| Notification без terminal state | повторить до expiry либо dead-letter |
| Attendance без reputation signal | применить только finalized outcome |
| Media/cleanup drift | повторить idempotent lifecycle command |

Ручное исправление требует permission, reason, re-auth для опасного действия и
privileged audit.

## Retention и наблюдаемость

- Pending/leased deliveries хранятся до terminal resolution.
- Terminal outbox/inbox сохраняются до установленного reconciliation window,
  затем compact/delete без удаления owner facts.
- Dead-letter сохраняется достаточно для расследования и не дольше
  применимого data retention.
- Metrics: pending/oldest age, attempts, lease expiry, dead-letter by safe
  reason, consumer lag, reconciliation issues и alert delivery.

Ни metric, ни log не содержит exact location, chat text, raw Telegram payload,
credential, reputation weights или original media.

## Kafka trigger

Kafka отсутствует в MVP. Возврат к нему допускается только при двух и более
независимых consumers, доказанной потребности replay/analytics, измеримом
outbox lag/load, capacity plan, operations owner и отдельном принятом ADR.
До этого publisher port остаётся PostgreSQL outbox + Celery delivery.
