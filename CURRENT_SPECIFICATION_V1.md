# Afisha — актуальная спецификация v1.0

Это читаемый обзор, а не отдельный источник решений. Приоритет:
`PRODUCT_DECISIONS.md` → `DECISIONS.md` → принятый G4 → незаменённая часть
`SOURCE_SPECIFICATION.md`.

## Продукт

Afisha — Telegram Mini App и публичный адаптивный сайт бесплатных безопасных
офлайн-событий для Махачкалы, Хасавюрта и Дербента. Возраст — 14+ по
самодекларации.

В MVP пользователь входит только через Telegram Mini App. Обычный сайт публичен
и не имеет пользовательского входа; website OIDC отложен. Q&A, лайк,
вступление, chat, создание, жалоба и изменение профиля доступны только после
проверки Mini App `initData`. Staff работает в отдельной закрытой admin-панели.

MVP включает Event, LookingPost 72 часа, interest, join, FIFO waitlist, простой
participant chat, LookingPost Q&A, notifications, attendance/dispute/rating,
четыре публичных reputation level, moderation/appeals, public web и
общественные события.

В MVP нет minimum/confirmation, user geolocation/«Рядом со мной», clustering,
QR/geofence, WebSocket chat, achievements/challenges, AI/ML, Kafka и отдельного
слоя бизнес-аналитики с записью показов (PD-018, PD-021).

## Пользователь и профиль

Внутренний immutable `user_id` отделён от Telegram. Публичный профиль:
изменяемый случайный псевдоним, неизменяемый восьмизначный public ID, about,
безопасный `256×256 WebP` avatar и отдельные participant/organizer levels.

Telegram username/phone, выбранный город, координаты и история участия не
публикуются. Проверенный Mini App `initData` при первом входе создаёт или
находит внутреннюю identity; Mini session живёт 24 часа.

## Карта и место

Организатор выбирает точку marker-ом; backend reverse-geocode через закрытый
Nominatim. Point — источник истины. Publish разрешён внутри city polygon и
фиксированного буфера 1 000 м; размер Nominatim-extract эту зону не расширяет.
После публикации point/address/category неизменяемы.

Режимы: `STREET_ONLY`, `EXACT_PARTICIPANTS`, `EXACT_PUBLIC`. Interest,
waitlist и offer не дают exact access. Street marker строится по canonical
street geometry без скрытой event point. MapLibre использует OpenFreeMap;
обязательны legend, attribution и list fallback.

## Событие и участие

Создание — пять клиентских шагов: основное, время/участие, точка на карте,
адрес/видимость и фотография `4:3` с preview. Название ограничено 60, описание — 1000
символами. Persistent Event draft отсутствует: при выходе заполненная форма
предупреждает о потере и после закрытия/reload не восстанавливается.

Event имеет начало/окончание; capacity необязателен, а заданный лимит не может
быть меньше трёх. Like не занимает место.
Join занимает место сразу; при заполнении пользователь вручную входит в FIFO
waitlist. Освободившееся место сразу занимает первый подходящий человек в FIFO;
join и очередь закрываются в момент начала события.

После publication дата/начало/окончание суммарно меняются не более одного раза через immutable
revision; place/category не меняются. Уведомление не требует reconfirmation.
Stale edit возвращает conflict.

Chat становится доступен после вступления, но не открывается автоматически.
После leave/exclude/ban чтение и запись закрываются сразу. С началом Event
произвольная отправка прекращается.

Attendance подтверждает шестизначный server code только во время события:
joined-only, пять попыток, один success. Без code возникает preliminary no-show; dispute длится 24 часа,
финальное решение принимает moderator.

Подтверждённый участник может в течение семи дней один раз приватно отметить
событие «Понравилось» или «Не понравилось». При менее чем трёх подтверждённых
участниках ответ хранится, но не влияет на quality signal.

LookingPost живёт 72 часа, не имеет фото и отдельного времени; title ограничен
30, text — 300 символами. У пользователя может быть один unanswered question
до 200 символов; ответ автора — до 300. До ответа вопрос закрыт для остальных,
а опубликованная immutable пара показывает публичное имя, 64×64 avatar и
ссылку на профиль asker. Обычный Q&A staff не
видит без связанной жалобы и case permission.

Обычные категории: Спорт, Игры, Сходки, Кафе, Туризм, Обучение, Творчество,
Автомобили, Волонтёрство, Работа, Развлечения, Прогулки и Другое. «Работа»
допускает только бесплатные профессиональные встречи и обмен опытом.
Общественное событие создаёт только administrator, имеет любую активную категорию и не имеет
публичного организатора, вступления, capacity, очереди, чата, attendance,
оценок и reputation; низкая активность его не скрывает.

## Интерфейс

Принятая структура сайта, Mini App и admin-панели, состояния экранов и
визуальное направление находятся в
[UI/UX decisions](docs/ui/01-ui-ux-decisions.md). Точные HEX, полный icon set,
детальная design system и 3D-объект пока не выбраны.

## Safety и reputation

Новые organizers проходят premode до трёх успешных events. Reports,
restrictions, moderation и appeals принадлежат `trust_safety`.

Успешное событие завершилось, не отменено и имеет минимум три посещения,
подтверждённых кодом. После трёх таких событий без серьёзных нарушений
организатор становится доверенным.

Reputation хранит immutable signals и role-specific projections. Публично
виден один из уровней: «Новый пользователь»/«Новый организатор», «Низкая
надёжность», «Обычная репутация», «Надёжный», «Высокая репутация» — без чисел
и формулы.
Open dispute нейтрален; appeal создаёт reversal. Production weights,
thresholds и anti-fraud rules находятся вне Git/API/logs.

## Данные и сроки

- chat/announcements — 24 часа после Event;
- фотографии — 7 дней после применимого terminal state;
- закрытый LookingPost и Q&A — 24 часа;
- attendance evidence — 30 дней после dispute;
- revision details и staff audit — 90 дней;
- encrypted backups — 7 дней, локально на VPS (off-server — остаточный риск R-113).

После terminal/dispute итоговые факты остаются в операционных таблицах
(строка события, последняя одобренная версия, участия); тяжёлые details/media
удаляются идемпотентным sweep с legal-hold guard. По просроченной ссылке
показывается компактная карточка: название, последнее описание, время, место
по правилам доступа, счётчики участников и оценки; фотографии нет после
7 дней.

## Alpha-упрощения (PD-021)

- Nominatim: extract по bbox трёх городов + запас ~20 км вместо всего Дагестана.
- Мониторинг: без Alertmanager и node-exporter; Prometheus 3 дня (cap 128 MB);
  алерты — cron-скриптом.
- Бэкапы: локально на VPS, 7 дней, шифрованные; off-server отложен (R-113).
- Outbox: одна таблица, unique business key, bounded retry с TTL, без
  inbox/dead-letter/reconciliation.
- Очистка: простой идемпотентный sweep вместо compaction-механизма.
- Аналитика PD-018: слой фактов и показы вне MVP.
- Street anchor: центроид canonical street geometry.
- Качество: coverage ≥60% на alpha; SBOM/container scan перед публичным
  выпуском.

## Архитектура и выпуск

Backend — модульный монолит: `accounts`, `discovery`, `events`,
`communication`, `trust_safety`, `reputation`, `media`. Каждый владеет schema
и правилами. PostgreSQL/PostGIS — truth; outbox записывается с business state.
Celery/Redis не определяют права или state.

Stage 1 — один Compose VPS с private data networks и local protected media.
G6 не открывает production traffic. Первый выпуск требует все девять G5
slices, clean exact-commit VPS gate, restore drill и отдельное подтверждение.
