# Local verification record

Verified on 2026-09-17. Public deployment was explicitly deferred.

| Check | Result |
| --- | --- |
| Python lint / strict mypy | Passed; 48 typed application modules |
| SQLite backend suite | 36 passed |
| PostgreSQL backend suite | 36 passed on PostgreSQL 17 |
| Frontend / Worker unit tests | 8 passed |
| Offline Chromium browser tests | 6 passed |
| Live approval browser flow | Passed, including current-state reads and available NOOA interpretation |
| Deterministic evaluations | 12 passed |
| Vite production build | Passed using Node 22 |
| Cloudflare Wrangler dry run | Passed |
| Final Python 3.12 Docker image | Built, health OK, process UID 10001 |
| Restart persistence | Stored SQLite and PostgreSQL reports retrieved after API replacement/restart |

The real Ethereum approval transaction contains 13 events across nine distinct token/owner/spender tuples. Current allowance, balance, metadata and spender bytecode were resolved at the recorded block. The snapshot displayed three active permissions; this is a recorded result, not a prediction of future state. Exact values, evidence IDs and the checked timestamp are in the browser fixture and downloadable report.

Live NOOA used the user's configured openrouter/auto model. A previous large-output synthesis failure was rejected safely; bounded concise output then passed the complete live flow. The final timeout safeguard was exercised with a deterministic delayed RPC test.

Screenshots show the real local application:
- [Homepage](screenshots/landing.png)
- [Dashboard summary](screenshots/exposure-dashboard.png)
- [Then vs now](screenshots/exposure-comparison.png)
- [Mobile comparison](screenshots/exposure-mobile.png)
- [NOOA interpretation](screenshots/nooa-analysis.png)

Two upstream test-client deprecation warnings remain (Starlette/httpx and anyio). No test failed. GitHub Actions is configured but no hosted workflow run is claimed. Cloudflare account deployment, production domains and DigitalOcean SSH deployment remain deferred.