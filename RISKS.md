# Risks

Здесь остаются только активные или явно принятые Critical/High. Закрытые
формулировки доступны в Git history. `Residual=Да` означает осознанно принятый
остаточный риск, а не отсутствие контроля.

| ID | Уровень | Риск | Обязательный контроль | Residual |
|---|---|---|---|---|
| R-003 | High | Самодекларация 14+ не доказывает возраст | prohibited content, moderation, report/emergency flow и legal review перед public launch | Да |
| R-004 | High | Маленькая команда не успевает модерировать опасный UGC | premode новых organizers, queues, audit, escalation и измерение backlog | Да |
| R-009 | High | Join/waitlist race превышает capacity | transaction, lock/constraint, version и concurrency tests | Нет |
| R-011 | High | Chat/LookingPost Q&A evidence удаляется через 24 часа | report связывает source ID и нужный evidence фиксируется отдельно; срок явно принят | Да |
| R-015/016 | High | Attendance code можно передать отсутствующему | joined-only, 5 попыток, hash, one redemption, rate limit и dispute | Да |
| R-019 | High | Короткий retention теряет evidence, длинный нарушает privacy | final-state guards, legal hold, compaction audit и restore tests | Да |
| R-101 | Critical | Forged Telegram identity/initData | server signature/JWKS, expiry, replay/session binding и internal user ID | Нет |
| R-102 | Critical | BOLA/IDOR раскрывает места/chat/admin data | deny-by-default object permission и negative tests | Нет |
| R-103 | High | Forged или duplicate webhook | secret header, update allowlist и inbox dedup | Нет |
| R-104 | High | State commit без notification/reputation effect | transactional outbox, inbox, unique key и reconciliation | Нет |
| R-107 | High | SSRF/image bomb/malicious media | no arbitrary URL, limits, decode/re-encode, quarantine | Нет |
| R-108 | High | XSS/chat abuse в WebView | plain text, encoding/CSP, validation и rate limits | Нет |
| R-109 | High | Staff злоупотребляет override | least privilege, scope, re-auth и append-only audit | Нет |
| R-111 | High | Redis/Celery duplicate/lost delivery | PostgreSQL truth, outbox-before-enqueue, idempotency и bounded retry | Нет |
| R-112 | High | Secrets/PII/exact point попадают в telemetry | structured allowlist, redaction, access и retention tests | Нет |
| R-113 | High | Backup существует, но не восстанавливается | encrypted off-server backup и isolated restore drill | Нет |
| R-114 | High | Dependency/image drift или compromise | uv lock, immutable digests/SHAs, audit, SBOM и scans | Нет |
| R-117 | High | Один VPS — общий failure domain | limits, private networks, off-server backup и triggers разнесения | Да |
| R-118 | High | OIDC и Mini App создают два профиля | единый identity transaction и unique Telegram subject | Нет |
| R-119 | High | Увиденный exact address нельзя отозвать | default/explicit modes, warning, receipt, cache isolation и audit | Да |
| R-120 | High | Репутация стигматизирует по малой/ложной выборке | finalized facts, sample gates, capped impact, appeal/reversal | Да |
| R-121 | High | Production reputation policy раскрыта | private config adapter вне Git/API/logs и secret review | Да |
| R-122 | High | Admin password без MFA | closed enrollment, Argon2id, throttle, short session, re-auth и audit | Да |

## Release rule

Unresolved Critical запрещает release. Applicable High запрещает затронутую
функцию, пока нет owner, контроля и проверяющего теста; исключение требует
отдельного owner decision. Security/privacy incident имеет нулевой error
budget. Остаточные риски пересматриваются перед соответствующим slice и первым
публичным выпуском.



