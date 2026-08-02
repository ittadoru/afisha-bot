# Afisha — актуальная спецификация v1.0

Это читаемый обзор, а не отдельный источник решений. Приоритет:
`PRODUCT_DECISIONS.md` → `DECISIONS.md` → принятый G4 → незаменённая часть
`SOURCE_SPECIFICATION.md`.

## Продукт

Afisha — Telegram Mini App и адаптивный сайт бесплатных безопасных офлайн-
событий для Махачкалы, Хасавюрта и Дербента. Возраст — 14+ по самодекларации.

Anonymous видит карту/list, публичное событие, deep link, organizer profile и
safe preview активного LookingPost. Q&A, профиль автора LookingPost, лайк,
вступление, chat, создание, жалоба и profile mutation требуют Telegram login.
Staff работает в отдельной закрытой admin-панели.

MVP включает Event, LookingPost 72 часа, interest, join, FIFO waitlist, простой
participant chat, LookingPost Q&A, notifications, attendance/dispute/rating,
четыре публичных reputation level, moderation/appeals, public web и civic
events.

В MVP нет minimum/confirmation, user geolocation/«Рядом со мной», clustering,
QR/geofence, WebSocket chat, achievements/challenges, AI/ML и Kafka.

## Пользователь и профиль

Внутренний immutable `user_id` отделён от Telegram. Публичный профиль:
изменяемый случайный псевдоним, неизменяемый восьмизначный public ID, about,
безопасный `256×256 WebP` avatar и отдельные participant/organizer levels.

Telegram username/phone, выбранный город, координаты и история участия не
публикуются. Website использует Telegram OIDC+PKCE, Mini App — проверенный
`initData`; оба пути создают одну identity. Website session: rolling 30/absolute
90 дней; Mini session — 24 часа.

## Карта и место

Организатор выбирает точку marker-ом; backend reverse-geocode через закрытый
Nominatim. Point — источник истины. Publish разрешён только внутри city polygon.
После публикации point/address/category неизменяемы.

Режимы: `STREET_ONLY`, `EXACT_PARTICIPANTS`, `EXACT_PUBLIC`. Interest,
waitlist и offer не дают exact access. Street marker строится по canonical
street geometry без скрытой event point. MapLibre использует OpenFreeMap;
обязательны legend, attribution и list fallback.

## Событие и участие

Создание — четыре шага в открытом клиенте: основное, время/участие, место и
одна обязательная фотография `16:9`. Название ограничено 60, описание — 1000
символами. Persistent Event draft отсутствует: при выходе заполненная форма
предупреждает о потере и после закрытия/reload не восстанавливается.

Event имеет начало/окончание; capacity необязателен. Like не занимает место.
Join занимает место сразу; при заполнении пользователь вручную входит в FIFO
waitlist. Offers резервируют освободившиеся места первым подходящим.

После publication время суммарно переносится не более двух раз через immutable
revision; place/category не меняются. Уведомление не требует reconfirmation.
Stale edit возвращает conflict.

Chat доступен active participants. После leave write закрывается сразу, read —
через 24 часа; после exclude/ban доступ закрывается сразу. С началом Event
произвольная отправка прекращается.

Attendance подтверждает шестизначный server code: joined-only, пять попыток,
один success. Без code возникает preliminary no-show; dispute длится 24 часа,
финальное решение принимает moderator.

LookingPost живёт 72 часа, не имеет фото и отдельного времени; title ограничен
30, text — 300 символами. У пользователя может быть один unanswered question
до 200 символов; ответ автора — до 300. До ответа вопрос закрыт для остальных,
а опубликованная immutable пара не раскрывает asker. Обычный Q&A staff не
видит без связанной жалобы и case permission.

## Интерфейс

Принятая структура сайта, Mini App и admin-панели, состояния экранов и
визуальное направление находятся в
[UI/UX decisions](docs/ui/01-ui-ux-decisions.md). Точные HEX, полный icon set,
детальная design system и 3D-объект пока не выбраны.

## Safety и reputation

Новые organizers проходят premode до трёх успешных events. Reports,
restrictions, moderation и appeals принадлежат `trust_safety`.

Reputation хранит immutable signals и role-specific projections. Публично
виден `Новый пользователь` либо четыре принятых уровня без чисел/формулы.
Open dispute нейтрален; appeal создаёт reversal. Production weights,
thresholds и anti-fraud rules находятся вне Git/API/logs.

## Данные и сроки

- chat/announcements — 24 часа после Event;
- фотографии — 7 дней после применимого terminal state;
- закрытый LookingPost и Q&A — 24 часа;
- attendance evidence — 30 дней после dispute;
- revision details и staff audit — 90 дней;
- encrypted backups — 14 дней.

После terminal/dispute сохраняется компактный snapshot/outcomes; тяжёлые
details/media удаляются идемпотентным compaction с legal-hold guard.

## Архитектура и выпуск

Backend — модульный монолит: `accounts`, `discovery`, `events`,
`communication`, `trust_safety`, `reputation`, `media`. Каждый владеет schema
и правилами. PostgreSQL/PostGIS — truth; outbox записывается с business state.
Celery/Redis не определяют права или state.

Stage 1 — один Compose VPS с private data networks и local protected media.
G6 не открывает production traffic. Первый выпуск требует все девять G5
slices, clean exact-commit VPS gate, restore drill и отдельное подтверждение.
