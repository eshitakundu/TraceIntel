import { useOutletContext } from "react-router-dom";
import type { useHealth } from "../hooks/useHealth";
import TransactionForm from "../components/TransactionForm";
import { tilt } from "../motion";

const steps = [
  {
    key: "then",
    tone: "",
    title: "What permission was created?",
    text: "Decoded from the transaction.",
  },
  {
    key: "now",
    tone: "cobalt",
    title: "Does it still exist?",
    text: "Checked against the chain today.",
  },
  {
    key: "ref",
    tone: "lime",
    title: "Can I verify it?",
    text: "Linked evidence. Unknowns stay visible.",
  },
];

const features = [
  {
    key: "then",
    title: "Historical facts",
    text: "What moved, and who got permission.",
  },
  {
    key: "now",
    title: "Current exposure",
    text: "Which approvals are still active now.",
  },
  {
    key: "vs",
    title: "Then vs now",
    text: "Original amount next to today's allowance.",
  },
  {
    key: "ref",
    title: "Cited answers",
    text: "NOOA explains, linking every claim to evidence.",
  },
];

export default function Home() {
  const { state, retry } = useOutletContext<ReturnType<typeof useHealth>>();
  return (
    <>
      <section className="hero intelligence-hero">
        <div className="hero-copy">
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
          <h1>
            Trace what happened.
            <br />
            <span className="dim">See what remains.</span>
          </h1>
          <p>
            See what a transaction did, and which token approvals it left
            active.
          </p>
          <div className="trust-strip">
            <span>Read-only analysis</span>
            <span>No wallet connection</span>
            <span>Ethereum & Monad</span>
          </div>
        </div>
        <aside
          className="time-lens"
          aria-label="Historical analysis and current exposure"
        >
          {steps.map((step, index) => (
            <div key={step.key}>
              {index > 0 && (
                <span className="lens-connector" aria-hidden="true">
                  <span className="beam" />
                </span>
              )}
              <div className={"lens-step " + step.key}>
                <span
                  className={"time-node keycap pixel " + step.tone}
                  aria-hidden="true"
                >
                  {step.key}
                </span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </div>
              </div>
            </div>
          ))}
        </aside>
      </section>
      <TransactionForm ready={state === "connected"} />
      <section className="product-difference">
        <div>
          <h2>
            A finished transaction
            <br />
            <span className="dim">can leave access open.</span>
          </h2>
          <p>
            Approvals often outlive the swap that created them. TraceIntel
            checks whether they still work.
          </p>
        </div>
        <div className="feature-grid">
          {features.map((feature) => (
            <article className="tilt" key={feature.title} {...tilt(5)}>
              <span className="feature-icon keycap pixel" aria-hidden="true">
                {feature.key}
              </span>
              <h3>{feature.title}</h3>
              <p>{feature.text}</p>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
