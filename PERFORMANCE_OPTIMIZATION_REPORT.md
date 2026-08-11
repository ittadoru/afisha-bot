# Performance optimization report

## Measurement protocol

Each runtime scenario must be run five times with the same account, device, viewport and network profile. The median is reported. Differences below 5% are treated as noise.

Scenarios: cold Mini App to map, warm start, Map → List, Company with avatars, event detail, own/public profile, and a 50-message chat.

## Baseline

Baseline production-build assets captured before implementation:

| Asset | Raw | gzip |
|---|---:|---:|
| Global CSS | 224.94 kB | 42.05 kB |
| Mini App | 160.79 kB | 44.28 kB |
| Shared runtime/config | 225.06 kB | 71.53 kB |
| Event map | 1,039.89 kB | 278.05 kB |

Runtime WebView medians require a deployed Telegram environment and are intentionally left pending rather than replaced by synthetic guesses.

## Implemented changes

- Responsive, immutable media contracts for avatars, event photos and profile backgrounds.
- Lazy admin and MapLibre CSS chunks.
- Shared GET deduplication/cache foundation with logout cleanup.
- Visibility-aware chat polling with bounded backoff.
- Static map marker glyphs without one React root per marker.
- gzip delivery for text assets.

## Final measurements

Run the same five-pass protocol after deployment and record time to useful UI, LCP, CLS, map readiness, requests, JS/CSS/image bytes, retries and avatar fallback count here. Percentage change is `(baseline - final) / baseline × 100`.

The verified production build now has:

| Asset | Before raw | After raw | Change | Before gzip | After gzip | Change |
|---|---:|---:|---:|---:|---:|---:|
| Initial/global CSS | 224.94 kB | 140.01 kB | **−37.8%** | 42.05 kB | 29.28 kB | **−30.4%** |
| Initial runtime/config JS | 225.06 kB | 193.68 kB | **−13.9%** | 71.53 kB | 61.65 kB | **−13.8%** |
| Mini App feature chunk | 160.79 kB | 125.13 kB | **−22.2%** | 44.28 kB | 35.53 kB | **−19.8%** |
| Map JS chunk | 1,039.89 kB | 1,035.15 kB | −0.5% (noise) | 278.05 kB | 276.05 kB | −0.7% (noise) |

Admin CSS (16.59 kB) and JS (49.86 kB) are now separate lazy assets and do not execute on the user domain. MapLibre CSS (69.80 kB) is also separated from initial CSS and loads with the map route.

Runtime acceleration cannot be claimed until the Telegram WebView passes are complete. Based on transferred code alone, the measurable reduction is about 14% for initial runtime JS, 20% gzip for the Mini App feature chunk, and 30% for initial CSS; actual time-to-map may differ with device and network.
