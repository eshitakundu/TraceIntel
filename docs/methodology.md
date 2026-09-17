# Risk methodology v1.0.0

Scores describe observed indicators, not maliciousness, loss probability, or safety.

| Rule | Points | Trigger |
|---|---:|---|
| UNLIMITED_TOKEN_APPROVAL | 30 | Successful ERC20-pattern Approval equals 2^256 - 1 |
| NFT_OPERATOR_APPROVAL | 30 | Successful ApprovalForAll is true |
| TOKEN_APPROVAL | 10 | Positive finite ERC20-pattern Approval |
| CONTRACT_SPENDER | 10 | Positive approval and spender bytecode at block end |
| UNVERIFIED_TARGET | 12 | Successful explorer lookup explicitly reports no source |
| PROXY_DETECTED | 0 | Nonzero EIP-1967 implementation/beacon |
| EXECUTION_STATUS | 0 | Receipt success/failure |

Aggregate = min(100, sum(max(points) per distinct rule code)). Repeated logs cannot multiply a rule's contribution. Bands: 0 minimal, 1–19 low, 20–49 moderate, 50–79 high, 80–100 critical. No negative weights.

Missing information never subtracts points. Completeness is reported separately and a low observed score with incomplete evidence must not be interpreted as low actual risk. Unknown verification is not labelled unverified.

Failed transactions do not produce completed asset movements or approval events. Gas is charged for failed transactions. ERC721 token IDs are not fungible amounts. Event patterns can be spoofed; decoding does not attest token compliance. Emitted allowance is not necessarily the current allowance.

Contract state is queried at block end, not the exact intra-block execution position. Explorer metadata is current, not historical. Proxy detection covers EIP-1967, not every custom pattern. Without traces, internal native movements and revert information are unavailable. No balance reconciliation or token-price valuation is claimed.

## Current exposure is separate

ERC-20 current-state comparisons do not alter this historical score. See [persistent exposure methodology](exposure.md) for status definitions, pinned current allowance queries, freshness and limitations.
