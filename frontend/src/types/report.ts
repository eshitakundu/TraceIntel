export interface Evidence {
  id: string;
  source: string;
  description: string;
  data_json: string;
}
export interface Coverage {
  area: string;
  status: "available" | "partial" | "unavailable" | "not_applicable";
  reason: string;
}
export interface Transaction {
  hash: string;
  sender: string;
  recipient: string | null;
  created_contract: string | null;
  nonce: number;
  value_wei: string;
  gas_used: number;
  gas_price_wei: string;
  gas_fee_wei: string;
  status: "success" | "failed";
  block_number: number;
  block_hash: string;
  timestamp: number;
  selector: string | null;
  function: string | null;
  arguments_json: string | null;
  calldata: string;
  evidence_ids: string[];
}
export interface Movement {
  standard: string;
  token: string;
  sender: string;
  recipient: string;
  amount_raw: string;
  token_id: string | null;
  symbol: string | null;
  decimals: number | null;
  evidence_ids: string[];
}
export interface Approval {
  standard: string;
  token: string;
  owner: string;
  spender: string;
  amount_raw: string;
  unlimited: boolean;
  evidence_ids: string[];
  owner_role?: OwnerRole | null;
}
/** Who granted a permission relative to the transaction sender. */
export type OwnerRole = "sender" | "called_contract" | "other";
export interface Contract {
  address: string;
  kind: string;
  verification: string;
  name: string | null;
  proxy: string;
  implementation: string | null;
  abi_json: string | null;
  state?: "historical" | "current";
  evidence_ids: string[];
}
export interface RiskSignal {
  code: string;
  severity: string;
  score: number;
  title: string;
  description: string;
  reason: string;
  source: string;
  evidence_ids: string[];
}
export interface CitedClaim {
  id: string;
  text: string;
  evidence_ids: string[];
}
export type ActionKind =
  "consider_revoking" | "verify_spender" | "review_upgrade_control";
export interface PermissionAction {
  permission_id: string;
  action: ActionKind;
  reasons: CitedClaim[];
}
export interface TraceStep {
  actor: "planner" | "tool" | "reporter" | "validator";
  name: string;
  detail: string;
  status: "ok" | "rejected" | "error" | "skipped";
  duration_ms: number;
  claim_ids: string[];
}
export interface Investigation {
  planner: "model" | "baseline";
  claims: CitedClaim[];
  evidence: Evidence[];
  coverage: Coverage[];
  rounds: number;
  tool_calls: number;
}
export interface AgentSelection {
  summary: CitedClaim[];
  important_findings: CitedClaim[];
  uncertainties: CitedClaim[];
  recommended_checks: string[];
  /** Legacy reports only: a model self-reported number, never displayed. */
  confidence?: number | null;
  actions?: PermissionAction[];
}
export interface Report {
  schema_version: string;
  exposure?: ExposureAnalysis | null;
  id: string;
  created_at: string;
  chain: string;
  transaction_hash: string;
  explorer_url: string;
  decoded: {
    transaction: Transaction;
    movements: Movement[];
    approvals: Approval[];
    evidence: Evidence[];
    coverage: Coverage[];
  };
  contracts: Contract[];
  coverage: Coverage[];
  risk: {
    version: string;
    score: number;
    level: string;
    signals: RiskSignal[];
    interpretation: string;
  };
  interpretation: {
    status: string;
    model: string | null;
    result: AgentSelection | null;
    reason: string | null;
    author?: "model" | "baseline" | null;
    investigation?: Investigation | null;
    trace?: TraceStep[];
    llm_calls?: number;
    duration_ms?: number;
  };
}
export interface Job {
  id: string;
  chain: string;
  transaction_hash: string;
  status: "queued" | "running" | "complete" | "failed";
  stage: string;
  report_id: string | null;
  error: string | null;
}
export interface Chain {
  slug: string;
  name: string;
  chain_id: number;
  native_symbol: string;
  explorer_url: string;
}

export interface CurrentPermissionState {
  allowance_raw: string | null;
  balance_raw: string | null;
  spender_has_code: boolean | null;
  symbol: string | null;
  name: string | null;
  decimals: number | null;
  block_number: number | null;
  block_hash: string | null;
  block_timestamp: number | null;
  checked_at: string;
  errors: string[];
  evidence_ids: string[];
}
export interface PersistentExposure {
  id: string;
  historical: {
    token: string;
    owner: string;
    spender: string;
    allowance_raw: string;
    unlimited: boolean;
    block_number: number;
    timestamp: number;
    evidence_ids: string[];
    owner_role?: OwnerRole | null;
  };
  current: CurrentPermissionState;
  status: "ACTIVE" | "PARTIALLY_ACTIVE" | "REVOKED" | "SUPERSEDED" | "UNKNOWN";
  permission_active: boolean | null;
  summary: string;
  evidence_ids: string[];
}
export interface ExposureAnalysis {
  version: string;
  checked_at: string;
  permissions: PersistentExposure[];
  evidence: Evidence[];
  coverage: Coverage;
  limitations: string[];
}
