# Risks

Здесь остаются только активные или явно принятые Critical/High. Закрытые
формулировки доступны в Git history. `Residual=Да` означает осознанно принятый
остаточный риск, а не отсутствие контроля.

| ID | Уровень | Риск | Обязательный контроль | Residual |
|---|---|---|---|---|
| R-003 | High | Самодекларация 14+ не доказывает возраст | prohibited content, moderation, report/emergency flow и legal review перед public launch | Да |
| R-004 | High | Маленькая команда не успевает модерировать опасный UGC | premode новых organizers, queues, audit, escalation и измерение backlog | Да |
| R-009 | High | Join/waitlist race превышает capacity | transaction, lock/constraint, version и concurrency tests | Нет |
| R-011 | High | Chat evidence удаляется через 24 часа | жалоба/важный факт фиксируется отдельно; срок явно принят | Да |
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
