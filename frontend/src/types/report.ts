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
}
export interface Contract {
  address: string;
  kind: string;
  verification: string;
  name: string | null;
  proxy: string;
  implementation: string | null;
  abi_json: string | null;
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
export interface AgentSelection {
  summary: CitedClaim[];
  important_findings: CitedClaim[];
  uncertainties: CitedClaim[];
  recommended_checks: string[];
  confidence: number;
}
export interface Report {
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
