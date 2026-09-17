# Deployment: Cloudflare + DigitalOcean

Public deployment is deferred until account, SSH host/user and hostnames are supplied. Docker/PostgreSQL execution and Cloudflare deployment packaging have been verified locally.

## API host

Use a Linux DigitalOcean host with Docker Compose and a TLS reverse proxy. Keep the repository's .env only on the host; do not put it in the image.

Set:
- TRACEINTEL_ENVIRONMENT=production
- POSTGRES_PASSWORD to a strong database password
- TRACEINTEL_DATABASE_URL to postgresql+asyncpg://traceintel:PASSWORD@db:5432/traceintel
- TRACEINTEL_PROXY_TOKEN to a random value of at least 32 characters
- OPENROUTER_API_KEY and OPENROUTER_MODEL=openrouter/auto
- RPC and optional explorer settings as needed

URL-encode special characters in the database password when constructing DATABASE_URL.

```sh
docker compose config --quiet
docker compose up -d --build
curl http://127.0.0.1:8000/api/v1/health
```

The API migrates the schema before starting, runs as a non-root user and binds only to host loopback. PostgreSQL uses a persistent named volume and has no published port. Use deploy/Caddyfile with API_DOMAIN set to the API hostname; point DNS there and allow TLS traffic.

Run one API process/replica: interrupted-job recovery is intentionally single-process. Rolling multi-worker deployment requires leases/queue coordination first. Back up PostgreSQL before migrations and test restores. Reports and job budgets persist in PostgreSQL; replacing the API container does not remove them.

The daily LLM job cap is not a dollar cap, especially with auto routing. Set an appropriate OpenRouter key spend cap before public launch.

## Cloudflare frontend

From frontend:
```sh
npm ci
npm run build
npx wrangler login
npx wrangler secret put API_ORIGIN
npx wrangler secret put API_PROXY_TOKEN
npx wrangler deploy
```

API_ORIGIN is the HTTPS API origin. API_PROXY_TOKEN must match TRACEINTEL_PROXY_TOKEN. Keep both out of frontend build variables. Configure the final custom hostname in Cloudflare after the first deployment.

The Worker serves Vite assets with SPA fallback and proxies API/OpenAPI/docs requests. It caps JSON request bodies, sanitizes forwarded headers and returns an explicit 503 if deployment settings are missing. No API keys are embedded in static assets.

## Release verification

Run make check, make evaluate and the browser suite. Verify a real transaction through the public origin, reload/download its stored report, exercise an invalid hash, verify NOOA status and citations, then restart the API and confirm the report survives. Check the real public URL before adding a live link to README.

## Cloudflare Python Workers

Backend development and deployment do not depend on Pyodide. The normal Python image successfully imports and executes NOOA. Python Worker compatibility has not been claimed; it remains an optional separate investigation. The approved production target is Docker.