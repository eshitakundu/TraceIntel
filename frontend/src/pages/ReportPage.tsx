import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getReport } from "../api/analysis";
import type { Report } from "../types/report";
import EvidenceLinks from "../components/EvidenceLinks";
import {
  Approvals,
  AssetMovements,
  Contracts,
  RawEvidence,
  RiskEvidence,
} from "../components/ReportSections";

const checks: Record<string, string> = {
  verify_spender: "Verify the spender address and intended permissions.",
  review_allowance:
    "Check the current allowance and whether it is still needed.",
  review_implementation:
    "Review the proxy implementation and upgrade authority.",
  compare_explorer: "Compare the report with an independent block explorer.",
  check_missing_data: "Resolve coverage gaps before drawing conclusions.",
};
export default function ReportPage() {
  const { id = "" } = useParams();
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    getReport(id, controller.signal)
      .then((value) => {
        if (!controller.signal.aborted) setReport(value);
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setError(
            error instanceof Error ? error.message : "Report unavailable.",
          );
      });
    return () => controller.abort();
  }, [id]);
  if (error)
    return (
      <section className="document">
        <h1>Report unavailable</h1>
        <p role="alert">{error}</p>
        <Link to="/">Return to workspace</Link>
      </section>
    );
  if (!report) return <p role="status">Loading stored report…</p>;
  const tx = report.decoded.transaction;
  const gaps = report.coverage.filter(
    (item) => item.status === "partial" || item.status === "unavailable",
  );
  const interpretation = report.interpretation.result;
  async function copyLink() {
    try {
      await navigator.clipboard.writeText(location.href);
      setCopied("Link copied");
    } catch {
      setCopied("Copy this page URL from your address bar.");
    }
  }
  return (
    <>
      <div className="report-topline">
        <Link to="/">← Workspace</Link>
        <span className="label">STORED INTELLIGENCE REPORT</span>
      </div>
      <section className="report-header">
        <div>
          <div className="eyebrow">
            {report.chain.toUpperCase()} / TRANSACTION REPORT
          </div>
          <h1>Transaction intelligence.</h1>
          <code className="hash">{report.transaction_hash}</code>
          <div className="report-meta">
            <span
              className={
                "badge " + (tx.status === "success" ? "success" : "high")
              }
            >
              {tx.status}
            </span>
            <span>Block {tx.block_number.toLocaleString()}</span>
            <span>{new Date(tx.timestamp * 1000).toLocaleString()}</span>
          </div>
        </div>
        <aside className={"risk-meter " + report.risk.level}>
          <span className="label">OBSERVED INDICATOR SCORE</span>
          <strong>
            {report.risk.score}
            <small>/ 100</small>
          </strong>
          <span>{report.risk.level.toUpperCase()}</span>
          <small>Not a safety rating</small>
        </aside>
      </section>
      <div className="report-actions">
        <a
          className="button secondary"
          href={report.explorer_url}
          target="_blank"
          rel="noreferrer"
        >
          Open in explorer ↗
        </a>
        <button className="secondary" onClick={() => void copyLink()}>
          Copy report link
        </button>
        <a
          className="button"
          href={"/api/v1/reports/" + report.id + "/download"}
        >
          Download JSON ↓
        </a>
        <span role="status">{copied}</span>
      </div>
      <div className="coverage-banner">
        <strong>
          {gaps.length
            ? "Evidence coverage is incomplete"
            : "Configured checks completed"}
        </strong>
        <span>
          {gaps.length} partial or unavailable checks. Missing information never
          establishes safety.
        </span>
        <a href="#coverage">Review coverage ↓</a>
      </div>
      <div className="report-layout">
        <nav className="report-nav" aria-label="Report sections">
          {[
            "overview",
            "movements",
            "approvals",
            "contracts",
            "risk",
            "interpretation",
            "coverage",
            "evidence",
          ].map((section) => (
            <a href={"#" + section} key={section}>
              {section}
            </a>
          ))}
        </nav>
        <div className="report-content">
          <section className="report-section" id="overview">
            <div className="section-heading">
              <h2>What happened</h2>
              <span className="label">DETERMINISTIC FACTS</span>
            </div>
            <p>
              The transaction{" "}
              {tx.status === "success" ? "executed successfully" : "failed"}.{" "}
              {tx.recipient
                ? "It called or transferred value to the recipient shown below."
                : "It attempted contract creation."}
            </p>
            <dl>
              <dt>Sender</dt>
              <dd className="hash">{tx.sender}</dd>
              <dt>Recipient</dt>
              <dd className="hash">
                {tx.recipient ??
                  tx.created_contract ??
                  "Contract creation failed"}
              </dd>
              <dt>Function candidate</dt>
              <dd>
                {tx.function ??
                  (tx.selector
                    ? "Unresolved selector " + tx.selector
                    : "No function selector")}
              </dd>
              <dt>Value requested</dt>
              <dd className="hash">{tx.value_wei} wei</dd>
              <dt>Execution gas</dt>
              <dd>
                {tx.gas_used.toLocaleString()} units · {tx.gas_fee_wei} wei
              </dd>
              <dt>Nonce</dt>
              <dd>{tx.nonce}</dd>
            </dl>
            <EvidenceLinks ids={tx.evidence_ids} />
          </section>
          <AssetMovements report={report} />
          <Approvals report={report} />
          <Contracts report={report} />
          <RiskEvidence report={report} />
          <section className="report-section" id="interpretation">
            <div className="section-heading">
              <h2>NOOA interpretation</h2>
              <span className="badge">{report.interpretation.status}</span>
            </div>
            {interpretation ? (
              <>
                <p className="note">
                  Model: {report.interpretation.model}. Selection confidence:{" "}
                  {Math.round(interpretation.confidence * 100)}%.
                </p>
                {interpretation.summary.map((claim) => (
                  <p key={claim.id}>
                    {claim.text} <EvidenceLinks ids={claim.evidence_ids} />
                  </p>
                ))}
                <h3>Important findings</h3>
                {interpretation.important_findings.map((claim) => (
                  <p key={claim.id}>
                    {claim.text} <EvidenceLinks ids={claim.evidence_ids} />
                  </p>
                ))}
                <h3>Recommended checks</h3>
                <ul>
                  {interpretation.recommended_checks.map((check) => (
                    <li key={check}>{checks[check] ?? check}</li>
                  ))}
                </ul>
                <h3>Uncertainty</h3>
                {interpretation.uncertainties.map((claim) => (
                  <p key={claim.id}>{claim.text}</p>
                ))}
              </>
            ) : (
              <p>
                {report.interpretation.reason} All deterministic facts and
                signals remain available.
              </p>
            )}
          </section>
          <section className="report-section" id="coverage">
            <h2>Completeness & limitations</h2>
            {report.coverage.map((item, index) => (
              <div className="coverage-row" key={index}>
                <span className={"badge " + item.status}>
                  {item.status.replace("_", " ")}
                </span>
                <div>
                  <code className="hash">{item.area}</code>
                  <p>{item.reason}</p>
                </div>
              </div>
            ))}
          </section>
          <RawEvidence report={report} />
          <p className="note">
            Created {new Date(report.created_at).toLocaleString()} · Schema
            1.0.0 · Stored report
          </p>
        </div>
      </div>
    </>
  );
}