Настроить города, категории и карту
Махачкала;
Хасавюрт;
Дербент;
все 16 категорий;
карта OpenFreeMap;
определение адреса;
проверка, что точка находится в разрешённом городе;
три режима видимости адреса.
Результат: пользователь выбирает настоящее место события.
10. Сделать профиль
псевдоним;
фотография;
описание;
город;
публичный номер;
будущие и завершённые события;
статус организатора.
Результат: профиль сохраняется и открывается другим пользователям в разрешённом виде.
Этап D. Администратор и событияв
11. Базовая админ-панель
первый вход Atari;
создание первого администратора из .env;
отдельный защищённый вход;
главная страница со счётчиками;
будущая возможность добавлять модераторов в базе;
история действий.
Результат: только вы можете войти на admin.podvval.xyz.
12. Загрузка фотографий
выбор фотографии;
обрезка 16:9;
проверка размера и содержимого;
удаление скрытых данных фотографии;
сохранение безопасной версии.
Результат: фотография действительно загружается на сервер.
13. Создание события
Четыре шага:
название, категория и описание;
дата, время и количество мест;
место и видимость адреса;
фотография и предварительный просмотр.
Дополнительно:
предупреждение при закрытии заполненной формы;
данные незавершённой формы после закрытия не сохраняются;
новое событие отправляется на проверку.
14. Проверка и публикация
В админ-панели:
очередь новых событий;
просмотр автора, текста, фотографии и места;
«Опубликовать»;
«Отклонить» с причиной;
повторная отправка исправленного события;
создание вами событий категории «Особое».
Результат: одобренное событие появляется в приложении.
15. Управление событием
изменить название, описание или фотографию через повторную проверку;
изменить дату и время один раз;
место и категория не меняются;
отменить событие;
уведомить участников;
завершить событие автоматически по времени.
Этап E. Поиск и участие
16. Настоящая карта и список
реальные опубликованные события;
переключение карта/список;
фильтры города, даты и категории;
карточка события;
профиль организатора;
ссылка, которой можно поделиться;
особое оформление муниципальных событий;
правильное скрытие точного адреса.
17. Интерес, вступление и очередь
«Интересно»;
вступление;
ограничение количества мест;
очередь по порядку;
предложение освободившегося места;
отказ от участия;
точная позиция в очереди.
Результат: несколько друзей могут проверить борьбу за последнее место.
18. Чат и объявления
кнопка чата появляется после вступления;
чат не открывается автоматически;
после добровольного выхода доступ закрывается сразу;
с началом события обычные сообщения прекращаются;
организатор продолжает отправлять объявления;
сообщения удаляются через 24 часа после окончания.
19. Уведомления
внутренний центр уведомлений;
сообщения через Telegram;
одобрение или отказ;
изменение или отмена события;
предложение места;
объявление организатора;
повторная отправка при временной ошибке.
Этап F. Остальные функции полного MVP
20. «Ищу людей»
создание идеи без фотографии;
категория, заголовок и текст;
срок жизни 72 часа;
лайки;
вопросы и ответы;
превращение идеи в полноценное событие.
21. Подтверждение посещения
шестизначный код;
код показывается организатору после начала;
ввести его могут только участники;
не более пяти попыток;
один человек подтверждается только один раз;
спор, если посещение не подтвердилось.
22. Оценки и репутация
оценка после события;
отдельный статус участника и организатора;
открытый спор не ухудшает репутацию;
успешным считается завершённое событие с реальными участниками;
после трёх успешных событий организатор становится доверенным;
вы можете убрать доверенный статус.
23. Проверка безопасности и жалобы
жалоба на событие или сообщение;
скрытие опасного события;
история решений;
возможность оспорить решение;
блокировку пользователей пока не добавляем согласно вашему решению.
Этап G. Готовность к тесту
24. Очистка и хранение
автоматическое удаление старых чатов и временных файлов;
резервная копия базы и фотографий;
проверка восстановления;
контроль свободного места.
25. Полная проверка MVP
Пройти с телефона весь путь:
вход → профиль → карта → создание → проверка → публикация → вступление → очередь → чат → уведомление → посещение → оценка
Также проверить:
перезагрузку сервера;
работу после сбоя;
пять одновременных тестировщиков;
три города;
скрытый адрес;
событие «Особое».
Правило работы
Каждый этап выполняем отдельно:
согласуем детали;
изменяем код;
запускаем проверки;
устанавливаем на VPS;
проверяем с телефона;
только потом переходим к следующему.

