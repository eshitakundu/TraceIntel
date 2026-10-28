const rules = [
  ["Unlimited ERC20 allowance", 30],
  ["Collection-wide NFT operator", 30],
  ["Finite positive allowance", 10],
  ["Contract spender", 10],
  ["Explicitly unverified target", 12],
  ["Proxy architecture / execution status", 0],
];

const methodology = [
  {
    title: "Historical risk and current exposure",
    body: [
      "The historical score describes the original transaction. Exposure is a separate deterministic comparison of ERC-20 approval events with allowance, owner balance and spender bytecode at a recorded current block. It never changes the historical score.",
    ],
  },
  {
    title: "Exposure states",
    body: [
      "Active means the amount matches; partially active means it decreased but remains positive. Revoked means zero current allowance, without inferring why.",
      "Superseded means a later event or increased current amount replaced the historical amount. Unknown means allowance could not be verified. Superseded can still be active.",
    ],
  },
  {
    title: "Snapshots, not monitoring",
    body: [
      "Refresh uses a five-minute cache window. Saved reports are immutable snapshots, not continuous monitoring. Zero balance and absent bytecode do not revoke permission.",
    ],
  },
  {
    title: "Completeness is independent",
    body: [
      "Unavailable RPC, explorer, ABI, trace, and contract data is shown explicitly. Missing data never subtracts points. Unknown verification is not labelled unverified.",
    ],
  },
  {
    title: "Protocol limitations",
    body: [
      "Event patterns do not prove token compliance. Emitted approvals are not current allowances. Contract state is block-end; explorer metadata is current. Without traces, internal native movements are unknown.",
    ],
  },
  {
    title: "Reproducible evaluation",
    body: [
      "Recorded Ethereum/Monad evidence and synthetic edge cases check extraction, signals, scoring stability and source references. Scripted NOOA execution tests reject invented claims and altered citations.",
    ],
  },
];

const architecture = [
  {
    title: "Immutable contracts",
    body: [
      "Frozen Pydantic models carry stable evidence IDs across stages. Nested evidence is serialized, so agents cannot mutate underlying dictionaries. Agent output is separately validated against an approved claim catalog.",
    ],
  },
  {
    title: "Independent storage",
    body: [
      "SQLAlchemy adapters support SQLite and PostgreSQL behind repository interfaces. Alembic manages migrations. Persisted jobs provide real progress, duplicate suppression and restart recovery.",
    ],
  },
  {
    title: "Deployment",
    body: [
      "A Python 3.12 FastAPI backend and Node 22 React/Vite frontend. Cloudflare serves the frontend and proxies API requests to Render Docker with PostgreSQL in Singapore. The public demo uses free compute and may need time to wake after inactivity.",
    ],
  },
];

const pipeline = [
  "Blockchain evidence",
  "Deterministic decoding",
  "Risk signals and scoring",
  "Current-state exposure",
  "NOOA interpretation",
  "Report",
];

export default function Documentation({
  kind,
}: {
  kind: "methodology" | "architecture";
}) {
  const cards = kind === "methodology" ? methodology : architecture;
  return (
    <article className="document trace-light-page reference-page">
      <div className="eyebrow">
        {kind === "methodology" ? "How TraceIntel reasons" : "How TraceIntel is built"}
      </div>
      <h1>
        {kind === "methodology"
          ? "Evidence before interpretation."
          : "A deliberate separation."}
      </h1>
      {kind === "methodology" ? (
        <>
          <p className="lead">
            Risk indicators are not proof of maliciousness. The score describes
            observed indicators and is not a probability of loss or a safety
            rating.
          </p>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Rule</th>
                  <th>Points</th>
                </tr>
              </thead>
              <tbody>
                {rules.map(([rule, score]) => (
                  <tr key={rule}>
                    <td>{rule}</td>
                    <td className="points-cell">{score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="note">
            Sum the highest contribution for each rule code, capped at 100.
            Repeated logs cannot multiply a rule. Bands: 0 minimal, 1–19 low,
            20–49 moderate, 50–79 high, 80–100 critical.
          </p>
        </>
      ) : (
        <ol className="pipeline" aria-label="Analysis pipeline">
          {pipeline.map((stage, index) => (
            <li key={stage}>
              <span className="pixel">
                {String(index + 1).padStart(2, "0")}
              </span>
              {stage}
            </li>
          ))}
        </ol>
      )}
      <div className="doc-grid">
        {cards.map((card) => (
          <section className="doc-card" key={card.title}>
            <h2>{card.title}</h2>
            {card.body.map((text) => (
              <p key={text}>{text}</p>
            ))}
          </section>
        ))}
      </div>
    </article>
  );
}
