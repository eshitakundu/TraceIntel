# Browser fixture provenance

`exposure-report.json` is an immutable schema 1.2.0 report captured from production (traceintel.eshita.dev) for the real Ethereum approval sample `0xe7ac5477…645f` on 2026-10-13. Its briefing was written by the model, and its trace records the validator rejecting the model's first answer (an empty summary) and accepting the repaired one. It contains public transaction evidence, block-pinned current state and the agent's investigation; no provider credentials. Recorded values are not promised to remain current.

Browser tests use it offline so CI spends no RPC or model budget. The unavailable-state test alters a copy to exercise failure presentation. Live verification remains a separate opt-in test.
