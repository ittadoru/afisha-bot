# G4 — API, авторизация и права

Статус: `ACCEPTED`. Документ объединяет прежние G4.3, G4.5, G4.11–G4.14 и
G4.16. Он задаёт границы, а не окончательный OpenAPI-файл.

## HTTP contract

- JSON, строгая валидация и запрет неизвестных command fields.
- User identity берётся только из проверенной server session.
- Public/list endpoints имеют pagination или viewport/bbox + hard limit.
- Mutation получает idempotency key и, где применимо, expected aggregate
  version.
- Ошибка содержит стабильный code, безопасное сообщение, request ID и
  необязательные field details; stack/SQL/provider response наружу не выходят.
- `401` означает отсутствие identity, `403` — отсутствие права, `404`
  используется для безопасного сокрытия объекта, `409` — conflict/state/version,
  `422` — validation, `429` — throttling, `503` — временная зависимость.

Public API показывает только safe discovery/profile/event projections.
Admin API находится на отдельном origin/cookie namespace и вызывает те же
owner use cases через permissions.

## Группы API

| Группа | Основные операции |
|---|---|
| Auth/account | OIDC start/callback, Mini exchange, refresh/logout, sessions, profile/preferences |
| Discovery | cities/categories, viewport/list, public event/profile, LookingPost/Q&A/conversion |
| Events | complete create submit, media attach, revise/cancel, interest/join/waitlist/leave |
| Communication | participant chat, announcements, notification center |
| Attendance/reputation | code redemption, preliminary result, dispute, safe levels |
| Safety | report, own appeal/status |
| Admin | staff auth, queues, cases, decisions, configuration и operations |

Deep link открывает связанный object/action screen и никогда не несёт право,
PII, координату или автоматическую mutation. После identity resolution сервер
повторно проверяет object permission; недоступный объект скрывается безопасно.

## Пользовательская identity

Диаграммы:

- [website OIDC + PKCE](diagrams/11-web-oidc-pkce-flow.mmd);
- [Mini App initData](diagrams/11-mini-app-initdata-flow.mmd);
- [identity resolution transaction](diagrams/12-identity-resolution-transaction.mmd).

Внутренний immutable `user_id` отделён от Telegram identity. Одна защищённая
запись обеспечивает unique Telegram user ID и unique `issuer + subject`.
Telegram username/name/photo не идентификаторы и не перезаписывают публичный
профиль.

Website:

- Telegram OIDC Authorization Code + PKCE;
- проверка `state`, nonce, issuer, audience, signature/JWKS, expiry и code
  transaction;
- scopes только `openid profile`;
- authorization code и token никогда не логируются.

Mini App:

- сервер проверяет подписанный raw `initData`, `auth_date`, допустимый TTL,
  replay/session binding и Telegram user;
- `initDataUnsafe` не доверяется;
- bootstrap/replay claim выполняется атомарно;
- повтор payload не создаёт новый User или параллельную identity.

Website и Mini разрешают identity одним transaction use case. Потеря Telegram
аккаунта не даёт ручного переноса identity в MVP.

## Пользовательские sessions

| Канал | Sliding/absolute срок |
|---|---|
| Website | rolling 30 дней, absolute 90 дней |
| Mini App | 24 часа, обновление только свежим проверенным initData |

Session token хранится только в защищённом виде; rotation/revocation атомарны.
Website использует `Secure`, `HttpOnly`, подходящий `SameSite` cookie, CSRF,
Origin/CORS allowlist. Пользователь может завершить свои sessions. Logout,
block, account deletion и credential compromise отзывают применимые sessions.

## Staff authentication

Admin-панель не использует пользовательский Telegram login. Staff account,
password credential и session принадлежат `trust_safety`.

- Саморегистрации нет.
- Первый admin создаётся одноразовой server command.
- Moderator получает одноразовое приглашение на 24 часа.
- Reset выполняет другой уполномоченный admin.
- Password хранится как Argon2id hash; login имеет generic errors и durable
  throttling.
- Session: absolute 8 часов, idle 30 минут.
- Опасная операция требует action-bound re-auth не старше 5 минут.
- Последнего активного admin нельзя отключить.
- Login, grant/revoke, invite/reset, re-auth и override пишутся в privileged
  audit; audit failure закрывает действие.

Диаграмма: [admin session и re-auth](diagrams/13-admin-session-reauth-lifecycle.mmd).

## Permissions

Role — шаблон, решение принимает permission + scope + object/state guard.

`moderator` работает с очередью, event/media review, reports, временными
мерами и attendance disputes в выданном scope. `admin` дополнительно управляет
staff/permissions, постоянными ограничениями, configuration, appeals,
emergency и audited override.

Backend проверяет:

1. active staff identity/session;
2. конкретный permission;
3. city/case/object scope;
4. lifecycle guard;
5. применимый re-auth;
6. успешную запись audit.

Нельзя выдавать себе permission, читать sensitive case без назначения,
обходить owner state machine или выполнять bulk retry без отдельного решения.

## Public profile

Профиль имеет случайный неизменяемый восьмизначный public ID, изменяемый
псевдоним, about, безопасный avatar и role-specific reputation levels.
Телефон, Telegram username, выбранный город, координаты и история участия не
публикуются.

Anonymous видит только разрешённый organizer profile. Из LookingPost anonymous
видит safe preview pseudonym/avatar, но профиль автора, Q&A и действия требуют
user session. Exact lookup public ID
доступен authenticated пользователю с enumeration throttling. Search/indexing
не раскрывает обычных участников. Safety hide немедленно закрывает projection.

Avatar проходит media pipeline `256×256 WebP`; original/EXIF не публикуются.

## Раскрытие места

Диаграммы:

- [actor/mode matrix](diagrams/14-location-projection-matrix.mmd);
- [fail-closed public hide](diagrams/14-public-hide-barrier.mmd).

| Mode | Anonymous/authenticated non-participant | Active participant | Organizer/staff по праву |
|---|---|---|---|
| `STREET_ONLY` | улица | улица | exact owner/case view |
| `EXACT_PARTICIPANTS` | улица | exact по active episode | exact owner/case view |
| `EXACT_PUBLIC` | exact с предупреждением | exact | exact owner/case view |

Interest, waitlist и offer не дают exact access. Join создаёт reveal receipt
для participation episode; leave/exclude/cancel закрывают дальнейшую выдачу.
После события exact participant access существует только в явно принятом
ограниченном окне; итоговая публичная карточка показывает максимум улицу.

Изменение public → скрытый режим сначала ставит owner barrier, затем обновляет
projection/cache. Exact не попадает в public HTML/SSR, cache key, analytics,
notification text, provider call или log. Уже увиденный адрес нельзя отозвать,
поэтому первая `EXACT_PUBLIC` публикация требует явного предупреждения.

## Security tests

Обязательны positive/negative сценарии forged/expired/replayed auth, duplicate
identity resolution, session rotation/revocation, CSRF/Origin, IDOR/BOLA,
mass assignment, stale version, permission scope, re-auth, public ID
enumeration, exact-location leakage, Q&A auth/privacy/report context и deep-link
permission re-check.
