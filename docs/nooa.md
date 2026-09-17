# NOOA integration

Pinned by uv.lock (NOOA 0.0.10). Python 3.12 imports and real PredictStrategy execution are tested with NOOA's scripted transport. Live OpenRouter execution requires configuration and is separately verified.

Three restricted roles have different purposes: transaction prioritization, contract-context selection when contracts exist, and final synthesis. Each uses PredictStrategy with zero validation retries; no generated-code tools are exposed. The whole sequence has a 90-second timeout.

The public report uses an approved claim catalog. Agents select and order cited claims and choose verification guidance; exact claim text, ID and evidence references must match the catalog. This deliberately rejects unsupported wording instead of attempting to prove arbitrary prose correct. Confidence describes the agent's selection, never safety. All original evidence, coverage and signals remain visible independently of agent selections.

The adapter has narrow local stubs because NOOA's top-level dynamic decorators are not fully typed. Application schemas, validation and orchestration remain under strict mypy checking.

Cloudflare/Pyodide compatibility has not been established and does not block the normal Docker backend.