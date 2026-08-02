# G4 — deployment, observability и quality gates

Статус: `ACCEPTED`, включая пересмотр `ADR-021`. Документ объединяет прежние
G4.9, G4.10, G4.20 и G4.21.

## Stage 1

Диаграмма: [один VPS](diagrams/10-stage-1-one-server.mmd).

MVP/alpha использует один Ubuntu 24.04 `linux/amd64` VPS и Docker Compose.
Core: Nginx, API, worker, beat, PostgreSQL/PostGIS, Redis и local media.
Nominatim и monitoring включаются отдельными profiles.

- PostgreSQL, Redis, Nominatim, metrics и media не публикуют host ports.
- В G6 Nginx доступен только на `127.0.0.1:8080` через SSH tunnel.
- Production `80/443`, domains и TLS не входят в G6.
- Application containers работают non-root, read-only где возможно, без
  Docker socket, с limits и log rotation.
- Media доступна только API/worker; database/media backups уходят off-server
  начиная со Slice 9.
- Geo import не запускается одновременно с worker/beat/ops на VPS 4 ГБ.

Следующий сервер появляется только по измеримой причине: PostgreSQL RAM/IO и
failure domain; worker/media CPU/RAM; API connections/CPU. Kubernetes, Kafka и
собственный tile server не добавляются заранее.

## Backup и recovery

Alpha: `RPO ≤24h`, `RTO ≤24h`, encrypted off-server backup, retention 14 дней.
Backup включает PostgreSQL и media consistency manifest, commit/revision,
timestamps и checksums без secrets.

Restore drill выполняется в изолированном окружении: проверить decrypt,
PostgreSQL/PostGIS restore, migration head, media references, critical counts,
readiness и smoke. Наличие backup без успешного restore evidence не закрывает
release gate.

## Monitoring

- Prometheus scrape/evaluation: 60 секунд.
- Retention: 7 дней, cap 512 MB.
- Application logs: structured allowlist, 7 дней.
- Security detection logs: до 14 дней; privileged audit — PostgreSQL 90 дней.
- Node exporter: только filesystem/textfile collectors.
- Alertmanager не содержит production Telegram receiver в G6.
- Distributed tracing отсутствует в MVP.

| Signal | Gate/alert |
|---|---|
| Disk free | warning `<30%`, critical `<15%`, emergency `<10%` |
| API | availability, error rate и p95 по public/user/admin |
| DB | availability, connections, slow queries и disk |
| Async | outbox oldest age, queue/dead-letter и worker heartbeat |
| External | Telegram/Nominatim errors/429 и expiry |
| Security | auth/replay/rate-limit/audit failures без sensitive payload |
| Backup | age, completion и restore-drill evidence |

Alpha SLO: public/user API 99,5%; admin/background 99,0%. Security/privacy
incident не поглощается обычным error budget.

## Миграции

Один Alembic environment, одна линейная chain и ровно один head/runner.
Revision меняет только owner schema; applied history не переписывается.

Диаграмма: [migration lifecycle](diagrams/21-migration-lifecycle.mmd).

Используется expand → compatible deploy → bounded resumable backfill →
verification → отдельный contract cleanup. Перед migration проверяются backup,
restore rehearsal, disk/inodes, expected head и migration lease.

Обязательны upgrade from empty и поддерживаемого current snapshot, single-head,
expected schema diff, PostGIS preconditions и post-upgrade smoke. Blind
destructive downgrade запрещён; основной путь — app rollback для compatible
schema, forward fix или rehearsed restore.

## Authoritative verification

Диаграмма:
[VPS verification pipeline](diagrams/21-ci-cd-pipeline.mmd).

По `ADR-021` authority имеет versioned script на clean checkout exact commit
resettable VPS. Safe manifest связывает commit SHA, external image digests,
application image ID, migration head, checks и result без env/secrets/PII.

Gate:

1. deterministic `uv sync --locked`;
2. Ruff format/check и Pyright strict;
3. pytest coverage `≥85%` и architecture tests;
4. empty DB migration/single head/PostGIS/seven schemas;
5. PostgreSQL, Redis, Celery и API health/readiness;
6. Nginx/media/port/non-root/resource boundaries;
7. pip-audit, Bandit и secret scan;
8. SBOM, container scan и Compose health smoke.

GitHub Actions выполняет только secret-free subset, использует immutable action
SHA, не получает VPS credentials и не разрешает deployment. Deployment
manual-only после owner approval.

## Definition of Done

- Accepted PD/ADR/G4 связаны с owner module и acceptance scenarios.
- Public/application/domain/infrastructure boundaries не нарушены.
- Mutation идемпотентна, авторизована и имеет transaction/failure semantics.
- Migration linear, owner-scoped и проверена.
- Unit, DB/API, permission и применимые concurrency/recovery tests зелёные.
- Пользовательские срезы проверены на phone/desktop viewport: anonymous gates,
  location projection, waitlist expiry, form loss, deep links и staff scope;
  keyboard/screen-reader/contrast/touch-target checks применены.
- Coverage не ниже 85%; critical scenarios не заменяются процентом.
- Нет applicable Critical/High security findings.
- Logs/responses не содержат secrets, PII, exact hidden location или policy
  internals.
- External outage имеет safe fallback/fail-closed behavior.
- Feature можно закрыть flag/deny barrier либо откатить по migration plan.
- Docs, risks и changelog обновлены только для реально принятого изменения.
