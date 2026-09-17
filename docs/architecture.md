# Architecture

The runnable system uses Python 3.12/FastAPI and Node 22/React/Vite.

## Evidence boundary

Raw RPC acquisition cross-checks transaction, receipt and block identity. The decoder emits frozen Pydantic models with tuple collections. Nested raw objects are stored as JSON text, avoiding shallow-frozen dictionaries.

Evidence IDs include chain, transaction and source location. Event IDs use receipt log index. Contract/proxy/token evidence records the query block; explorer evidence is explicitly current metadata. Risk signals and agent claims retain these IDs.

Rules operate only on decoded evidence. Aggregation uses fixed weights, no negative adjustments and one contribution per rule code. Coverage is independent of the score.

## Interpretation boundary

NOOA PredictStrategy handles transaction prioritization, contract context and final organization. It receives an approved cited-claim catalog, not provider credentials or unrestricted tools. Selected text, IDs and references must match. Verification suggestions come from an allowed vocabulary. Agent output has no field for replacing evidence or numerical scores.

## Services and persistence

AnalysisService owns sequencing and bounded async work. It depends on ReportRepository, not SQLAlchemy or SQL. The SQL adapter supports SQLite and PostgreSQL, with schema history in Alembic.

Jobs persist real stages. Unique cache keys suppress concurrent duplicate work. Cache buckets incorporate chain/hash, analyzer version, date and configured interpretation identity. Cached completed reports revalidate their block hash before reuse. Stored reports remain as-of snapshots.

A semaphore bounds active pipelines; the queue, per-client requests, total daily analyses and model jobs are capped. Atomic SQL budget updates work across database connections. The current process owns its tasks and marks interrupted jobs retryable on startup; multiple simultaneous API processes are unsupported.

## Hosting

Cloudflare serves assets and proxies API requests to a DigitalOcean Docker service. A shared origin token protects POST requests; client identity is accepted only through that authenticated proxy. PostgreSQL is persistent and private to the deployment network. No secrets are bundled into frontend assets.

## Persistent exposure extension

Historical scoring is followed by a separate current-state permission analyzer. It uses the existing read-only RPC client and hash-pinned calls, returns immutable typed exposure observations, and contributes approved claims to NOOA. Historical facts and scores remain unchanged. Report JSON adds an optional versioned exposure field without changing SQL tables. Five-minute snapshot cache buckets allow fresh checks while retaining every saved report. See [exposure](exposure.md).
