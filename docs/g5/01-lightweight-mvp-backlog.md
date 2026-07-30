# G5 — облегчённый MVP backlog

Статус: `ACCEPTED`, подтверждено владельцем 2026-07-30. Документ не вводит
новых PD, ADR, API или моделей данных.

## Выпуски

- `MVP-0`: G6 + Slice 1–4, только непубличное окружение; доказать путь
  login → карта → создание → moderation → публичная карточка.
- Первый выпуск: все девять срезов, обычный доступ без рекламы; 3–5 помощников,
  отдельные admin/moderator accounts, подготовлены Махачкала, Хасавюрт и
  Дербент.
- Post-demand: clustering, расширенный chat, собственные tiles, дополнительные
  servers, marketing и Kafka — только по принятым triggers.
- Data-dependent: AI/ML, achievements/challenges и production reputation tuning
  — после достаточной реальной истории и отдельного решения.

## Девять срезов

### 1. Инженерный каркас и доступ

- Результат: принятый G6, Mini App auth, website OIDC, единый user/profile,
  city и sessions.
- Зависимости: G6 exact-commit VPS gate.
- Готовность: оба входа разрешают одну identity; forged/expired/replayed data
  отклоняется.
- Риск/тесты: account takeover и duplicate profile; auth, replay, race,
  session revocation и negative permission tests.
- Отключение: закрыть authenticated entry points, public read остаётся.

### 2. Публичное знакомство

- Результат: responsive map/list, event card и organizer profile.
- Зависимости: safe discovery/profile projections и geo configuration.
- Готовность: anonymous видит только разрешённые поля; street/exact markers и
  list fallback доступны.
- Риск/тесты: утечка exact point через API/HTML/cache/log; projection/privacy и
  accessibility tests.
- Отключение: list-only mode или закрытие map provider.

### 3. Admin, фоновые задачи и фотографии

- Результат: отдельный staff auth, permissions/audit, moderation queue,
  outbox/Celery и safe image pipeline.
- Зависимости: slices 1–2 и G6 media/worker boundary.
- Готовность: worker/Redis failure не теряет business operation; original/EXIF
  не публикуются.
- Риск/тесты: privilege abuse, malicious file и duplicate delivery; staff,
  media, outbox/inbox и recovery tests.
- Отключение: deny staff mutation, stop delivery, quarantine uploads.

### 4. Создание и жизнь события

- Результат: draft, point/Nominatim/polygon, publication, moderation,
  revisions, cancellation и deep link.
- Зависимости: slices 1–3.
- Готовность: вне города publish невозможен; защищённые поля неизменяемы;
  stale version не перезаписывает новую.
- Риск/тесты: неверное место и lifecycle race; DB/API/version/privacy tests.
- Отключение: закрыть create/publish, public safe read сохраняется.

### 5. Интерес, участие и общение

- Результат: like, join, capacity, FIFO waitlist, leave/exclude, простой chat
  и announcements.
- Зависимости: published Event.
- Готовность: одно последнее место, FIFO сохраняется, chat grant отзывается по
  принятым правилам.
- Риск/тесты: oversubscription и IDOR; concurrency, permission и lifecycle
  tests.
- Отключение: deny joins/chat; существующие факты остаются в PostgreSQL.

### 6. Уведомления и изменения

- Результат: internal center, Telegram delivery, critical banners,
  aggregation, retry и dead-letter.
- Зависимости: outbox и event/participation facts.
- Готовность: блокировка бота не запрещает действие, повтор не дублирует
  доставку.
- Риск/тесты: потеря/спам/stale message; adapter, retry, expiry и replay tests.
- Отключение: остановить external delivery, оставить internal center/banner.

### 7. LookingPost и холодный старт

- Результат: LookingPost 72 часа, likes, idempotent conversion, civic event и
  city low-activity flag.
- Зависимости: discovery/events/moderation.
- Готовность: interest переносится один раз; civic event не получает
  join/chat/attendance/reputation.
- Риск/тесты: fake activity и conversion race; TTL, idempotency и flag tests.
- Отключение: per-city flags для creation/cleanup/civic content.

### 8. Attendance и reputation

- Результат: code, пять попыток, preliminary no-show, dispute, rating, ledger,
  projection, appeal и private policy adapter.
- Зависимости: finalized participation/event outcomes.
- Готовность: redemption один раз; open dispute нейтрален; policy internals
  отсутствуют в Git/API/logs.
- Риск/тесты: code sharing, retaliation и policy leak; brute-force, race,
  dispute/reversal/rebuild/privacy tests.
- Отключение: stop signal application/public levels; ledger не удалять.

### 9. Хранение, восстановление и выпуск

- Результат: cleanup/compaction, snapshots, observability, off-server backup,
  restore drill и end-to-end release checks.
- Зависимости: все предыдущие срезы.
- Готовность: clean gates, restore доказан, карты/Nominatim проверены в трёх
  городах, admin/moderator готовы.
- Риск/тесты: необратимая потеря данных; retention, restore, recovery, E2E и
  Telegram-client map tests.
- Отключение: остановить public entry и mutations; выполнить принятую recovery
  процедуру.

## Общий gate

Каждый срез требует целого пользовательского пути, unit/DB/API/permission и
применимых concurrency/recovery tests, отсутствия unresolved Critical и
контроля каждого applicable High. Ответы/logs не содержат secrets, hidden
coordinates, лишние PII или policy internals. External outage безопасен, а
функция закрывается flag/deny barrier либо откатывается по G4.

Первый выпуск требует clean authoritative gate, обязательные E2E,
backup/restore drill, проверки MapLibre/Nominatim, отдельные staff accounts и
явное подтверждение владельца. Все элементы `PD-011` входят в Slice 1–9.
