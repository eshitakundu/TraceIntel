# Persistent approval exposure

TraceIntel answers two separate questions: what was notable in the historical transaction, and which ERC-20 permissions exist at the current-state checkpoint.

## Reused architecture

Exposure is computed by `blockchain/exposure_analyzer.py` into `models/exposure.py` contracts and shown by `ExposurePanel.tsx`. The pipeline evaluates historical risk first, then reads current permissions, then hands the result to the agent, which turns each distinct permission into catalog claims (`p0`, `p0:reach`…) and may investigate the live ones further ([agent design](agents.md)). Exposure never changes the historical score.

## Whose permission is it?

A transaction emits Approval events for every owner it touches. Each permission records `owner_role`:

| Role | Meaning | Treatment |
| --- | --- | --- |
| `sender` | The transaction's signer granted it | The sender's own exposure: scored, investigated, advised on |
| `called_contract` | The contract the transaction called granted it, for example a Safe smart wallet executing for its owner, or a router approving from its own balance | Investigated and advised on; labelled "possibly your smart wallet" |
| `other` | Another contract granted it while the transaction executed | Checked and shown separately, not scored or advised on |

The bounded current-state reads cover the sender's permissions first. ERC-4337 smart accounts, whose transactions are sent by a bundler, appear as `other`; this is a documented limitation.

## Data contracts

HistoricalPermission retains token, owner, spender, exact reported amount, maximum-allowance flag, historical block/time and event IDs. CurrentPermissionState holds allowance, balance, spender bytecode presence, optional token name/symbol/decimals, checked time, block number/hash/time, errors and observation IDs. PersistentExposure links these with a deterministic status and independent permission_active boolean. ExposureEvidence holds immutable serialized RPC observations.

Reports use schema 1.2.0 (1.1.0 added the optional exposure field; 1.2.0 added owner roles and the agent's investigation, actions and trace). Older reports remain readable; 1.0.0 reports show that current state was not checked. SQL storage already persists the full versioned report JSON, so no table alteration or data migration is required. Existing Alembic migrations remain authoritative.

## Rules

| Status | Deterministic condition | Meaning |
| --- | --- | --- |
| ACTIVE | Positive current allowance equals the historical amount | Matching permission is active at the checked block |
| PARTIALLY_ACTIVE | Current allowance is positive but lower | Reduced permission remains active |
| REVOKED | Current allowance is zero | Inactive; spending or later changes may explain zero |
| SUPERSEDED | A later Approval event exists for the same tuple, or current amount exceeds the historical amount | Original amount no longer describes the permission |
| UNKNOWN | Allowance could not be validated | No conclusion about active permission |

Repeated events are retained in JSON and historical Approvals. The comparison displays the last event for each token/owner/spender tuple, and its current permission is counted once. SUPERSEDED does not mean inactive: permission_active explicitly identifies whether the queried current allowance is positive. No later transaction or reason for a changed amount is inferred.

A historical zero amount with a current zero amount is labelled inactive; the report does not claim the transaction created a positive permission. An unchanged amount cannot prove permission was continuously active between the two blocks.

## Current-state queries

The analyzer selects one latest block, pins eth_call and eth_getCode to its hash with requireCanonical=true (EIP-1898), and rechecks the block hash afterwards. It reads allowance(owner,spender), balanceOf(owner), symbol(), name(), decimals() and spender bytecode. A 30-second stage timeout yields unknown state while preserving historical results. Maximum 16 distinct permissions are queried concurrently through the existing RPC semaphore. Overflow, unsupported calls and non-standard responses remain explicit unknowns.

If the reference block cannot be validated or changes, all queried values are discarded. Providers without hash-pinned state-call support yield unavailable state rather than silently mixing blocks. Balances and labels can fail independently without losing a valid allowance.

Amounts use exact uint256 integer strings. Metadata is optional and token-reported. Current decimals are used only for labelled display; raw original/current amounts remain available. Very large display values use explicitly approximate compact notation. Zero balance, missing bytecode, or missing metadata never revoke permission or lower historical risk.

## Freshness and persistence

“Now” means the recorded block and checked time. Reports are immutable and do not update while open. Refresh submits through the existing protected job API and creates a new report after the five-minute UTC cache bucket changes. Within the bucket it reuses the report and tells the user to retry within five minutes. Configuration and pipeline version are part of the cache key. Historical block revalidation is preserved.

Each refresh can consume a normal analysis and model budget. Daily persisted caps and the authenticated Cloudflare proxy remain in force. This is snapshot analysis, not background monitoring or wallet scanning.

## Evaluation

make evaluate includes six exposure transition goldens alongside the historical, ownership and agent cases. Tests cover pinned calldata, missing balance, malformed allowance, unavailable blocks, reorganization, citation integrity, and unchanged historical facts/risk.

PYTHONPATH=backend uv run python scripts/verify_exposure_live.py performs an opt-in real Ethereum check without model calls. The recorded approval sample has 13 events across nine distinct tuples. Live values change; offline expected results use labelled synthetic transitions.

## References

The [ERC-20 specification](https://eips.ethereum.org/EIPS/eip-20) defines allowance/balance queries and optional metadata. [EIP-1898](https://eips.ethereum.org/EIPS/eip-1898) defines block-hash-pinned state calls.