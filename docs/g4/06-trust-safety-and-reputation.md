# G4 — Trust & Safety и reputation

Статус: `ACCEPTED`. Документ объединяет прежние G4.17 и G4.19 и сохраняет
разделение ответственности ADR-011.

## Ответственность

`trust_safety` единолично владеет reports, moderation, bans/restrictions,
appeals, emergency decisions, staff permissions и privileged audit.
`reputation` принимает finalized signals и вычисляет уровень, но не блокирует
пользователя или событие.

Новые организаторы проходят премодерацию. Она снимается после трёх успешно
завершённых событий без подтверждённого серьёзного нарушения и возвращается
при принятом safety signal согласно PD. Text fallback через три часа проверяет
только разрешённый узкий сценарий и не заменяет moderation.

## Moderation и appeals

- Case связывает subject, safe reason, reporter/owner, lifecycle и assigned
  staff без раскрытия лишних данных.
- Один moderation command имеет expected version и immutable decision audit.
- Temporary hide/restriction применяется fail-closed до публичной projection.
- Для любого компонента события staff может только отклонить жалобу либо скрыть
  событие целиком. Организатор и участники немедленно получают уведомление.
- Скрытое событие восстанавливается при отмене решения в течение трёх дней; уже
  завершившееся событие возвращается в статус `finished`. Без апелляции или после
  её отклонения минутный идемпотентный sweep удаляет revisions content, chat и
  photos, закрывает активное участие/waitlist и сохраняет tombstone + audit.
- Жалоба до решения не меняет reputation.
- Appeal создаёт отдельный lifecycle; upheld/reversed outcome публикует
  compensating fact, а не переписывает ledger.
- Staff читает sensitive evidence только по permission + case scope.
- Обычные LookingPost questions не видны staff. Новые отдельные reports на Q&A
  answer не принимаются; пользователь может пожаловаться на сам LookingPost.
  Исторические Q&A cases остаются читаемыми в staff history.
- Emergency action минимально достаточен, ограничен сроком и требует последующей
  review.

## Reputation model

Отдельно считаются participant и organizer projections. Публично показывается
`Новый пользователь` либо один из четырёх принятых уровней без numeric score.

Ledger append-only хранит типизированный signal, subject role, source event,
finalization time, policy version и reversal link. Unique source/business key
не даёт повтору повысить или снизить результат дважды.

Policy port принимает публичный component vector и возвращает safe level,
explanations и typed result. Production weights, thresholds и anti-fraud rules
хранятся вне Git/API/logs/admin UI. Demo policy использует только synthetic
fixtures и не раскрывает production policy.

Диаграмма:
[signal → projection](diagrams/17-reputation-signal-projection-flow.mmd).

Policy activation проходит shadow calculation, comparison, owner approval и
atomic version cutover. Rollback переключает projection policy version либо
пересчитывает ledger; applied signals не удаляются.

Attendance signal возникает только после finalized decision. Один event/user
даёт не более одного normalized outcome. Open dispute нейтрален. Appeal
reversal создаёт compensating signal.

## Privacy и threat boundaries

Диаграмма:
[public/auth/location data flow](diagrams/19-public-auth-location-dfd.mmd).

| Угроза | Обязательный контроль |
|---|---|
| Forged identity/webhook | signature/secret, expiry, replay и dedup |
| BOLA/IDOR | deny-by-default object permission и negative tests |
| Exact-location leakage | caller-specific serializer, separate cache, fail-closed hide |
| XSS/chat/Q&A abuse | plain text/default encoding, CSP, limits и rate limits |
| Malicious media/SSRF | no arbitrary fetch URL, decode/re-encode и resource limits |
| Privileged misuse | least privilege, re-auth и append-only audit |
| Duplicate/race | unique keys, version, transaction и lock |
| Lost side effect | transactional outbox, unique business key и bounded retry (PD-021) |
| Log/backup disclosure | allowlist telemetry, encryption, access и retention |
| Supply-chain compromise | lock, pinned digest/SHA, audit, SBOM и scan |

Security/privacy error budget равен нулю: подтверждённое раскрытие exact
location, credential, private chat или закрытой policy требует containment,
rotation/revocation где применимо, расследование и owner review.

## Наблюдаемость и данные

Разрешены pseudonymous IDs, safe reason codes, counts, latency, lifecycle и
component health. Запрещены raw initData/tokens/cookies/passwords, exact
coordinates/address, chat/description text, original filename/EXIF, evidence и
reputation internals.

Critical finding блокирует выпуск. High блокирует затронутую функцию, пока нет
контроля, теста и отдельного owner decision. False positive документируется;
его нельзя молча игнорировать.

## Остаточные риски MVP

- Самодекларация возраста не доказывает возраст.
- Exact public address и адрес, увиденный участником, нельзя сделать снова
  неизвестным.
- Общий attendance code можно передать внешним каналом.
- Chat и закрытое LookingPost Q&A evidence удаляются через 24 часа, кроме
  отдельно зафиксированного report/safety evidence.
- Password-only admin не имеет MFA в MVP.
- Репутационная policy требует реальных данных и отдельной production tuning.

Эти риски сохраняются в `RISKS.md`; изменение их принятия требует нового PD/ADR.
