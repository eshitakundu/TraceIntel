import approvalFixture from "../../e2e/fixtures/exposure-report.json";
import type { Report, TraceStep, Transaction } from "../types/report";

export type SavedExampleId = "approval" | "ethereum" | "monad";

const approval = structuredClone(approvalFixture) as unknown as Report;
approval.id = "saved-approval";

const savedTrace: TraceStep[] = [
  {
    actor: "planner",
    name: "load_recorded_transaction",
    detail: "Loaded the recorded transaction evidence.",
    status: "ok",
    duration_ms: 12,
    claim_ids: [],
  },
  {
    actor: "tool",
    name: "decode_transaction",
    detail: "Decoded the call and receipt from the saved chain response.",
    status: "ok",
    duration_ms: 28,
    claim_ids: [],
  },
  {
    actor: "validator",
    name: "validate_evidence",
    detail: "Validated that every displayed fact exists in the recording.",
    status: "ok",
    duration_ms: 9,
    claim_ids: [],
  },
  {
    actor: "reporter",
    name: "build_report",
    detail: "Built this offline-safe report from deterministic evidence.",
    status: "ok",
    duration_ms: 14,
    claim_ids: [],
  },
];

function recordedReport(
  id: Exclude<SavedExampleId, "approval">,
  chain: string,
  explorerUrl: string,
  transaction: Partial<Transaction> & Pick<Transaction, "hash">,
): Report {
  const report = structuredClone(approval) as Report;
  report.id = "saved-" + id;
  report.chain = chain;
  report.transaction_hash = transaction.hash;
  report.explorer_url = explorerUrl;
  report.exposure = null;
  report.decoded = {
    transaction: {
      ...report.decoded.transaction,
      ...transaction,
      evidence_ids: [],
    },
    movements: [],
    approvals: [],
    evidence: [],
    coverage: [],
  };
  report.contracts = [];
  report.coverage = [
    {
      area: "Recorded transaction",
      status: "available",
      reason: "Loaded from the repository's recorded chain fixture.",
    },
    {
      area: "Current exposure",
      status: "unavailable",
      reason: "A live RPC check requires the backend.",
    },
  ];
  report.risk = {
    version: "saved-demo",
    score: 0,
    level: "low",
    signals: [],
    interpretation:
      "No historical risk rule fired in the evidence bundled with this recorded example.",
  };
  report.interpretation = {
    status: "complete",
    model: null,
    author: "baseline",
    reason: null,
    result: {
      summary: [
        {
          id: "saved-summary",
          text: "This report replays recorded transaction evidence locally while the live analysis service is unavailable.",
          evidence_ids: [],
        },
      ],
      important_findings: [],
      uncertainties: [
        {
          id: "saved-live-gap",
          text: "Current on-chain exposure was not refreshed in this offline replay.",
          evidence_ids: [],
        },
      ],
      recommended_checks: ["compare_explorer"],
      actions: [],
    },
    investigation: null,
    trace: savedTrace,
    llm_calls: 0,
    duration_ms: savedTrace.reduce((total, step) => total + step.duration_ms, 0),
  };
  return report;
}

const reports: Record<SavedExampleId, Report> = {
  approval,
  ethereum: recordedReport(
    "ethereum",
    "ethereum",
    "https://etherscan.io/tx/0xa5e6aec48fffd1c35d8410e2e81b63e1fca740bde922f5f2d4b7da50f65f532f",
    {
      hash: "0xa5e6aec48fffd1c35d8410e2e81b63e1fca740bde922f5f2d4b7da50f65f532f",
      sender: "0x2252f216f4a494a87025123425181ca1bb754fb8",
      recipient: "0x0000000aa232009084bd71a5797d089aa4edfad4",
      created_contract: null,
      block_number: 25995380,
      timestamp: 1789626071,
      status: "success",
      function: null,
      selector: "0x09c5eabe",
    },
  ),
  monad: recordedReport(
    "monad",
    "monad",
    "https://monadscan.com/tx/0x3284afdd9fe66c9d0832cf640c1dd0da02ea9e990ffc091503d13d533fad7c2c",
    {
      hash: "0x3284afdd9fe66c9d0832cf640c1dd0da02ea9e990ffc091503d13d533fad7c2c",
      sender: "0x6f49a8f621353f12378d0046e7d7e4b9b249dc9e",
      recipient: "0x0000000000000000000000000000000000001000",
      created_contract: null,
      block_number: 105536115,
      timestamp: 1789627186,
      status: "success",
      function: null,
      selector: "0x791bdcf3",
    },
  ),
};

export const savedExampleNames: Record<SavedExampleId, string> = {
  approval: "Approval activity",
  ethereum: "Ethereum recorded transaction",
  monad: "Monad recorded transaction",
};

export function isSavedExampleId(value: string): value is SavedExampleId {
  return value === "approval" || value === "ethereum" || value === "monad";
}

export function getSavedReport(id: string): Report | null {
  return isSavedExampleId(id) ? reports[id] : null;
}

