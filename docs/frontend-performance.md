# Frontend performance

## Current architecture

- Server state is managed by feature hooks backed by a small in-memory cache.
- Cache keys are structured by feature and parameters. GET requests are deduplicated, stale responses are ignored, mutations invalidate affected prefixes, and logout clears all entries.
- Private responses are never persisted in Service Worker, Cache Storage, localStorage, or IndexedDB.
- Images use versioned immutable URLs and purpose-specific variants. Avatars use 64/256, events 320/640/1200, and profile backgrounds 320/768/1280.
- Route-only code is loaded through dynamic imports. MapLibre and its CSS load after authentication when the default map screen mounts.

## Future TanStack Query migration

TanStack Query is intentionally not part of the current optimization. Adopt it when the number of server-state screens or the frontend team grows enough that maintaining retry, invalidation and devtools behavior internally costs more than the dependency.

Migration must happen one feature module at a time. A migrated resource must not continue using the custom cache in parallel. After the final feature moves, delete the custom cache rather than retaining two permanent server-state systems.

## Cache policy

| Resource | Freshness |
|---|---:|
| Catalog | 30 minutes |
| Event map/list | 30 seconds |
| Event/profile | 60 seconds |
| Company | 30 seconds |
| Notifications/cases | 15 seconds |
| Chat | Not cached; visibility-aware polling |

Automatic network retries are disabled for normal feature queries. The UI provides explicit retry. Chat alone uses bounded polling backoff because it is a live screen.
