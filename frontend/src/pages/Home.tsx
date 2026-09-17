import { useHealth } from "../hooks/useHealth";
import TransactionForm from "../components/TransactionForm";

export default function Home() {
  const { state, retry } = useHealth();
  return (
    <>
      <div className="eyebrow">
        <span className="dot" /> EVM TRANSACTION INTELLIGENCE
      </div>
      <section className="hero">
        <div>
          <h1>
            Follow the transaction.
            <br />
            <span>Understand the evidence.</span>
          </h1>
          <p>
            On-chain facts, deterministic risk signals, and traceable
            interpretation. Understand what moved, who received permission, and
            what remains unknown.
          </p>
        </div>
        <aside className="status-card">
          <span className="label">SYSTEM STATUS</span>
          <strong className={state}>
            {state === "online"
              ? "API connected"
              : state === "checking"
                ? "Checking connection…"
                : "API unavailable"}
          </strong>
          <small>Live health check · FastAPI</small>
          {state === "offline" && (
            <button onClick={retry}>Retry connection</button>
          )}
        </aside>
      </section>
      <TransactionForm />
      <section className="pipeline-section">
        <div className="section-heading">
          <h2>From transaction to understanding</h2>
          <span className="label">THE PIPELINE</span>
        </div>
        <div className="pipeline">
          {["Acquire", "Decode", "Evidence", "Rules", "NOOA", "Report"].map(
            (label, index) => (
              <div key={label}>
                <small>0{index + 1}</small>
                <strong>{label}</strong>
              </div>
            ),
          )}
        </div>
      </section>
      <div className="principles">
        <article>
          <h3>Facts stay facts</h3>
          <p>
            Blockchain evidence and numerical risk scores come from
            deterministic Python code.
          </p>
        </article>
        <article>
          <h3>Every claim has a source</h3>
          <p>
            Restricted NOOA interpretations retain evidence IDs. Unsupported
            claims are rejected.
          </p>
        </article>
        <article>
          <h3>Unknown stays visible</h3>
          <p>
            Missing provider data is a coverage limitation, never evidence of
            safety.
          </p>
        </article>
      </div>
    </>
  );
}
