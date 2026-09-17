# Developer API

Local base: http://localhost:8000/api/v1. Production clients use the public Cloudflare origin. OpenAPI: /openapi.json; interactive docs: /docs.

| Method | Path | Result |
|---|---|---|
| GET | /health | Process liveness; not provider readiness |
| GET | /ready | Database and job-lease readiness; no paid provider calls |
| GET | /chains | Supported chain metadata without RPC credentials |
| POST | /analyses | 202 persisted job, or cached existing job |
| GET | /analyses/{uuid} | Status, actual stage, report ID or safe error |
| GET | /reports/{uuid} | Immutable stored report |
| GET | /reports/{uuid}/download | JSON attachment |

Submit:
```json
{
  "chain": "ethereum",
  "transaction_hash": "0xe7ac5477adad86fe9f70854da18b0a182b878773381421418d5bf1a69514645f"
}
```

Poll the returned job ID until complete or failed. Complete jobs include report_id. Stages may finish between polls; the API never fabricates progress percentages.

Errors: 422 invalid hash/network; 404 missing job/report; 413 oversized body; 429 request/queue/daily limit; 503 cache revalidation unavailable. Jobs record pending/not-found transactions, provider failures and timeouts as failed. RPC/provider error bodies and credential-bearing URLs are not exposed.

POST bodies require Content-Length and at most 4096 bytes. Default limits: 20 submissions per client/hour, 100 new analyses/day, 20 interpreted analyses/day, two simultaneous pipelines and a queue bounded at 16 tasks. A NOOA pipeline uses at most three model calls with bounded output and no retries. Daily limits are UTC buckets.

Production writes require the private proxy token at the origin; the public Worker supplies it. The Worker forwards Cloudflare's client IP and replaces caller-supplied identity headers. Direct origin users cannot bypass the public request budget without the token.

Amounts are decimal strings. Never coerce uint256 amounts into JavaScript numbers. Claims contain evidence_ids linking to decoded.evidence or exposure.evidence entries. Coverage and numerical risk are separate. Original reports remain immutable snapshots; requesting a new analysis revalidates a cached block hash before reuse.

## Exposure snapshots

Schema 1.1.0 reports include exposure: permissions, current-state observations, coverage and checked time. Existing 1.0.0 reports may have exposure=null. POST /analyses reuses a five-minute UTC snapshot bucket; after it changes, a new job/report is created. GET never mutates a saved report. Status and permission_active are deterministic and independent of historical risk. See [exposure contracts](exposure.md).
