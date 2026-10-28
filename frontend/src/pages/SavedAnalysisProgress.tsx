import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  getSavedReport,
  isSavedExampleId,
  savedExampleNames,
} from "../data/savedReports";

const stages = [
  "Load recorded transaction",
  "Decode calldata and event logs",
  "Inspect recorded contracts",
  "Evaluate deterministic signals",
  "Validate evidence coverage",
  "Build saved report",
];

export default function SavedAnalysisProgress() {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const [current, setCurrent] = useState(0);
  const report = getSavedReport(id);
  useEffect(() => {
    if (!report) return;
    if (current >= stages.length) {
      const timer = setTimeout(
        () => navigate("/reports/saved-" + id, { replace: true }),
        450,
      );
      return () => clearTimeout(timer);
    }
    const timer = setTimeout(() => setCurrent((value) => value + 1), 430);
    return () => clearTimeout(timer);
  }, [current, id, navigate, report]);
  if (!report || !isSavedExampleId(id))
    return (
      <section className="document trace-light-page">
        <h1>Saved example not found</h1>
        <Link to="/">Return to workspace</Link>
      </section>
    );
  return (
    <section className="document saved-replay trace-light-page">
      <div className="eyebrow">Recorded analysis, available offline</div>
      <h1>Replaying the evidence.</h1>
      <p>{savedExampleNames[id]}</p>
      <code className="hash">{report.transaction_hash}</code>
      <ol className="stage-list" aria-live="polite">
        {stages.map((stage, index) => (
          <li
            key={stage}
            className={
              index < current ? "done" : index === current ? "current" : ""
            }
          >
            <span className="keycap pixel">
              {index < current ? "ok" : String(index + 1).padStart(2, "0")}
            </span>
            {stage}
          </li>
        ))}
      </ol>
      <p className="note">
        This is a saved TraceIntel run. No live backend or wallet connection is
        being used.
      </p>
      <Link className="button secondary" to={"/reports/saved-" + id}>
        Open report now
      </Link>
    </section>
  );
}

