import { traceSummary } from "../api/trace";
import type { ActionKind, CitedClaim, Report } from "../types/report";
import EvidenceLinks from "./EvidenceLinks";

const actionCopy: Record<ActionKind, { title: string; hint: string }> = {
  consider_revoking: {
    title: "Consider revoking",
    hint: "It can still move these tokens. Revoke it if you no longer use this app.",
  },
  verify_spender: {
    title: "Verify the spender",
    hint: "Make sure this is the app you meant to approve before leaving it in place.",
  },
  review_upgrade_control: {
    title: "Check who can upgrade it",
    hint: "Its code can be replaced. Know who controls that before trusting it.",
  },
};

/** revoke.cash supports these chain IDs for one-click revocation. */
const revokeChains: Record<string, number> = { ethereum: 1 };

function Claims({ claims }: { claims: CitedClaim[] }) {
  if (!claims.length) return null;
  return (
    <ul className="claim-list">
      {claims.map((claim) => (
        <li key={claim.id}>
          {claim.text} <EvidenceLinks ids={claim.evidence_ids} />
        </li>
      ))}
    </ul>
  );
}

export default function AgentBriefing({ report }: { report: Report }) {
  const interpretation = report.interpretation;
  const result = interpretation.result;
  const actions = result?.actions ?? [];
  const chainId = revokeChains[report.chain];
  const sender = report.decoded.transaction.sender;
  const byModel = interpretation.author === "model";
  // Reasons already stated in the summary are not repeated on each action card.
  const stated = new Set(result?.summary.map((claim) => claim.id));
  const onCards = new Set(
    actions.flatMap((action) => action.reasons.map((reason) => reason.id)),
  );
  const why = (result?.important_findings ?? []).filter(
    (claim) => !stated.has(claim.id) && !onCards.has(claim.id),
  );
  return (
    <section
      className="briefing"
      id="briefing"
      aria-labelledby="briefing-title"
    >
      <div className="briefing-head">
        <div>
          <span className="eyebrow">AGENT BRIEFING</span>
          <h2 id="briefing-title">What this transaction left behind</h2>
        </div>
        <span className={"author-chip " + (byModel ? "model" : "baseline")}>
          {byModel
            ? "AI agent · " + (interpretation.model ?? "model")
            : interpretation.author === "baseline"
              ? "Rule-based briefing"
              : "Evidence only"}
        </span>
      </div>
      {result ? (
        <>
          <div className="briefing-summary">
            {result.summary.map((claim) => (
              <p key={claim.id}>
                {claim.text} <EvidenceLinks ids={claim.evidence_ids} />
              </p>
            ))}
          </div>
          {actions.length ? (
            <div className="action-grid">
              {actions.map((action) => (
                <article
                  className={"action-card " + action.action}
                  key={action.permission_id + action.action}
                >
                  <span className="action-kind">
                    {actionCopy[action.action].title}
                  </span>
                  <p className="action-hint">
                    {actionCopy[action.action].hint}
                  </p>
                  <Claims
                    claims={action.reasons.filter((r) => !stated.has(r.id))}
                  />
                  {action.action === "consider_revoking" && chainId && (
                    <a
                      className="button secondary"
                      href={`https://revoke.cash/address/${sender}?chainId=${chainId}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Review on revoke.cash ↗
                    </a>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <p className="no-action">
              No live permission held by the sender needs action based on the
              checks that ran. This is not a safety guarantee.
            </p>
          )}
          <div className="briefing-columns">
            {why.length > 0 && (
              <div>
                <h3>Also found</h3>
                <Claims claims={why} />
              </div>
            )}
            {result.uncertainties.length > 0 && (
              <div>
                <h3>What could not be verified</h3>
                <Claims claims={result.uncertainties} />
              </div>
            )}
          </div>
        </>
      ) : (
        <p className="no-action">
          {interpretation.reason ?? "No briefing is available for this report."}{" "}
          All deterministic evidence below remains available.
        </p>
      )}
      <p className="briefing-foot">
        {byModel
          ? "The model chose these sentences and actions; code wrote every sentence from on-chain evidence and validated every citation."
          : (interpretation.reason ? interpretation.reason + " " : "") +
            "Every sentence is written by code from on-chain evidence."}{" "}
        {interpretation.trace?.length ? (
          <a href="#interpretation">
            How the agent reached this (
            {traceSummary(
              interpretation.trace,
              interpretation.llm_calls,
              interpretation.duration_ms,
            )}
            ) ↓
          </a>
        ) : null}
      </p>
    </section>
  );
}
