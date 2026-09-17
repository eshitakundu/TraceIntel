import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { submitAnalysis } from "../api/analysis";
import { formatCompactUnits } from "../api/format";
import type { PersistentExposure, Report } from "../types/report";
import EvidenceLinks from "./EvidenceLinks";

const labels: Record<string, string> = {
  ACTIVE: "Active",
  PARTIALLY_ACTIVE: "Reduced · active",
  REVOKED: "Inactive · zero allowance",
  SUPERSEDED: "Superseded",
  UNKNOWN: "Unknown",
};
const short = (value: string) => value.slice(0, 8) + "…" + value.slice(-6);
function amount(value: string | null, decimals: number | null) {
  if (value === null) return "Unavailable";
  if (value === ((1n << 256n) - 1n).toString()) return "Unlimited";
  return formatCompactUnits(value, decimals);
}
function distinctPermissions(report: Report) {
  const values = new Map<string, PersistentExposure>();
  for (const permission of report.exposure?.permissions ?? []) {
    const h = permission.historical;
    values.set(h.token + h.owner + h.spender, permission);
  }
  return [...values.values()];
}

export function ExposureMetrics({ report }: { report: Report }) {
  const permissions = distinctPermissions(report);
  const active = permissions.filter((p) => p.permission_active === true).length;
  const unknown = permissions.filter(
    (p) => p.permission_active === null,
  ).length;
  const checked = report.coverage.filter(
    (c) => c.status === "available",
  ).length;
  return (
    <div className="intelligence-metrics">
      <article className={"metric-card historical " + report.risk.level}>
        <span className="label">THEN / HISTORICAL TRANSACTION RISK</span>
        <div className="metric-value">
          {report.risk.score}
          <small>/100</small>
          <span className="badge">{report.risk.level}</span>
        </div>
        <p>Indicators in the original transaction. Not a safety rating.</p>
      </article>
      <article className="metric-card current">
        <span className="label">NOW / CURRENT APPROVAL EXPOSURE</span>
        <div className="metric-value">
          {report.exposure ? active : "—"}
          <small>
            {report.exposure ? "active permissions" : "Not checked"}
          </small>
        </div>
        <p>
          {unknown ? unknown + " unknown · " : ""}
          {permissions.length
            ? permissions.length + " distinct permissions checked"
            : "No ERC-20 permission comparison available"}
        </p>
      </article>
      <article className="metric-card">
        <span className="label">EVIDENCE COVERAGE</span>
        <div className="metric-value">
          {checked}
          <small>/{report.coverage.length} checks available</small>
        </div>
        <p>Partial and missing evidence remain visible below.</p>
      </article>
    </div>
  );
}

