import { useOutletContext } from "react-router-dom";
import type { useHealth } from "../hooks/useHealth";
import TransactionForm from "../components/TransactionForm";
import DemoWalkthrough from "../components/DemoWalkthrough";

const caseStages = [
  {
    key: "then",
    label: "Approval",
    title: "WETH permission",
    text: "The transaction emitted a positive allowance.",
    facts: [
      ["Tx", "0xe7ac…645f"],
      ["Block", "25,995,282"],
      ["Spender", "0xbbbb…ffcb"],
    ],
  },
  {
    key: "now",
    label: "Current state",
    title: "Allowance active",
    text: "The recorded permission still resolves on-chain.",
    facts: [
      ["Allowance", "Unlimited"],
      ["Coverage", "9 / 9 resolved"],
      ["Spender", "Contract"],
    ],
  },
  {
    key: "decision",
    label: "Decision",
    title: "Revoke",
    text: "The live allowance no longer matches the original amount.",
    facts: [
      ["Risk", "Moderate"],
      ["Evidence", "Cited"],
      ["Method", "Validated"],
    ],
  },
];

const why = [
  {
    signal: "Persistent",
    title: "Approvals don't expire",
    text: "An unlimited approval stays live long after the swap that needed it.",
  },
  {
    signal: "Mutable",
    title: "Spenders can change",
    text: "An upgradeable spender can get new code after you said yes.",
  },
  {
    signal: "Unresolved",
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
    rule: "Decision",
    title: "Answers “should I revoke?”",
    text: "Not a list of approvals: a cited recommendation for each live permission.",
  },
  {
    rule: "Comparison",
    title: "Notices what changed",
    text: "Compares the spender at approval time with today, including upgrades and single-key control.",
  },
  {
    rule: "Guardrail",
    title: "AI that can't invent facts",
    text: "The model picks from facts written by code. A validator rejects anything else, and a rule-based baseline keeps it honest.",
  },
];

export default function Home() {
  const { state, retry } = useOutletContext<ReturnType<typeof useHealth>>();
  return (
    <>
      <section className="hero recruiter-hero">
        <div className="hero-meta">
          <span>Open-source approval forensics</span>
          <span role="status" className={"connection-pill " + state}>
            {state === "connected"
              ? "Live analysis ready"
              : state === "checking"
                ? "Checking live analysis…"
                : state === "waking"
                  ? "Live analysis waking…"
                  : "Recorded demo available"}
            {state === "unavailable" && (
              <button onClick={retry}>Retry</button>
            )}
          </span>
        </div>
        <h1>
          What changed after you approved it?
        </h1>
        <div className="hero-brief">
          <p>
            TraceIntel reconstructs an old token approval, compares it with live
            on-chain state, and recommends whether to revoke it.
          </p>
          <div className="hero-actions">
            <a className="button" href="#walkthrough">
              Watch the 1:44 walkthrough
            </a>
            <a className="hero-text-link" href="#analyze">
              Run a transaction
            </a>
          </div>
        </div>
        <div className="case-file" aria-label="Example TraceIntel decision">
          <header className="case-file-head">
            <span>TraceIntel evidence · recorded example</span>
            <code>Ethereum · 0xe7ac…645f</code>
          </header>
          <ol>
            {caseStages.map((stage, index) => (
              <li className={stage.key} key={stage.key}>
                <span className="case-count">0{index + 1}</span>
                <div>
                  <span>{stage.label}</span>
                  <strong>{stage.title}</strong>
                  <small>{stage.text}</small>
                  <dl>
                    {stage.facts.map(([term, value]) => (
                      <div key={term}>
                        <dt>{term}</dt>
                        <dd>{value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              </li>
            ))}
          </ol>
          <footer className="case-file-foot">
            <span>Historical RPC</span>
            <span>Live state</span>
            <span>Cited decision</span>
            <span>React + FastAPI</span>
          </footer>
        </div>
      </section>
      <DemoWalkthrough />
      <div id="analyze" className="analyze-anchor">
        <div className="analyze-intro">
          <span>Use the live system</span>
          <h2>Trace your own transaction.</h2>
          <p>
            Public chain data only. No wallet connection, signing, or private
            information required.
          </p>
        </div>
        <div>
          <TransactionForm ready={state === "connected"} />
        </div>
      </div>
      <section className="pitch risk-section" aria-labelledby="why-title">
        <div className="pitch-head">
          <span className="pitch-marker">Exposure, after the transaction</span>
          <h2 id="why-title">
            A finished transaction
            <br />
            <span className="dim">can leave access open.</span>
          </h2>
        </div>
        <ul className="risk-ledger">
          {why.map((item, index) => (
            <li key={item.title}>
              <span className="ledger-index" aria-hidden="true">
                0{index + 1}
              </span>
              <div>
                <span className="ledger-signal">{item.signal}</span>
                <h3>{item.title}</h3>
              </div>
              <p>{item.text}</p>
            </li>
          ))}
        </ul>
      </section>
      <section className="pitch process-section" aria-labelledby="how-title">
        <div className="pitch-head">
          <span className="pitch-marker">One transaction, examined twice</span>
          <h2 id="how-title">Four steps. One answer.</h2>
        </div>
        <ol className="process-trace">
          {how.map((step) => (
            <li key={step.key}>
              <span className="trace-node" aria-hidden="true">
                {step.key}
              </span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
      <section
        className="pitch principles-section"
        aria-labelledby="different-title"
      >
        <div className="pitch-head">
          <span className="pitch-marker">Built to show its work</span>
          <h2 id="different-title">
            Evidence first.
            <br />
            <span className="dim">AI where it helps.</span>
          </h2>
        </div>
        <div className="principle-ledger">
          {different.map((item) => (
            <article key={item.title}>
              <span>{item.rule}</span>
              <div>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
