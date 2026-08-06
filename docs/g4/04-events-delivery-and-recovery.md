# G4 — события, доставка и восстановление

Статус: `ACCEPTED`, включая упрощение MVP-контура решением `PD-021`.
Документ объединяет прежние G4.6–G4.8 и сохраняет transport-neutral границу
ADR-015/ADR-017.

## Outbox (MVP-контур по PD-021)

Диаграммы:

- [outbox/inbox topology](diagrams/07-outbox-inbox-topology.mmd) — справочная
  полная топология; MVP использует только её подмножество;
- [delivery state](diagrams/07-delivery-state.mmd).

В MVP доставка строится на одной таблице `notification_outbox`:

| Поле | Назначение |
|---|---|
| `id` | идентификатор строки |
| `notification_id` | unique business key — одна строка на уведомление, дубли невозможны |
| `recipient_user_id` | получатель |
| `kind` | тип доставки (telegram/internal) |
| `payload` | безопасная ссылка на объект/action, без raw secrets/PII |
| `attempts`, `next_retry_at` | bounded retry |
| `expires_at` | срок актуальности; истёкшая строка не отправляется |
| `created_at` | время записи |

Owner transaction атомарно записывает state и outbox-строку. Worker забирает
bounded batch через `FOR UPDATE SKIP LOCKED`, отправляет через Telegram и
удаляет строку только после успеха. Crash до удаления приводит к повторной
отправке следующим запуском; unique business key гарантирует отсутствие
дублей-уведомлений.

## Retry (bounded)

- Retry — bounded exponential backoff + jitter, ограничен `expires_at`.
- Истёкшее уведомление не отправляется: продукт остаётся во внутреннем центре
  (PD-010), потеря Telegram-доставки принята.
- Task всегда повторно проверяет aggregate lifecycle/version.
- Payload хранит только safe target reference; переход к object или action
  screen всегда заново проходит permission check.
- Redis outage оставляет outbox pending; committed operation не откатывается.
- Celery task содержит ID/version, а не полную бизнес-запись.

Inbox-таблицы, receipts, dead-letter и административный retry одной записи в
MVP не вводятся (PD-021); их роль выполняют unique business key и повторный
идемпотентный запуск.

## Сверка (упрощено PD-021)

В MVP сверка — периодический контрольный запрос: «outbox-строки старше N минут
или с исчерпанными retry». Обнаруженные строки не переписываются автоматически:
записывается issue в метрику/лог для расследования. Ручное исправление
требует permission, reason, re-auth для опасного действия и privileged audit.

Полная таблица reconciliation (owner vs inbox, stale projection, rebuild) не
вводится до возврата слоя фактов перед публичным запуском.

## Retention и наблюдаемость

- Pending-строки хранятся до terminal resolution: успех → удаление,
  `expires_at` → удаление без отправки.
- Внутреннее уведомление остаётся в центре по правилам PD-014.
- Metrics: pending/oldest age, attempts, lease expiry и alert delivery.

Ни metric, ни log не содержит exact location, chat text, raw Telegram payload,
credential, reputation weights или original media.

## Kafka trigger

Kafka отсутствует в MVP. Возврат к нему допускается только при двух и более
независимых consumers, доказанной потребности replay/analytics, измеримом
outbox lag/load, capacity plan, operations owner и отдельном принятом ADR.
До этого publisher port остаётся PostgreSQL outbox + Celery delivery.
