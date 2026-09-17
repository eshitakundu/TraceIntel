# Browser fixture provenance

exposure-report.json is an immutable local API report captured from the real Ethereum approval sample on 2026-09-17. It contains public transaction evidence, block-specific current state and validated NOOA selections; no provider credentials. The recorded values are not promised to remain current.

Browser tests use this response offline so CI does not spend RPC/model budgets. The unavailable-state test explicitly alters a copy to exercise failure presentation. Live verification remains a separate opt-in test.