Поэтапный план Afisha: карта, события, авторизация и MVP
Ключевые решения
Карты: OpenFreeMap остаётся внешним источником vector tiles/styles; собственный tile-сервер не поднимаем на MVP.
Геокодирование: self-hosted Nominatim на VPS с regional Dagestan extract. Browser обращается только к backend.
География MVP: Махачкала, Хасавюрт и Дербент.
Адреса: не сохраняем «все адреса Дагестана» в прикладной БД. Nominatim хранит импортированные OSM-данные; Afisha сохраняет только canonical-адрес выбранной точки, street geometry/anchor и ограниченный приватный cache.
Формат работы: малые вертикальные PR, каждый даёт видимый пользовательский результат и проходит собственные тесты.
Первый результат: demo seed → затем подключение PostgreSQL/PostGIS без смены пользовательского UX.
Этапы и PR
PR 0 — Geo foundation и запуск
Проверить новый BOT_TOKEN на VPS.
Запустить geo-import с Dagestan extract и checksum.
Запустить профиль geo после импорта.
Проверить reverse-geocoding на реальных точках трёх городов.
Оставить OpenFreeMap для browser tiles.
Добавить smoke-проверки MapLibre, Nominatim, /health/ready и bot startup.
Результат: карта загружается, адрес по точке определяется через закрытый VPS Nominatim.
PR 1 — Меню Mini App и demo-события
Добавить навигацию: «События», «Ищу людей», профиль-заглушка.
Экран событий: карта, список, карточка, фильтры города/категории.
Loading/empty/error/list-fallback состояния.
Использовать фиксированные demo events только для UI.
Сохранить full-size Telegram WebApp behavior.
Результат: внутри Telegram виден полноценный экран раздела «События».
PR 2 — Публичная модель событий в PostgreSQL/PostGIS
Создать schemas/tables для cities, categories и public event projection.
Добавить city polygons для трёх городов.
Добавить event point, canonical address и street metadata.
Реализовать city + bbox/zoom + limit API.
Подключить карту и список к API вместо demo seed.
Ограничить публичные поля и исключить exact-location leakage.
Результат: карта и список работают на настоящей БД.
PR 3 — Telegram Mini App authentication
Проверять raw initData на backend.
Проверять подпись, TTL, replay и session binding.
Создавать internal user/profile при первом входе.
Добавить Mini session на 24 часа.
Включить authenticated gates для действий.
Не доверять initDataUnsafe, не логировать raw payload/token.
Результат: пользователь идентифицируется через Telegram, а сайт остаётся anonymous public read.
PR 4 — Профиль и создание события
Реализовать профиль с pseudonym/public ID.
Четырёхшаговая форма события.
Выбор точки marker-ом и reverse-geocoding.
Проверка принадлежности city polygon.
Одна обязательная фотография 16:9.
Submit в moderation queue.
Stale-version, validation и потеря незавершённой формы.
Результат: login → создание события → заявка на модерацию.
PR 5 — Раздел «Ищу людей»
Добавить список и карточки LookingPost.
Создание поста с TTL 72 часа.
Ограничения title/text.
Likes.
Q&A с privacy rules.
Conversion LookingPost → Event.
Low-activity city flag.
Результат: второй самостоятельный пользовательский сценарий работает поверх общей identity/discovery модели.
PR 6 — Участие в событиях
Like/interest.
Join/leave.
Capacity.
FIFO waitlist.
Participant permissions.
Exact location только для допустимых участников.
Concurrency tests против oversubscription.
Результат: пользователь может записаться на событие и управлять участием.
PR 7 — Админ-панель
Отдельный admin.podvval.xyz.
Staff authentication и роли admin/moderator.
Moderation queue.
Approve/reject/hide.
Reports и audit log.
Scope permissions.
Re-auth для опасных операций.
Результат: события и LookingPost проходят управляемую модерацию; текущий 404 заменяется рабочим закрытым UI/API.
PR 8 — Media и фоновые операции
Upload session/quarantine.
Проверка MIME, размера, decode и pixel limits.
Удаление EXIF и re-encode.
Protected media serving.
Outbox + Celery worker.
Retry/dead-letter/idempotency.
Cleanup orphan/expired media.
Результат: фотографии и фоновые действия безопасны и устойчивы к сбоям.
PR 9 — Уведомления
Internal notification center.
Telegram delivery.
Aggregation и deep links.
Retry и delivery status.
Без requestWriteAccess.
Fail-safe при недоступном Telegram.
Результат: изменения по событиям и участию доставляются пользователю.
PR 10 — Participant chat
Чат только после join.
Закрытие доступа после leave/exclude/ban.
Announcements.
Запрет произвольной отправки после начала события.
Retention 24 часа.
Сначала обычный API polling, без WebSocket.
Результат: рабочее общение внутри событий без преждевременного усложнения инфраструктуры.
PR 11 — Attendance, disputes и reputation
Шестизначный attendance code.
Пять попыток и joined-only access.
Preliminary no-show.
Dispute на 24 часа.
Rating.
Immutable reputation ledger.
Публичные уровни без раскрытия формулы.
Результат: после события формируется безопасная история доверия.
PR 12 — Release hardening
Backup/restore drill.
Cleanup/compaction и retention.
Monitoring/alerts.
E2E на трёх городах.
Privacy/security audit.
HTTPS/host Nginx.
Exact-commit VPS gate.
Финальная проверка Telegram Mini App, MapLibre и Nominatim.
Результат: готовность к первому публичному выпуску.
Что можно сократить
Не поднимать собственные vector tiles на MVP — OpenFreeMap достаточно.
Не импортировать весь Дагестан: начать с трёх городов.
Не хранить полный каталог адресов в Afisha — использовать Nominatim как geo index, сохранять только canonical data событий.
Не делать WebSocket chat — начать с polling/API.
Отложить clustering, user geolocation, «Рядом со мной», QR/geofence, Kafka, AI/ML и achievements.
Не объединять admin, notifications и chat в ранние PR: это увеличит риск и скроет прогресс.
Не запускать monitoring/ops/geo-import одновременно на 6 GB VPS; import выполнять отдельным maintenance-этапом без жёстких CPU/RAM limits.
Тестовые критерии каждого PR
unit + API + migration tests для изменённого поведения;
positive/negative permission tests;
loading/error/empty UI states;
phone/desktop и Telegram WebView проверки;
отсутствие secrets, raw initData, exact coordinates и лишних PII в logs/responses;
deploy на VPS только после green checks и короткой rollback-процедуры.
Допущения
Платный map provider вообще не нужен, только бесплатный, и собственный tile hosting не входят в MVP.
Админ-панель начинается после реализации «Ищу людей», как требуется в пользовательском порядке.
Публичное чтение событий может быть anonymous; создание, участие, Q&A и profile actions требуют Telegram Mini App auth.
