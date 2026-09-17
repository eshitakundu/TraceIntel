import { useOutletContext } from "react-router-dom";
import type { useHealth } from "../hooks/useHealth";
import TransactionForm from "../components/TransactionForm";

export default function Home() {
  const { state, retry } = useOutletContext<ReturnType<typeof useHealth>>();
  return (
    <>
      <div className="workspace-bar">
        <span className="eyebrow">
          <span className="dot" /> PERSISTENT ON-CHAIN EXPOSURE INTELLIGENCE
        </span>
        <span role="status" className={"connection-pill " + state}>
          {state === "connected"
            ? "API connected"
            : state === "checking"
              ? "Checking connection…"
              : state === "waking"
                ? "Backend waking up…"
                : "API unavailable"}
          {state === "unavailable" && (
            <button onClick={retry}>Retry connection</button>
          )}
        </span>
      </div>
      <section className="hero intelligence-hero">
        <div className="hero-copy">
          <span className="hero-kicker">
            THE TRANSACTION IS ONLY THE BEGINNING
          </span>
          <h1>
            Trace what happened.
            <br />
            <span>See what remains.</span>
          </h1>
          <p>
            A transaction can finish while its permissions remain active.
            Reconstruct Ethereum and Monad transactions, then check what remains
            exposed today.
          </p>
          <div className="trust-strip">
            <span>◈ Public on-chain evidence</span>
            <span>↗ Read-only analysis</span>
            <span>No wallet connection</span>
          </div>
        </div>
        <aside
          className="time-lens"
          aria-label="Historical analysis and current exposure"
        >
          <div className="lens-heading">
            <span className="label">TWO LENSES. ONE INVESTIGATION.</span>
            <span className="lens-orbit">◈</span>
          </div>
          <div className="lens-step">
            <span className="time-node">01</span>
            <div>
              <span className="label">THEN · TRANSACTION</span>
              <h3>What permission was created?</h3>
              <p>Decode approvals, movements and historical risk.</p>
            </div>
          </div>
          <div className="lens-connector">
            <span /> Follow the permission <span />
          </div>
          <div className="lens-step now">
            <span className="time-node">02</span>
            <div>
              <span className="label">NOW · CURRENT STATE</span>
              <h3>Does it still exist?</h3>
              <p>Read the current allowance and owner balance.</p>
            </div>
          </div>
          <div className="lens-foot">
            Evidence at both ends. Unknowns stay visible.
          </div>
        </aside>
      </section>
      <TransactionForm ready={state === "connected"} />
      <section className="product-difference">
        <div>
          <span className="eyebrow">BEYOND THE TRANSACTION RECEIPT</span>
          <h2>
            A completed transaction.
            <br />
            An ongoing permission?
          </h2>
          <p>
            An approval can outlive the action that created it. TraceIntel
            connects the historical event to a fresh, block-specific allowance
            check.
          </p>
        </div>
        <div className="feature-grid">
          <article>
            <span className="feature-icon">↗</span>
            <h3>Historical facts</h3>
            <p>
              What moved, who gained permission and which indicators triggered.
            </p>
          </article>
          <article>
            <span className="feature-icon">◉</span>
            <h3>Persistent exposure</h3>
            <p>
              Active, reduced, inactive or changed allowances, with explicit
              unknowns.
            </p>
          </article>
          <article>
            <span className="feature-icon">⇄</span>
            <h3>Then vs now</h3>
            <p>
              Original amounts beside current state. Historical risk stays
              separate.
            </p>
          </article>
          <article>
            <span className="feature-icon">⌁</span>
            <h3>Traceable interpretation</h3>
            <p>
              NOOA organizes verified claims with links back to their evidence.
            </p>
          </article>
        </div>
      </section>
    </>
  );
}