export default function ExposurePanel({ report }: { report: Report }) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const navigate = useNavigate();
  const exposure = report.exposure;
  const permissions = distinctPermissions(report);
  async function refresh() {
    setBusy(true);
    setMessage("");
    try {
      const job = await submitAnalysis(report.chain, report.transaction_hash);
      if (job.report_id === report.id) {
        setMessage(
          "This is the latest cached snapshot. A new check is available within five minutes.",
        );
      } else navigate("/analysis/" + job.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not refresh.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="report-section exposure-section" id="exposure">
      <div className="section-heading">
        <div>
          <span className="eyebrow">FOLLOW THE PERMISSION</span>
          <h2>Then → Now</h2>
        </div>
        <button
          className="secondary"
          disabled={busy}
          onClick={() => void refresh()}
        >
          {busy ? "Checking…" : "Refresh current state ↻"}
        </button>
      </div>
      <p className="snapshot-note">
        {exposure
          ? "Snapshot checked " + new Date(exposure.checked_at).toLocaleString()
          : "This older report has no current-state snapshot."}{" "}
        · Saved evidence, not continuous monitoring.
      </p>
      {message && <p role="status">{message}</p>}
      {!permissions.length ? (
        <div className="exposure-empty">
          <span>◈</span>
          <h3>
            {exposure
              ? "No ERC-20 approvals to compare"
              : "Current exposure has not been checked"}
          </h3>
          <p>
            {exposure
              ? "This transaction may have other effects. No ERC-20 approval does not establish overall safety."
              : "Request a fresh analysis to add a current-state comparison."}
          </p>
        </div>
      ) : (
        <>
          {(expanded ? permissions : permissions.slice(0, 3)).map((p) => (
            <PermissionCard key={p.id} permission={p} />
          ))}
          {permissions.length > 3 && (
            <button
              className="secondary"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded
                ? "Show fewer permissions"
                : "Show all " + permissions.length + " permissions"}
            </button>
          )}
          <details className="exposure-method">
            <summary>How to read this comparison</summary>
            <ul>
              {exposure?.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
            <p>
              “Superseded” means a later event or a higher current amount
              replaced the historical amount. It does not mean permission is
              inactive. “Inactive” means zero allowance; the cause is not
              inferred.
            </p>
            <p>
              {exposure?.permissions.length} historical events ·{" "}
              {permissions.length} distinct token / owner / spender permissions.
              The last event for each permission is shown here; all events
              remain in Approvals and downloaded JSON.
            </p>
          </details>
        </>
      )}
    </section>
  );
}
function PermissionCard({ permission: p }: { permission: PersistentExposure }) {
  const h = p.historical,
    c = p.current;
  return (
    <article className="permission-card">
      <div className="permission-heading">
        <div className="token-identity">
          <span className="token-avatar">{c.symbol?.slice(0, 1) ?? "◈"}</span>
          <div>
            <h3>
              {c.symbol ?? short(h.token)}
              <small>{c.name ?? "Token label unavailable"}</small>
            </h3>
            <code title={h.token}>{short(h.token)}</code>
          </div>
        </div>
        <span className={"exposure-badge state-" + p.status}>
          {labels[p.status]}
        </span>
      </div>
      <div className="comparison-grid">
        <div className="comparison-side then">
          <span className="label">THEN / REPORTED APPROVAL</span>
          <strong className="permission-amount">
            {amount(h.allowance_raw, c.decimals)}
          </strong>
          <small>
            {h.unlimited
              ? "Maximum uint256 allowance"
              : c.decimals === null
                ? "Raw token units"
                : "Token units using current reported decimals"}
          </small>
          <p>
            Block {h.block_number.toLocaleString()}
            <br />
            {new Date(h.timestamp * 1000).toLocaleString()}
          </p>
          <EvidenceLinks ids={h.evidence_ids} />
        </div>
        <div className="comparison-arrow" aria-hidden="true">
          →
        </div>
        <div className="comparison-side now">
          <span className="label">NOW / CURRENT ALLOWANCE</span>
          <strong className="permission-amount">
            {amount(c.allowance_raw, c.decimals)}
          </strong>
          <small>
            {c.allowance_raw === null
              ? "Current allowance is unknown"
              : p.permission_active
                ? "Spending permission remains active"
                : "No active allowance at this block"}
          </small>
          <p>
            {c.block_number
              ? "Block " + c.block_number.toLocaleString()
              : "Block unavailable"}
            <br />
            {c.block_timestamp
              ? new Date(c.block_timestamp * 1000).toLocaleString()
              : "Current state could not be verified"}
          </p>
          <EvidenceLinks ids={c.evidence_ids} />
        </div>
      </div>
      <p className="exposure-takeaway">{p.summary}</p>
      <div className="permission-context">
        <div>
          <span>Owner balance now</span>
          <strong>
            {amount(c.balance_raw, c.decimals)}
            {c.symbol && c.balance_raw !== null ? " " + c.symbol : ""}
          </strong>
        </div>
        <div>
          <span>Spender bytecode now</span>
          <strong>
            {c.spender_has_code === null
              ? "Unknown"
              : c.spender_has_code
                ? "Contract code present"
                : "No bytecode"}
          </strong>
        </div>
      </div>
      <details>
        <summary>Owner, spender & query details</summary>
        <dl>
          <dt>Owner</dt>
          <dd className="hash">{h.owner}</dd>
          <dt>Spender</dt>
          <dd className="hash">{h.spender}</dd>
          <dt>Token</dt>
          <dd className="hash">{h.token}</dd>
          <dt>Original raw allowance</dt>
          <dd className="hash">{h.allowance_raw}</dd>
          <dt>Current raw allowance</dt>
          <dd className="hash">{c.allowance_raw ?? "Unknown"}</dd>
        </dl>
        {c.errors.map((error) => (
          <p className="error" key={error}>
            {error}
          </p>
        ))}
      </details>
    </article>
  );
}
