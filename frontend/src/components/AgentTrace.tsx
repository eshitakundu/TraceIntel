import { traceSummary } from "../api/trace";
import type { Report } from "../types/report";

const actorLabel = {
  planner: "Plan",
  tool: "Tool",
  reporter: "Brief",
  validator: "Check",
} as const;

const checkCopy: Record<string, string> = {
  verify_spender: "Verify the spender address and intended permissions.",
  review_allowance:
    "Check the current allowance and whether it is still needed.",
  review_implementation:
    "Review the proxy implementation and upgrade authority.",
  compare_explorer: "Compare the report with an independent block explorer.",
  check_missing_data: "Resolve coverage gaps before drawing conclusions.",
};

/** The audit trail: every plan, tool call, validation and briefing step. */
export default function AgentTrace({ report }: { report: Report }) {
  const interpretation = report.interpretation;
  const trace = interpretation.trace ?? [];
  const investigation = interpretation.investigation;
  const checks = interpretation.result?.recommended_checks ?? [];
  return (
    <section className="report-section" id="interpretation">
      <div className="section-heading">
        <h2>How the agent worked</h2>
        <span className="badge">
          {interpretation.author === "model"
            ? "AI agent"
            : interpretation.author === "baseline"
              ? "Rule-based"
              : interpretation.status}
        </span>
      </div>
      <p className="note">
        A planner chooses read-only checks within a fixed budget; tools observe
        the chain; a validator accepts only claims written by code from
        evidence. The model never writes facts, scores or exposure states.
      </p>
      {trace.length ? (
        <>
          <p className="trace-totals">
            {investigation
              ? (investigation.planner === "model"
                  ? "AI-planned investigation"
                  : "Baseline-planned investigation") + " · "
              : ""}
            {traceSummary(
              trace,
              interpretation.llm_calls,
              interpretation.duration_ms,
            )}
          </p>
          <ol className="trace">
            {trace.map((step, index) => (
              <li key={index} className={"trace-step " + step.status}>
                <span className={"trace-actor " + step.actor}>
                  {actorLabel[step.actor]}
                </span>
                <span className="trace-detail">{step.detail}</span>
                <span className="trace-meta">
                  {step.status !== "ok" && (
                    <span className="trace-status">{step.status}</span>
                  )}
                  {step.duration_ms > 0 && step.duration_ms + " ms"}
                </span>
              </li>
            ))}
          </ol>
        </>
      ) : (
        <p>
          {interpretation.reason ??
            "This report was created before agent traces were recorded."}
        </p>
      )}
      {checks.length > 0 && (
        <>
          <h3>Independent checks worth doing</h3>
          <ul>
            {checks.map((check) => (
              <li key={check}>{checkCopy[check] ?? check}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
