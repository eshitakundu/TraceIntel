# Reproducible evaluations

Run make evaluate: twelve offline cases verify historical findings, score stability, evidence references, unsupported-claim rejection and current exposure transitions.

- Four labelled synthetic historical approval cases: maximum, finite, revoked and reverted.
- One real Ethereum approval transaction: 13 approval events, two maximum values, historical score 40 without contract enrichment. Repeated events cannot inflate a rule's score.
- One adversarial grounding group: known claim accepted; altered claim text, ID and citation rejected.
- Six labelled synthetic exposure transitions: unchanged maximum, reduced positive, zero, increased, unavailable and zero-to-zero.

ethereum-approval.json retains the real raw transaction/receipt/block for 0xe7ac5477adad86fe9f70854da18b0a182b878773381421418d5bf1a69514645f. Additional Ethereum/Monad acquisition fixtures retain chain provenance. No synthetic transaction is presented as a real on-chain event.

Backend tests separately exercise actual RPC request construction with scripted responses, hash-pinned state calls, reorg rejection, partial metadata/balance, exact amounts, immutable scoring and valid exposure citations. Browser tests use a recorded real report and a clearly synthetic unknown-state variant.

Live checks are opt-in and results are time-dependent:

```sh
PYTHONPATH=backend uv run python scripts/verify_exposure_live.py
PYTHONPATH=backend uv run python scripts/verify_nooa_live.py
cd frontend
TRACEINTEL_LIVE_E2E=1 TRACEINTEL_EXPECT_LIVE_AGENT=1 npm run test:e2e -- --grep approval
```

The exposure check uses no LLM. The other live checks may incur model charges and are bounded. Current quantities are never hard-coded as permanently expected live values.