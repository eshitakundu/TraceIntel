const rules = [
  ["Unlimited ERC20 allowance", 30],
  ["Collection-wide NFT operator", 30],
  ["Finite positive allowance", 10],
  ["Contract spender", 10],
  ["Explicitly unverified target", 12],
  ["Proxy architecture / execution status", 0],
];
export default function Documentation({
  kind,
}: {
  kind: "methodology" | "architecture";
}) {
  return (
    <article className="document">
      <div className="eyebrow">TRACEINTEL / DESIGN CONTRACT</div>
      <h1>
        {kind === "methodology"
          ? "Evidence before interpretation."
          : "A deliberate separation."}
      </h1>
      {kind === "methodology" ? (
        <>
          <p>
            Risk indicators are not proof of maliciousness. The score describes
            observed indicators and is not a probability of loss or a safety
            rating.
          </p>
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
                  <td>{score}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>
            Sum the highest contribution for each rule code, capped at 100.
            Repeated logs cannot multiply a rule. Bands: 0 minimal, 1–19 low,
            20–49 moderate, 50–79 high, 80–100 critical.
          </p>
          <h2>Historical risk and current exposure</h2>
          <p>
            The historical score describes the original transaction. Exposure is
            a separate deterministic comparison of ERC-20 approval events with
            allowance, owner balance and spender bytecode at a recorded current
            block. It never changes the historical score.
          </p>
          <p>
            Active means the amount matches; partially active means it decreased
            but remains positive. Revoked means zero current allowance, without
            inferring why. Superseded means a later event or increased current
            amount replaced the historical amount. Unknown means allowance could
            not be verified. Superseded can still be active.
          </p>
          <p>
            Refresh uses a five-minute cache window. Saved reports are immutable
            snapshots, not continuous monitoring. Zero balance and absent
            bytecode do not revoke permission.
          </p>
          <h2>Completeness is independent</h2>
          <p>
            Unavailable RPC, explorer, ABI, trace, and contract data is shown
            explicitly. Missing data never subtracts points. Unknown
            verification is not labelled unverified.
          </p>
          <h2>Protocol limitations</h2>
          <p>
            Event patterns do not prove token compliance. Emitted approvals are
            not current allowances. Contract state is block-end; explorer
            metadata is current. Without traces, internal native movements are
            unknown.
          </p>
          <h2>Reproducible evaluation</h2>
          <p>
            Recorded Ethereum/Monad evidence and synthetic edge cases check
            extraction, signals, scoring stability and source references.
            Scripted NOOA execution tests reject invented claims and altered
            citations.
          </p>
        </>
      ) : (
        <>
          <p>
            Blockchain evidence → deterministic decoding → risk signals and
            scoring → current-state exposure comparison → NOOA interpretation →
            report.
          </p>
          <h2>Immutable contracts</h2>
          <p>
            Frozen Pydantic models carry stable evidence IDs across stages.
            Nested evidence is serialized, so agents cannot mutate underlying
            dictionaries. Agent output is separately validated against an
            approved claim catalog.
          </p>
          <h2>Independent storage</h2>
          <p>
            SQLAlchemy adapters support SQLite and PostgreSQL behind repository
            interfaces. Alembic manages migrations. Persisted jobs provide real
            progress, duplicate suppression and restart recovery.
          </p>
          <h2>Deployment</h2>
          <p>
            A Python 3.12 FastAPI backend and Node 22 React/Vite frontend.
            Cloudflare serves the frontend and proxies API requests to Render
            Docker with PostgreSQL in Singapore. The public demo uses free
            compute and may need time to wake after inactivity.
          </p>
        </>
      )}
    </article>
  );
}
