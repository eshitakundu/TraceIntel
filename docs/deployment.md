# Deployment

The public app is [traceintel.eshita.dev](https://traceintel.eshita.dev). Cloudflare serves React static assets and proxies `/api/*` to [the Render API](https://traceintel-api.onrender.com), which persists jobs and reports in Render PostgreSQL and queries Ethereum/Monad RPC providers. NOOA uses OpenRouter downstream of evidence.

## Render: current manual configuration

The service is configured manually. There is no Blueprint to apply; the obsolete paid pre-deploy configuration was removed.

| Setting | Value |
| --- | --- |
| Runtime | Docker |
| Root directory | Repository root (blank) |
| Dockerfile | `./Dockerfile` |
| Build context | `.` |
| Docker Command | **Blank** — use the image CMD |
| Health check | `/api/v1/ready` |
| Region | Singapore |
| Compute | Free web service, one instance |
| Database | Render PostgreSQL |
| Migrations | Container startup; no pre-deploy command |

Do not set Docker Command to `./Dockerfile`: it overrides the image command. `backend/start.sh` validates Render's `PORT`, runs `alembic upgrade head`, then uses `exec uvicorn` with one worker and a 20-second graceful shutdown timeout. Leave `TRACEINTEL_SKIP_MIGRATIONS` unset or false. That escape hatch is only for environments that already run migrations separately.

Free compute sleeps after inactivity. The frontend checks `/api/v1/ready`, displays “Backend waking up…” after a failed or timed-out attempt, and retries with bounded backoff. Eight attempts have an eight-second request timeout and delays of 3, 5, 8, 10, 12, 14 and 15 seconds (at most about 131 seconds). A valid readiness response enables analysis automatically. Each submission rechecks readiness because a previously connected free service can sleep while the page remains open. In-form activity shows the current step and elapsed time; submission requests time out after 35 seconds. An interrupted POST is not replayed automatically because acceptance may be ambiguous; the UI preserves input and rechecks connectivity for an explicit retry. Exhaustion displays an unavailable state with manual retry. Informational pages remain usable.

### Runtime settings

| Variable | Configuration |
| --- | --- |
| `DATABASE_URL` | Existing Render PostgreSQL internal connection URL (secret) |
| `TRACEINTEL_ENVIRONMENT` | `production` |
| `TRACEINTEL_PROXY_TOKEN` | Existing shared origin secret; must match the Worker |
| `OPENROUTER_API_KEY` | Backend-only secret |
| `OPENROUTER_MODEL` | `openrouter/auto` |
| `TRACEINTEL_CORS_ORIGINS` | `["https://traceintel.eshita.dev"]` |
| `TRACEINTEL_MAX_CONCURRENT_ANALYSES` | `2` |
| `TRACEINTEL_REQUESTS_PER_HOUR` | `20` |
| `TRACEINTEL_DAILY_ANALYSES` | `100` |
| `TRACEINTEL_DAILY_LLM_ANALYSES` | `20` |

The backend normalizes Render's PostgreSQL URL to asyncpg. `TRACEINTEL_DATABASE_URL` takes precedence over `DATABASE_URL`; configure only one. Optional `TRACEINTEL_ETHEREUM_RPC_URL`, `TRACEINTEL_MONAD_RPC_URL` and `TRACEINTEL_EXPLORER_API_KEY` select providers. Keep tracing disabled unless the provider supports it. Local `.env` is ignored and is not deployed.

## Cloudflare Worker

`frontend/wrangler.jsonc` preserves the ASSETS binding, SPA fallback and API/docs proxy routing. It stores the non-secret `API_ORIGIN=https://traceintel-api.onrender.com` and declares `API_PROXY_TOKEN` under `secrets.required`, supported by the installed Wrangler schema. This declaration provides development validation/type-generation metadata; it does not provision or rotate the secret.

Keep `API_PROXY_TOKEN` configured as a **runtime secret** in the existing Worker's Variables and Secrets settings. It must match Render's existing `TRACEINTEL_PROXY_TOKEN`. Never put its value in configuration files, browser variables, screenshots or logs. No other backend credentials belong in Cloudflare. Preserve the existing custom domain when deploying.

```sh
cd frontend
npm ci
npm run build
npx wrangler deploy --dry-run
# With the existing account and runtime secret configured:
npx wrangler deploy
```

The Worker serves `favicon.svg` and the 16/32px PNG variants directly from Vite's copied public assets. Only API and documentation routes run through the backend proxy.

## Verification and operation

Check these readiness endpoints for valid JSON with `status: "ok"` and `service: "traceintel-api"`:

- [Public proxy readiness](https://traceintel.eshita.dev/api/v1/ready)
- [Origin readiness](https://traceintel-api.onrender.com/api/v1/ready)

Then exercise both recorded network examples, progress, report reload and JSON download. Readiness tests the database and job coordination, not RPC provider health. Worker 503 indicates missing configuration; 502 indicates an unreachable/timed-out origin. Origin readiness 503 indicates unavailable persistence or coordination.

Keep one configured API instance/worker. Process-owned leases protect temporary deployment overlap: heartbeat every 15 seconds, expiry after 60 seconds. Shutdown interrupts only owned jobs; recovery marks expired/unowned jobs retryable. Lost leases cannot revive terminal jobs. Heartbeat failure stops local work and fails readiness/submissions closed. Free-service sleep can interrupt in-process analysis; persisted reports survive in PostgreSQL.

Back up PostgreSQL before migrations. Initial adoption of lease migration 0002 from an older unleased deployment requires draining old work. Set provider spending limits independently of application job limits.

`compose.yml` remains useful for local Docker/PostgreSQL integration. It binds the API to loopback and requires database settings in the ignored root environment file. Caddy is not part of the deployment.
