# Evaluations

`make evaluate` runs 24 offline cases in CI. No network, no model provider, no RPC.

| Group | Cases | What passing means |
| --- | --- | --- |
| Historical rules | 4 | Synthetic approvals (maximum, finite, revoked, reverted) produce the labelled score and rule codes, and every signal cites existing evidence |
| Ownership on a real transaction | 1 | The recorded Ethereum approval transaction decodes to 13 approval events: the sender's 4 finite WETH approvals, and 9 granted by contracts mid-transaction, including both maximum values. Only the sender's are scored (10 without contract enrichment) |
| Exposure transitions | 6 | Unchanged maximum, reduced, zero, increased, unavailable and zero-to-zero current states map to the right status, liveness and citations |
| Agent scenarios | 8 | Labelled situations on top of the real transaction, each with a scripted on-chain world (below). The agent's advice must match the label, cite the required claims, surface the required uncertainties, stay grounded and stay within budget |
| Agent guardrails | 5 | The model itself is scripted to misbehave (below), and the system must contain it |

**Agent scenarios.** spender upgraded after the approval · spender is a key-held account · single key controls spender upgrades · recognised router, unchanged, finite allowance · unrecognised contract, unchanged, finite · recognised protocol, allowance raised to unlimited since · allowance already revoked · approval-block state pruned by the provider.

**Guardrails.** planner calls outside the action space (duplicate, unknown permission, another owner's permission) are rejected and only valid calls run · an invented claim is rejected and repaired after validator feedback · advice on another owner's permission is rejected twice and falls back to the baseline · an injected token symbol never reaches model input · a provider that rejects the key degrades to rule-based advice with a safe, specific reason.

"Grounded" means every claim in the briefing exists verbatim in the code-built catalog and every evidence ID it cites exists in the report. The same scenarios run as individual pytest cases in `backend/tests/test_agents.py`.

## Provenance

`cases/ethereum-approval.json` holds the real raw transaction, receipt and block for `0xe7ac5477adad86fe9f70854da18b0a182b878773381421418d5bf1a69514645f`. Agent scenarios keep that real evidence and script only the current on-chain state, which is labelled per scenario. Other Ethereum and Monad fixtures retain chain provenance. No synthetic transaction is presented as a real on-chain event.

Backend tests also cover RPC request construction, hash-pinned state calls, reorg rejection, pruned-state fallback, EIP-7702 detection, rate-limit retries, lease loss, heartbeat recovery and budget refunds. Browser tests use a recorded real report and a clearly synthetic unknown-state variant.

## Live checks (opt-in)

```sh
# Real Ethereum current-state check, no model:
PYTHONPATH=backend uv run python scripts/verify_exposure_live.py
# Real model vs the rule-based baseline on the agent scenarios (charges apply):
OPENROUTER_API_KEY=... OPENROUTER_MODEL=... PYTHONPATH=backend uv run python scripts/verify_nooa_live.py
```

The live agent evaluation writes `evals/results/live-<model>.json` with, for the model and for the baseline: advice accuracy against the labels, grounding rate, how often the model authored the briefing, repairs, model calls and median latency. Because the on-chain world is scripted, only the model varies between runs.
