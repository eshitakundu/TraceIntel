import { useOutletContext } from "react-router-dom";
import type { useHealth } from "../hooks/useHealth";
import TransactionForm from "../components/TransactionForm";
import { tilt } from "../motion";

const steps = [
  {
    key: "then",
    tone: "",
    title: "What did you approve?",
    text: "Decoded from the transaction.",
  },
  {
    key: "now",
    tone: "cobalt",
    title: "Does it still exist?",
    text: "Checked against the chain today.",
  },
  {
    key: "ai",
    tone: "lime",
    title: "Should you revoke it?",
    text: "An agent checks the spender and cites every reason.",
  },
];

const why = [
  {
    title: "Approvals don't expire",
    text: "An unlimited approval stays live long after the swap that needed it.",
  },
  {
    title: "Spenders can change",
    text: "An upgradeable spender can get new code after you said yes.",
  },
  {
    title: "Explorers show history",
    text: "They show what happened, not what can still move your tokens.",
  },
];

const how = [
  {
    key: "01",
    title: "Decode",
    text: "Reads the approvals and separates yours from contracts' own.",
  },
  {
    key: "02",
    title: "Check today",
    text: "Reads each allowance, balance and spender at one pinned block.",
  },
  {
    key: "03",
    title: "Investigate",
    text: "An agent profiles spenders: upgrades since approval, who controls them.",
  },
  {
    key: "04",
    title: "Advise",
    text: "Revoke, verify or review, with every reason linked to evidence.",
  },
];

const different = [
  {
    title: "Answers “should I revoke?”",
    text: "Not a list of approvals: a cited recommendation for each live permission.",
  },
  {
    title: "Notices what changed",
    text: "Compares the spender at approval time with today, including upgrades and single-key control.",
  },
  {
    title: "AI that can't invent facts",
    text: "The model picks from facts written by code. A validator rejects anything else, and a rule-based baseline keeps it honest.",
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
            Old token approvals are how wallets get drained. Paste a transaction
            to see what it can still spend today, and whether to revoke it.
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
      <section className="pitch" aria-labelledby="why-title">
        <div className="pitch-head">
          <span className="eyebrow">WHY IT EXISTS</span>
          <h2 id="why-title">
            A finished transaction
            <br />
            <span className="dim">can leave access open.</span>
          </h2>
        </div>
        <div className="pitch-grid">
          {why.map((item) => (
            <article className="pitch-card" key={item.title}>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="pitch" aria-labelledby="how-title">
        <div className="pitch-head">
          <span className="eyebrow">HOW IT WORKS</span>
          <h2 id="how-title">Four steps. One answer.</h2>
        </div>
        <ol className="how-steps">
          {how.map((step) => (
            <li className="tilt" key={step.key} {...tilt(5)}>
              <span className="feature-icon keycap pixel" aria-hidden="true">
                {step.key}
              </span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </li>
          ))}
        </ol>
      </section>
      <section className="pitch" aria-labelledby="different-title">
        <div className="pitch-head">
          <span className="eyebrow">WHY IT'S DIFFERENT</span>
          <h2 id="different-title">
            Evidence first.
            <br />
            <span className="dim">AI where it helps.</span>
          </h2>
        </div>
        <div className="pitch-grid">
          {different.map((item) => (
            <article className="pitch-card accent" key={item.title}>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
