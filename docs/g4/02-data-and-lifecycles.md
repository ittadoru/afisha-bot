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
- дата/начало/окончание суммарно меняются не более одного раза; отклонённая
  revision лимит не расходует;
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

Capacity необязателен; если лимит задан, он не может быть меньше трёх.

| Действие | Guard и результат |
|---|---|
| Like/unlike | не занимает место; повтор команды идемпотентен |
| Join | event joinable; один active episode; место резервируется атомарно |
| Waitlist join | только при заполненном capacity; стабильная FIFO position |
| Place release | первый ожидающий автоматически становится участником и получает notification |
| Leave | active episode закрывается; старое место/position не восстанавливается |
| Exclude | закрывает участие и защищённый доступ немедленно |

Освобождение нескольких мест автоматически переводит не более `N` первых
подходящих пользователей в участники. Участие и очередь доступны до окончания
события, включая время после начала. Join, capacity edit, promotion и leave
используют transaction + lock/constraint; два пользователя не получают
последнее место.

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
- После вступления chat grant становится доступен, но клиент не открывает чат
  автоматически.
- После добровольного выхода, исключения или бана read/write закрываются сразу.
- С началом события произвольная отправка закрывается; объявления остаются
  отдельным организаторским каналом.
- Report, moderation decision и appeal имеют собственные immutable audit facts.
- Safety hold/hide применяется fail-closed и не ждёт eventual projection.

## Constraints и snapshots

Обязательны unique/partial constraints для active participation, active offer,
однократного redemption, outbox business key, public ID и policy signal source.
Конкретные SQL constraints добавляются owner migration. Inbox-таблица не
вводится (PD-021); её роль выполняет unique business key outbox-строки.

После завершения Event итоговые факты остаются в операционных таблицах:
owner, category, финальное время, защищённое место, результаты участия, counts,
ratings и lifecycle reason. Полные промежуточные тексты и media в долгосрочном
хранении не сохраняются.

`Особое` хранится как отдельный вид события с внутренним audit actor, но без
публичного организатора и participation-модели. Оно разрешает только safe view
и like, не имеет capacity/waitlist/chat/attendance/rating/reputation и не
попадает под скрытие из-за низкой активности.

## Retention

| Данные | Срок/правило |
|---|---|
| Chat и announcements | удалить через 24 часа после окончания |
| Event/profile фотографии | удалить через 7 дней после применимого terminal state |
| Закрытый LookingPost и Q&A details | удалить через 24 часа после закрытия/conversion |
| Attendance evidence | 30 дней после окончательного dispute |
| Revision old/new details | 90 дней, затем компактные факты |
| Moderation и privileged audit | 90 дней |
| Raw provider/cache payload | не хранить либо ≤24 часов по принятому contract |
| Encrypted backups | 7 дней, локально на VPS (off-server отложен — R-113) |

Legal/safety hold приостанавливает только применимое удаление и сам
аудируется. Закрытые anti-fraud/reputation internals не переносятся в Git.

## Compaction (упрощено PD-021: идемпотентный sweep)

Итоговые факты завершённого события живут в операционных таблицах и не
дублируются: строка `events.events`, одна последняя одобренная revision через
`approved_revision_id` и строки участия остаются навсегда. По просроченной
ссылке показывается компактная карточка: название, последнее описание, время,
место по правилам доступа, счётчики участников и оценки; фотографии нет после
7 дней.

Очистка — простой идемпотентный sweep. Периодический таск выполняет повторяемые
`DELETE` батчами по `delete_after`/срокам (чат 24 часа, media 7 дней, старые
revisions 90 дней, audit 90 дней). Каждый запрос сам по себе идемпотентен:
сбой до удаления исправляется следующим запуском, сбой после удаления не
повторяет бизнес-эффекта. Защита споров, жалоб и legal hold — одно условие
`NOT EXISTS` по открытым case. Отдельный compaction-механизм с расписками,
агрегатами и reconciliation не вводится (PD-021).
