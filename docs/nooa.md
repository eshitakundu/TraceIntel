# NOOA integration

NOOA 0.0.10 is pinned by uv.lock and runs in the Python Docker backend.

Three restricted roles prioritize transaction facts, contract context and final report selections. Each uses PredictStrategy with max_retries=1: in this NOOA version that means one total attempt, with no validation retry. Each output is capped at 4,000 tokens; prompts request concise JSON selections. The overall sequence has a 90-second timeout and provider retries are disabled.

Agents copy approved claim IDs, text and evidence IDs exactly. Historical facts and current exposure claims share this validation boundary. No generated-code tools are exposed. Unsupported claims, changed citations and malformed output are rejected; deterministic results remain available. Confidence refers to selection confidence, not safety.

OPENROUTER_API_KEY and OPENROUTER_MODEL=openrouter/auto are supported, with TRACEINTEL_OPENROUTER_* aliases. Use one naming style. The adapter prefixes the native model ID with the LiteLLM OpenRouter routing prefix; the resulting double prefix for openrouter/auto is intentional and was verified live.

Model output can be malformed or unavailable; validation failures remain explicit report statuses. Local typing stubs cover NOOA's dynamic decorators while application schemas and orchestration retain strict mypy validation.
