# G4 — данные и жизненные циклы

Статус: `ACCEPTED`. Документ объединяет прежние G4.4 data model и state
machines. Точные продуктовые правила определяют PD/ADR.

## Владение данными

Диаграмма: [обзор ER и owner schemas](diagrams/04-domain-er-overview.mmd).

| Schema | Основные записи |
|---|---|
| `accounts` | user, telegram identity, profile, preferences, sessions и auth transactions |
| `discovery` | safe event/profile projections, city/category, LookingPost, question/answer и conversion |
| `events` | event, immutable revision, interest, participation episode, waitlist entry/offer, attendance |
| `communication` | chat grant/message, announcement, notification и delivery |
| `trust_safety` | staff account/session, permission grant, moderation case/report/appeal, privileged audit |
| `reputation` | immutable signal ledger, policy version и role-specific projection |
| `media` | upload session, attachment, derivative и lifecycle state |

Technical outbox/inbox records имеют явно назначенного owner. Идентификаторы
между schemas хранятся как значения без cross-schema FK.

## Общие правила

- Primary IDs случайны и не раскрывают порядок создания.
- Время хранится в UTC; пользовательский вывод использует городскую timezone.
- Статусы представлены enum/value objects, а неизвестное внешнее значение
  отклоняется.
- Update агрегата требует ожидаемую version; stale write возвращает conflict.
- User-facing delete не означает мгновенное физическое удаление записей,
  удерживаемых dispute/legal/safety сроком.
- Точные координаты, chat, auth и moderation относятся к защищённым классам и
  не попадают в публичные projections.

## Event и LookingPost

Диаграммы:

- [Event lifecycle](diagrams/04-event-state.mmd);
- [participation и waitlist](diagrams/04-participation-waitlist-state.mmd);
- [attendance](diagrams/04-attendance-state.mmd).

Event хранит lifecycle отдельно от moderation/public visibility. Сервер не
хранит Event draft: четырёхшаговая форма живёт только в открытом клиенте, а
финальный submit принимает полную revision, валидный городской polygon и
готовое media. Публичная projection появляется только при разрешённом
moderation state.

После публикации:

- category, точка и адрес неизменяемы;
- дата/начало/окончание суммарно меняются не более двух раз;
- существенное изменение создаёт immutable revision;
- одновременно существует не более одной ожидающей moderation revision;
- cancellation terminal для вступления, offers и будущих reminders.

LookingPost живёт 72 часа. Conversion сначала заполняет клиентскую форму, но
не создаёт draft. Финальный submit одной идемпотентной транзакцией создаёт
ровно один полный Event, помечает LookingPost преобразованным и переносит
только активный interest без участия/capacity или скрытых прав. До submit
LookingPost остаётся активным.

У вошедшего пользователя может быть не более одного unanswered question на
LookingPost. До ответа текст видят только asker и author; после ответа
публичная пара не раскрывает asker. Опубликованные question/answer immutable.
Новые вопросы запрещены после close/conversion.

## Interest, participation и waitlist

`EventInterest`, `EventParticipation`, `WaitlistEntry/Offer` и attendance —
разные факты.

| Действие | Guard и результат |
|---|---|
| Like/unlike | не занимает место; повтор команды идемпотентен |
| Join | event joinable; один active episode; место резервируется атомарно |
| Waitlist join | только при заполненном capacity; стабильная FIFO position |
| Place release | первые подходящие записи получают отдельные timed offers |
| Offer accept | offer active, место всё ещё зарезервировано, один active episode |
| Leave | active episode закрывается; старое место/position не восстанавливается |
| Exclude | закрывает участие и защищённый доступ немедленно |

Освобождение нескольких мест создаёт не более `N` offers первым подходящим
пользователям. Join, capacity edit, offer и leave используют transaction +
lock/constraint; два пользователя не получают последнее место.

## Attendance и спор

- Сервер создаёт один шестизначный code и хранит только hash.
- Code вводит только вступивший до начала пользователь, максимум пять попыток.
- Один participation episode подтверждается не более одного раза.
- Без успешного ввода создаётся предварительное `не подтверждено` без влияния
  на reputation.
- Пользователь имеет 24 часа на dispute; moderator завершает его как
  `confirmed`, `neutral` или `no_show`.
- Открытый dispute блокирует финальный reputation signal.

## Communication и moderation lifecycle

- Chat grant существует только для разрешённого participation episode.
- После добровольного выхода write закрывается сразу, read — через 24 часа.
- После исключения/бана read/write закрываются сразу.
- С началом события произвольная отправка закрывается; объявления остаются
  отдельным организаторским каналом.
- Report, moderation decision и appeal имеют собственные immutable audit facts.
- Safety hold/hide применяется fail-closed и не ждёт eventual projection.

## Constraints и snapshots

Обязательны unique/partial constraints для active participation, active offer,
однократного redemption, outbox business key, inbox receipt, public ID и
policy signal source. Конкретные SQL constraints добавляются owner migration.

После завершения Event сохраняется компактный snapshot: owner, category,
финальное время, защищённое место, normalized outcomes, counts, ratings,
reputation facts и lifecycle reason. Полные промежуточные тексты и media в
долгосрочный snapshot не копируются.

## Retention

| Данные | Срок/правило |
|---|---|
| Chat и announcements | удалить через 24 часа после окончания |
| Event/profile фотографии | удалить через 7 дней после применимого terminal state |
| Закрытый LookingPost и Q&A details | удалить через 24 часа после закрытия/conversion |
| Attendance evidence | 30 дней после окончательного dispute |
| Revision old/new details | 90 дней, затем compact facts |
| Moderation и privileged audit | 90 дней |
| Raw provider/cache payload | не хранить либо ≤24 часов по принятому contract |
| Encrypted backups | 14 дней |

Legal/safety hold приостанавливает только применимое удаление и сам
аудируется. Закрытые anti-fraud/reputation internals не переносятся в Git.

## Compaction

Диаграмма: [compaction flow](diagrams/04-compaction-flow.mmd).

Compaction запускается только после terminal state и окончания всех dispute/
appeal окон. Одна транзакция фиксирует snapshot/outcomes и durable cleanup
intent. Cleanup идемпотентно удаляет тяжёлые details/media, записывает audit и
проверяется reconciliation. Сбой до commit не меняет данные; сбой после commit
повторяет cleanup без повторного бизнес-результата.
