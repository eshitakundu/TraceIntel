import { useEffect, useState } from "react";
import { useActiveSection } from "../hooks/useActiveSection";
import type { useHealth } from "../hooks/useHealth";
import BackendStatus from "../components/BackendStatus";
import { Link, useParams, useOutletContext } from "react-router-dom";
import { getReport } from "../api/analysis";
import type { Report } from "../types/report";
import { getSavedReport } from "../data/savedReports";
import EvidenceLinks from "../components/EvidenceLinks";
import ExposurePanel, { ExposureMetrics } from "../components/ExposurePanel";
import AgentBriefing from "../components/AgentBriefing";
import AgentTrace from "../components/AgentTrace";
import {
  Approvals,
  AssetMovements,
  Contracts,
  RawEvidence,
  RiskEvidence,
} from "../components/ReportSections";

const sections = [
  "exposure",
  "interpretation",
  "overview",
  "movements",
  "approvals",
  "contracts",
  "risk",
  "coverage",
  "evidence",
] as const;
const sectionNames: Record<string, string> = {
  exposure: "Then → Now",
  interpretation: "Agent trace",
  risk: "Historical risk",
  coverage: "Evidence coverage",
  evidence: "Technical evidence",
};
export default function ReportPage() {
  const { id = "" } = useParams();
  const savedId = id.startsWith("saved-") ? id.slice(6) : "";
  const savedReport = getSavedReport(savedId);
  const { state } = useOutletContext<ReturnType<typeof useHealth>>();
  const [report, setReport] = useState<Report | null>(savedReport);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");
  const active = useActiveSection(sections, report !== null);
  useEffect(() => {
    if (savedReport) {
      setReport(savedReport);
      setError("");
      return;
    }
    if (state !== "connected") return;
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
  }, [id, savedReport, state]);
  if (!savedReport && state !== "connected")
    return (
      <section className="document trace-light-page live-analysis">
        <BackendStatus />
      </section>
    );
  if (error)
    return (
      <section className="document trace-light-page live-analysis">
        <h1>Report unavailable</h1>
        <p role="alert">{error}</p>
        <Link to="/">Return to workspace</Link>
      </section>
    );
  if (!report)
    return (
      <section className="document trace-light-page route-loading">
        <p role="status">Loading stored report…</p>
      </section>
    );
  const tx = report.decoded.transaction;
  const coverage = [
    ...report.coverage,
    ...(report.interpretation.investigation?.coverage ?? []),
  ];
  const gaps = coverage.filter(
    (item) => item.status === "partial" || item.status === "unavailable",
  );
  async function copyLink() {
    try {
      await navigator.clipboard.writeText(location.href);
      setCopied("Link copied");
    } catch {
      setCopied("Copy this page URL from your address bar.");
    }
  }
  function downloadSavedReport() {
    if (!savedReport) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(savedReport, null, 2)], {
        type: "application/json",
      }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = savedReport.id + ".json";
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div
      className={
        "report-page trace-light-page" +
        (savedReport ? " recorded-report-page" : "")
      }
    >
      <div className="report-topline">
        <Link to="/">← New analysis</Link>
        <span className="label">
          {savedReport ? "RECORDED REPORT · OFFLINE SAFE" : "SAVED REPORT"}
        </span>
      </div>
      <section className="report-header">
        <div>
          <div className="eyebrow">
            {report.chain.toUpperCase()} / TRANSACTION REPORT
          </div>
          <h1>Transaction intelligence.</h1>
          <p className="report-subtitle">
            What changed then. What remains now.
          </p>
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
      </section>
      <AgentBriefing report={report} />
      <ExposureMetrics report={report} />
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
        {savedReport ? (
          <button className="secondary" onClick={downloadSavedReport}>
            Download saved JSON
          </button>
        ) : (
          <a
            className="button"
            href={"/api/v1/reports/" + report.id + "/download"}
          >
            Download JSON ↓
          </a>
        )}
        <span role="status">{copied}</span>
      </div>
      <div className="report-layout">
        <nav className="report-nav" aria-label="Report sections">
          {sections.map((section) => (
            <a
              href={"#" + section}
              key={section}
              className={active === section ? "active" : undefined}
              aria-current={active === section ? "true" : undefined}
            >
              {sectionNames[section] ?? section}
            </a>
          ))}
        </nav>
        <div className="report-content">
          <ExposurePanel report={report} />
          <AgentTrace report={report} />
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
            {tx.arguments_json && (
              <details>
                <summary>Decoded calldata arguments</summary>
                <pre className="argument-json">
                  {JSON.stringify(JSON.parse(tx.arguments_json), null, 2)}
                </pre>
              </details>
            )}
            <EvidenceLinks ids={tx.evidence_ids} />
          </section>
          <AssetMovements report={report} />
          <Approvals report={report} />
          <Contracts report={report} />
          <RiskEvidence report={report} />
          <section className="report-section" id="coverage">
            <h2>Completeness & limitations</h2>
            <div className="coverage-banner">
              <strong>
                {gaps.length
                  ? "Evidence coverage is incomplete"
                  : "Configured checks completed"}
              </strong>
              <span>
                {gaps.length} partial or unavailable checks. Missing information
                never establishes safety.
              </span>
              <a href="#coverage">Review coverage ↓</a>
            </div>

            {coverage.map((item, index) => (
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
            Created {new Date(report.created_at).toLocaleString()} · Schema{" "}
            {report.schema_version} · Stored report
          </p>
        </div>
      </div>
    </div>
  );
}
