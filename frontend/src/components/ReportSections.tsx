import type { Report } from "../types/report";
import EvidenceLinks from "./EvidenceLinks";

const short = (value: string) =>
  value.length > 20 ? value.slice(0, 8) + "…" + value.slice(-6) : value;
export function AssetMovements({ report }: { report: Report }) {
  return (
    <section className="report-section" id="movements">
      <h2>
        Asset movements{" "}
        <span className="count">{report.decoded.movements.length}</span>
      </h2>
      {report.decoded.movements.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Asset / standard</th>
                <th>From → To</th>
                <th>Quantity</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {report.decoded.movements.map((movement, index) => (
                <tr key={index}>
                  <td>
                    <strong>{movement.symbol || short(movement.token)}</strong>
                    <small>
                      {movement.standard}
                      {movement.token_id && " · token #" + movement.token_id}
                    </small>
                  </td>
                  <td>
                    <code title={movement.sender}>
                      {short(movement.sender)}
                    </code>{" "}
                    →{" "}
                    <code title={movement.recipient}>
                      {short(movement.recipient)}
                    </code>
                  </td>
                  <td className="amount">
                    {movement.amount_raw}
                    <small>
                      raw units
                      {movement.decimals !== null &&
                        " · " + movement.decimals + " decimals"}
                    </small>
                  </td>
                  <td>
                    <EvidenceLinks ids={movement.evidence_ids} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty">
          No completed asset movements identified in the available evidence.
        </p>
      )}
      <p className="note">
        Raw quantities preserve exact precision. Internal movements require
        tracing; missing metadata is not guessed.
      </p>
    </section>
  );
}
export function Approvals({ report }: { report: Report }) {
  return (
    <section className="report-section" id="approvals">
      <h2>
        Approvals{" "}
        <span className="count">{report.decoded.approvals.length}</span>
      </h2>
      {report.decoded.approvals.length ? (
        report.decoded.approvals.map((approval, index) => (
          <article className="approval-card" key={index}>
            <div className="section-heading">
              <strong>{approval.standard} permission</strong>
              <span className={approval.unlimited ? "badge high" : "badge"}>
                {approval.unlimited
                  ? "UNLIMITED / ALL"
                  : approval.amount_raw === "0"
                    ? "REVOKED"
                    : "LIMITED"}
              </span>
            </div>
            <dl>
              <dt>Token contract</dt>
              <dd className="hash">{approval.token}</dd>
              <dt>Owner</dt>
              <dd className="hash">{approval.owner}</dd>
              <dt>Spender</dt>
              <dd className="hash">{approval.spender}</dd>
              <dt>Emitted amount / token ID</dt>
              <dd className="hash">{approval.amount_raw}</dd>
            </dl>
            <EvidenceLinks ids={approval.evidence_ids} />
          </article>
        ))
      ) : (
        <p className="empty">No supported approval events identified.</p>
      )}
      <p className="note">
        Emitted approvals describe this transaction. They do not establish the
        current allowance.
      </p>
    </section>
  );
}
export function Contracts({ report }: { report: Report }) {
  return (
    <section className="report-section" id="contracts">
      <h2>Contract intelligence</h2>
      {report.contracts.length ? (
        report.contracts.map((contract) => (
          <article className="contract-card" key={contract.address}>
            <div className="section-heading">
              <code className="hash">{contract.address}</code>
              <span className="badge">{contract.kind.replace("_", " ")}</span>
            </div>
            <dl className="contract-facts">
              <dt>Source verification</dt>
              <dd>{contract.verification}</dd>
              <dt>Proxy pattern</dt>
              <dd>{contract.proxy.replace("_", " ")}</dd>
              <dt>Implementation</dt>
              <dd className="hash">
                {contract.implementation ?? "Not identified"}
              </dd>
            </dl>
            <EvidenceLinks ids={contract.evidence_ids} />
          </article>
        ))
      ) : (
        <p>No contract addresses to inspect.</p>
      )}
    </section>
  );
}
export function RiskEvidence({ report }: { report: Report }) {
  return (
    <section className="report-section" id="risk">
      <h2>Risk evidence</h2>
      {report.risk.signals.map((signal, index) => (
        <article className="signal-card" key={index}>
          <div className="section-heading">
            <span className={"severity " + signal.severity}>
              {signal.severity}
            </span>
            <span className="points">+{signal.score} rule points</span>
          </div>
          <h3>{signal.title}</h3>
          <p>{signal.description}</p>
          <details>
            <summary>Why this triggered</summary>
            <p>{signal.reason}</p>
            <code>{signal.source}</code>
          </details>
          <EvidenceLinks ids={signal.evidence_ids} />
        </article>
      ))}
      <p className="note">
        One contribution per rule code. Repeated findings do not multiply the
        score. Rules v{report.risk.version}.
      </p>
    </section>
  );
}
export function RawEvidence({ report }: { report: Report }) {
  return (
    <section className="report-section" id="evidence">
      <h2>
        Raw evidence{" "}
        <span className="count">{report.decoded.evidence.length}</span>
      </h2>
      {report.decoded.evidence.map((evidence) => (
        <details
          className="raw-evidence"
          id={"evidence-" + encodeURIComponent(evidence.id)}
          key={evidence.id}
        >
          <summary>
            <span>{evidence.description}</span>
            <code>{evidence.id.split(":").slice(2).join(":")}</code>
          </summary>
          <p>{evidence.source}</p>
          <pre>{JSON.stringify(JSON.parse(evidence.data_json), null, 2)}</pre>
        </details>
      ))}
    </section>
  );
}
