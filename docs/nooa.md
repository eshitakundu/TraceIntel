# NOOA integration

[NOOA](https://pypi.org/project/nooa/) (NVIDIA's agent framework, pinned at 0.0.10 in `uv.lock`) provides the model calls behind the two model-backed roles: the `Investigator` planner and the `Reporter`. Both use `PredictStrategy`, which turns a typed Python method signature into a JSON-schema-constrained request and validates the response against the return type.

| Role | Signature | Output |
| --- | --- | --- |
| `Investigator.plan` | permissions, findings so far, calls already run, budget | `PlanStep`: up to 4 `ToolCall(tool, permission_id)` and `done` |
| `Reporter.brief` | the full claim catalog, actionable permission IDs, validator feedback | `ReportDraft`: claim IDs for summary, findings and uncertainties; actions with cited IDs; checks |

`PredictStrategy` gets `max_retries=2`, so a malformed or schema-invalid response gets one retry with NOOA's own error feedback. Grounding problems (unknown IDs, out-of-scope actions) are caught by TraceIntel's validator, which gives the reporter one repair with precise feedback. Output is capped at 600–700 tokens because the model returns IDs, not prose.

## Configuration

`OPENROUTER_API_KEY` and `OPENROUTER_MODEL` (or their `TRACEINTEL_OPENROUTER_*` aliases) enable the model roles. The client adds the LiteLLM `openrouter/` routing prefix to the configured model, so `openrouter/auto` becomes `openrouter/openrouter/auto`. Each model call has a 30-second timeout with provider retries disabled. `TRACEINTEL_DAILY_LLM_ANALYSES` caps how many analyses may use the model each day.

Pin a model with reliable structured (JSON schema) output rather than relying on automatic routing, and compare candidates with `scripts/verify_nooa_live.py` before switching. When the model is missing, fails or exceeds the daily budget, the deterministic baseline runs instead, and the report names the reason, for example "Model unavailable: the provider rejected the API key (AuthenticationError)".

## Testing without a provider

`nooa.unifiedllm.fake.FakeLLMClient` accepts a list of scripted responses. The evaluation suite uses it to replay multi-turn trajectories (plans, invalid calls, invented claims, repairs) without network access. See [the agent design](agents.md) and [evaluations](../evals/README.md).

## Platform note

NOOA imports `fcntl` and registers a `SIGUSR2` handler at import time, so the backend runs on Linux and macOS but not natively on Windows. Use WSL or Docker on Windows. The frontend runs anywhere.
