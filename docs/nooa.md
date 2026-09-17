# NOOA integration

NOOA 0.0.10 is pinned by uv.lock. Python 3.12 imports, real PredictStrategy execution with a scripted transport, and live OpenRouter calls have been verified.

Three restricted roles prioritize transaction facts, contract context and final report selections. Each uses PredictStrategy with max_retries=1: in this NOOA version that means one total attempt, with no validation retry. Each output is capped at 4,000 tokens; prompts request concise JSON selections. The overall sequence has a 90-second timeout and provider retries are disabled.

Agents copy approved claim IDs, text and evidence IDs exactly. Historical facts and current exposure claims share this validation boundary. No generated-code tools are exposed. Unsupported claims, changed citations and malformed output are rejected; deterministic results remain available. Confidence refers to selection confidence, not safety.

OPENROUTER_API_KEY and OPENROUTER_MODEL=openrouter/auto are supported, with TRACEINTEL_OPENROUTER_* aliases. Use one naming style. The adapter prefixes the native model ID with the LiteLLM OpenRouter routing prefix; the resulting double prefix for openrouter/auto is intentional and was verified live.

A larger report initially produced reasoning text instead of valid JSON. Concise selection instructions and a bounded 4,000-token output passed the complete live approval-report browser flow, including exposure claims. Provider/model behavior can still vary; failure remains an explicit report status rather than fabricated interpretation.

Local typing stubs cover NOOA's dynamic decorators. Application schemas and orchestration retain strict mypy validation. Cloudflare/Pyodide compatibility is unverified and independent of the selected normal Python Docker deployment.