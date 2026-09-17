# TraceIntel

Evidence-first EVM transaction intelligence. Blockchain facts and risk scores belong to deterministic Python; NOOA will interpret immutable evidence with traceable citations.

## Current status

The foundation includes FastAPI, validated environment configuration, a typed health endpoint, React/TypeScript dashboard, live API connectivity, routing, tests, lint/type/build checks and CI. Transaction analysis, agents, persistence and deployment are subsequent milestones. There is no live public site yet.

## Local development

Requires Python 3.12, uv, Node **22 LTS** (22.12 or newer), npm and Make. Use `nvm install && nvm use` if you use nvm.

```sh
cp .env.example .env
make install
# Two terminals:
make backend
make frontend
```

Open http://localhost:5173. API docs: http://localhost:8000/docs.
Vite proxies /api to FastAPI on port 8000. The connectivity indicator makes an actual HTTP health request.

```sh
make check   # lint, formatting, type checks, tests, production frontend build
make test
curl http://localhost:8000/api/v1/health
```

Settings use TRACEINTEL_ environment variables and validate at startup. Secrets stay in root .env (ignored). Never put provider keys in VITE_* variables: frontend variables are public. /api/v1/health is process liveness, not provider readiness.

## Structure and decisions

backend/app contains API routes, configuration and typed models. backend/tests holds offline checks. frontend/src separates pages, components, hooks and API access. docs and evals document architecture and evaluation contracts.

Evidence → decoding → deterministic signals/scoring → NOOA interpretation → report.
Agents cannot mutate facts or scores. Evidence IDs connect claims to sources. Missing data is a completeness limitation, never an automatic reduction in risk.

Planned persistence uses repository interfaces and migrations: SQLite for development/tests and PostgreSQL for production. Planned hosting is Cloudflare frontend plus Python/FastAPI Docker API. Workers compatibility is independent of backend progress.

See [architecture](docs/architecture.md), [milestones](docs/milestones.md) and [evaluations](evals/README.md).