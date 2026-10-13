import { useState, type CSSProperties } from "react";
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
const meter = (ratio: number) =>
  ({
    "--fill": Math.round(Math.min(Math.max(ratio, 0), 1) * 100) + "%",
  }) as CSSProperties;
const UINT96_MAX = (1n << 96n) - 1n;
/** Wallets signal "infinite" with uint256 max, uint96 max (UNI/COMP) or near-max values. */
function isUnlimited(raw: string) {
  const value = BigInt(raw);
  return value === UINT96_MAX || value >= 1n << 255n;
}
function amount(value: string | null, decimals: number | null) {
  if (value === null) return "Unavailable";
  if (isUnlimited(value)) return "Unlimited";
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
/** Permissions the sender controls: their own, or the called contract's (possibly their
 * smart wallet). Reports created before ownership was classified treat all as theirs. */
function ownedBySender(permission: PersistentExposure) {
  return permission.historical.owner_role !== "other";
}
function granter(permission: PersistentExposure) {
  const owner = permission.historical.owner;
  switch (permission.historical.owner_role) {
    case "sender":
      return "Granted by the sender";
    case "called_contract":
      return (
        "Granted by the called contract " +
        short(owner) +
        " (possibly your smart wallet)"
      );
    case "other":
      return "Granted by contract " + short(owner) + " during the transaction";
    default:
      return "Owner " + short(owner);
  }
}

export function ExposureMetrics({ report }: { report: Report }) {
  const all = distinctPermissions(report);
  const permissions = all.filter(ownedBySender);
  const others = all.length - permissions.length;
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
          <span className={"badge " + report.risk.level}>
            {report.risk.level}
          </span>
        </div>
        <span className="meter" aria-hidden="true">
          <i style={meter(report.risk.score / 100)} />
        </span>
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
        <span className="meter" aria-hidden="true">
          <i
            style={meter(permissions.length ? active / permissions.length : 0)}
          />
        </span>
        <p>
          {unknown ? unknown + " unknown · " : ""}
          {permissions.length
            ? permissions.length + " distinct permissions checked"
            : "No ERC-20 permission comparison available"}
        </p>
        {others > 0 && (
          <p className="metric-aside">
            + {others} held by other contracts in this transaction
          </p>
        )}
      </article>
      <article className="metric-card">
        <span className="label">EVIDENCE COVERAGE</span>
        <div className="metric-value">
          {checked}
          <small>/{report.coverage.length} checks available</small>
        </div>
        <span className="meter" aria-hidden="true">
          <i
            style={meter(
              report.coverage.length ? checked / report.coverage.length : 0,
            )}
          />
        </span>
        <p>Gaps are listed in the report.</p>
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
  const all = distinctPermissions(report);
  const permissions = all.filter(ownedBySender);
  const others = all.filter((p) => !ownedBySender(p));
  const revokeUrl =
    report.chain === "ethereum"
      ? `https://revoke.cash/address/${report.decoded.transaction.sender}?chainId=1`
      : null;
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
        <h2>Then → Now</h2>
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
      {!all.length ? (
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
          {!permissions.length && (
            <p className="note">
              The sender granted no ERC-20 permissions in this transaction.
            </p>
          )}
          {(expanded ? permissions : permissions.slice(0, 3)).map((p) => (
            <PermissionCard key={p.id} permission={p} revokeUrl={revokeUrl} />
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
          {others.length > 0 && (
            <details className="other-owners">
              <summary>
                {others.length} more{" "}
                {others.length === 1 ? "permission was" : "permissions were"}{" "}
                granted by other contracts during this transaction
              </summary>
              <p className="note">
                These belong to the contracts that granted them, not to the
                sender, so they are shown for completeness and not scored.
              </p>
              {others.map((p) => (
                <PermissionCard key={p.id} permission={p} revokeUrl={null} />
              ))}
            </details>
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
              {exposure?.permissions.length} historical events · {all.length}{" "}
              distinct token / owner / spender permissions. The last event for
              each permission is shown here; all events remain in Approvals and
              downloaded JSON.
            </p>
          </details>
        </>
      )}
    </section>
  );
}
function PermissionCard({
  permission: p,
  revokeUrl,
}: {
  permission: PersistentExposure;
  revokeUrl: string | null;
}) {
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
            <span className="granter">{granter(p)}</span>
          </div>
        </div>
        <span className={"exposure-badge state-" + p.status}>
          {p.status === "PARTIALLY_ACTIVE" &&
          h.unlimited &&
          c.allowance_raw !== null &&
          isUnlimited(c.allowance_raw)
            ? "Active · effectively unlimited"
            : labels[p.status]}
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
              ? "Unlimited allowance sentinel"
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
          <span />
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
      {revokeUrl && p.permission_active && (
        <a
          className="button secondary revoke-link"
          href={revokeUrl}
          target="_blank"
          rel="noreferrer"
        >
          Review on revoke.cash ↗
        </a>
      )}
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
