# Deployment: existing Cloudflare Worker + Render backend

The production topology is:

```text
traceintel.eshita.dev          -> existing Cloudflare Worker + static assets
traceintel.eshita.dev/api/*    -> Worker proxy -> Render Docker API
                                                  -> Render PostgreSQL
```

Keep frontend/wrangler.jsonc, its ASSETS binding, SPA fallback and Worker proxy. This setup does not use Cloudflare Pages. The Worker is already being configured manually from GitHub; no Cloudflare deployment is performed by the backend setup.

## 1. Render PostgreSQL

Create a durable Render PostgreSQL database in the same account and region as the API. Copy its **internal database URL** into the API's DATABASE_URL runtime secret. Use the direct database connection for migrations. The backend accepts Render's postgres:// or postgresql:// URL and selects the asyncpg driver without changing encoded credentials. TRACEINTEL_DATABASE_URL is an alternative with higher precedence; use only one name.

Use an always-on API and durable database plan for production. Free service sleep can interrupt in-process jobs; inspect Render's resource limits and choose capacity appropriate for NOOA before enabling public traffic. The repository does not provision or purchase resources automatically.

## 2. Render Docker web service

Connect this GitHub repository and use these settings:

| Setting | Value |
| --- | --- |
| Runtime | Docker |
| Root directory | Repository root (leave blank) |
| Dockerfile | ./Dockerfile |
| Docker build context | . |
| Docker command | Leave blank; use the image command |
| Health check path | /api/v1/ready |
| Instances | 1, no autoscaling |
| Pre-deploy command | alembic upgrade head |
| Auto-deploy | After CI checks pass |

The optional root render.yaml Blueprint defines **only the API**, not the frontend or database. It asks for DATABASE_URL and OPENROUTER_API_KEY, and generates TRACEINTEL_PROXY_TOKEN. Review the chosen Render compute plan during setup. If you already created the API manually, apply the table and variables below instead of creating a duplicate service.

Set these Render runtime variables/secrets:

| Name | Value |
| --- | --- |
| DATABASE_URL | Render PostgreSQL internal connection URL (secret) |
| TRACEINTEL_ENVIRONMENT | production |
| TRACEINTEL_PROXY_TOKEN | Random secret of at least 32 characters; Blueprint generates one |
| OPENROUTER_API_KEY | Your existing OpenRouter key (secret) |
| OPENROUTER_MODEL | openrouter/auto |
| TRACEINTEL_CORS_ORIGINS | ["https://traceintel.eshita.dev"] |
| TRACEINTEL_SKIP_MIGRATIONS | true **only when the pre-deploy migration command is configured** |
| TRACEINTEL_MAX_CONCURRENT_ANALYSES | 2 |
| TRACEINTEL_REQUESTS_PER_HOUR | 20 |
| TRACEINTEL_DAILY_ANALYSES | 100 |
| TRACEINTEL_DAILY_LLM_ANALYSES | 20 |

Render supplies PORT; the image binds 0.0.0.0:$PORT (local fallback 8000). Do not set a frontend VITE_* backend URL. Your local ignored .env is not copied to Render: add secrets in its dashboard.

Optional TRACEINTEL_ETHEREUM_RPC_URL, TRACEINTEL_MONAD_RPC_URL and TRACEINTEL_EXPLORER_API_KEY configure your providers. Keep TRACEINTEL_TRACES_ENABLED=false unless the RPC supports tracing. Missing provider data stays explicit. Set an OpenRouter key spending cap; the daily job limit is not a dollar limit.

For manual services without pre-deploy support, omit TRACEINTEL_SKIP_MIGRATIONS: the image migrates before listening. Do not skip migrations without running them elsewhere.

## 3. Connect the existing Worker after Render supplies the URL

In **Cloudflare Dashboard → Workers & Pages → existing TraceIntel Worker → Settings → Variables and Secrets**, add these **runtime** entries:

| Name | Type | Exact value to supply |
| --- | --- | --- |
| API_ORIGIN | Plaintext variable (or secret) | https://YOUR-RENDER-SERVICE.onrender.com |
| API_PROXY_TOKEN | Secret | Exact same value as Render's TRACEINTEL_PROXY_TOKEN |

API_ORIGIN is only the HTTPS origin: no /api, /api/v1, query string or path. The Worker appends the incoming request path. Keep the existing traceintel.eshita.dev domain/route and ASSETS binding. Apply the runtime settings to the production Worker through your existing manual workflow; there is no repository Wrangler change to make.

Do **not** put the OpenRouter key, database URL or Render API token in Cloudflare. API_PROXY_TOKEN is the shared origin-authentication secret, not a Render account API token. It is never shipped to the browser.

## 4. Verify the connection

1. Open https://YOUR-RENDER-SERVICE.onrender.com/api/v1/ready. Expect HTTP 200 with status ok.
2. Open https://traceintel.eshita.dev/api/v1/health and /api/v1/ready. Both should return JSON.
3. Submit the approval sample from the public dashboard. Verify job progress, Then → Now state, coverage and NOOA status.
4. Reload and download the stored report. Restart/redeploy the API and retrieve the same report again.
5. A direct Render analysis POST without the shared token must be rejected. Do not paste tokens into screenshots or public logs.

Worker 503 "API deployment is not configured" means a runtime setting is missing. An origin authorization error means the two proxy token values differ. A Worker 502 means the backend is unreachable or timed out. Render readiness 503 means persistence or job coordination is unavailable.

## Restart and migration behavior

Alembic migration 0002 adds nullable owner/lease columns to jobs without altering immutable reports. Each process renews its own job leases every 15 seconds; leases expire after 60 seconds. Startup and periodic recovery mark only expired/unowned jobs retryable. A replacement instance therefore leaves healthy jobs on the outgoing instance alone.

Shutdown cancels owned work and marks only that process's unfinished jobs interrupted. A lost lease cannot revive a terminal job. Heartbeat failure stops local analysis and causes readiness/new submissions to fail closed. A killed process's jobs become retryable after lease expiry and the next recovery sweep.

Keep one configured API instance/worker. Leases protect deployment overlap; queue concurrency remains per-process. Reports, request budgets and cache keys are in PostgreSQL. Back up the database before migrations. Migration 0002's first adoption from an older unleased deployment should happen with old analysis work drained.

Existing compose.yml and deploy/Caddyfile remain optional self-hosted Docker tooling; Render does not need Caddy or a local persistent disk.

## References

- [Render Docker deployment](https://render.com/docs/docker)
- [Render PostgreSQL connections](https://render.com/docs/postgresql-creating-connecting)
- [Render health checks](https://render.com/docs/health-checks)
- [Render Blueprint specification](https://render.com/docs/blueprint-spec)