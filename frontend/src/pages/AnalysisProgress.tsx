import { useEffect, useState } from "react";
import type { useHealth } from "../hooks/useHealth";
import BackendStatus from "../components/BackendStatus";
import {
  Link,
  useNavigate,
  useParams,
  useOutletContext,
} from "react-router-dom";
import { getJob } from "../api/analysis";
import type { Job } from "../types/report";

const stages = [
  "Queued",
  "Fetching transaction",
  "Decoding calldata and event logs",
  "Inspecting contracts",
  "Evaluating deterministic signals",
  "Checking current approval exposure",
  "Running NOOA intelligence analysis",
  "Generating report",
  "Complete",
];
export default function AnalysisProgress() {
  const { id = "" } = useParams();
  const { state } = useOutletContext<ReturnType<typeof useHealth>>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (state !== "connected") return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await getJob(id, controller.signal);
        if (controller.signal.aborted) return;
        setJob(next);
        if (next.status === "complete" && next.report_id) {
          navigate("/reports/" + next.report_id, { replace: true });
          return;
        }
        if (next.status !== "failed")
          timer = setTimeout(() => void poll(), 750);
      } catch (error) {
        if (!controller.signal.aborted)
          setError(
            error instanceof Error
              ? error.message
              : "Could not retrieve progress.",
          );
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [id, navigate, state]);
  if (state !== "connected") return <BackendStatus />;
  const current = stages.indexOf(job?.stage ?? "Queued");
  return (
    <section className="document">
      <div className="eyebrow">LIVE ANALYSIS</div>
      <h1>Following the evidence.</h1>
      <p className="hash">{job?.transaction_hash}</p>
      {error || job?.error ? (
        <div role="alert" className="panel">
          <h2>Analysis could not complete</h2>
          <p>{error || job?.error}</p>
          <Link to="/">Return to workspace →</Link>
        </div>
      ) : (
        <ol className="stage-list" aria-live="polite">
          {stages.slice(0, -1).map((stage, index) => (
            <li
              key={stage}
              className={
                index < current ? "done" : index === current ? "current" : ""
              }
            >
              <span>
                {index < current ? "✓" : String(index + 1).padStart(2, "0")}
              </span>
              {stage}
            </li>
          ))}
        </ol>
      )}
      <p>
        Stages reflect actual backend work. Unavailable data will appear as a
        report limitation.
      </p>
    </section>
  );
}
