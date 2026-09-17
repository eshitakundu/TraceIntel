import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { getChains, submitAnalysis } from "../api/analysis";
import type { Chain } from "../types/report";

export default function TransactionForm() {
  const [chains, setChains] = useState<Chain[]>([]);
  const [chain, setChain] = useState("ethereum");
  const [hash, setHash] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    const controller = new AbortController();
    getChains(controller.signal)
      .then(setChains)
      .catch((error) => {
        if (!controller.signal.aborted)
          setError(
            error instanceof Error ? error.message : "Could not load networks.",
          );
      });
    return () => controller.abort();
  }, []);
  async function analyze(
    event?: FormEvent,
    sample?: { chain: string; hash: string },
  ) {
    event?.preventDefault();
    const value = (sample?.hash ?? hash).trim();
    if (!/^0x[0-9a-fA-F]{64}$/.test(value)) {
      setError("Enter a 0x-prefixed, 64-digit transaction hash.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const job = await submitAnalysis(sample?.chain ?? chain, value);
      navigate("/analysis/" + job.id);
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Analysis could not start.",
      );
      setBusy(false);
    }
  }
  return (
    <>
      <section className="panel transaction-panel">
        <div className="section-heading">
          <h2>Analyze a transaction</h2>
          <span className="badge">READ-ONLY</span>
        </div>
        <form onSubmit={(event) => void analyze(event)}>
          <div className="form-grid">
            <label>
              Network
              <select
                value={chain}
                onChange={(event) => setChain(event.target.value)}
                disabled={!chains.length || busy}
              >
                {chains.map((item) => (
                  <option key={item.slug} value={item.slug}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Transaction hash
              <input
                value={hash}
                onChange={(event) => setHash(event.target.value)}
                placeholder="0x…"
                spellCheck={false}
                autoComplete="off"
                disabled={busy}
              />
            </label>
          </div>
          <div className="form-bottom">
            <span>Public on-chain data. No wallet connection required.</span>
            <button disabled={busy || !chains.length}>
              {busy ? "Starting analysis…" : "Analyze transaction →"}
            </button>
          </div>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </form>
      </section>
      <section>
        <div className="section-heading">
          <h2>Start with a real transaction</h2>
          <span className="label">PUBLIC CHAIN EXAMPLES</span>
        </div>
        <div className="sample-grid">
          {[
            {
              chain: "ethereum",
              name: "Approval activity",
              hash: "0xe7ac5477adad86fe9f70854da18b0a182b878773381421418d5bf1a69514645f",
            },
            {
              chain: "ethereum",
              name: "Ethereum",
              hash: "0xa5e6aec48fffd1c35d8410e2e81b63e1fca740bde922f5f2d4b7da50f65f532f",
            },
            {
              chain: "monad",
              name: "Monad",
              hash: "0x3284afdd9fe66c9d0832cf640c1dd0da02ea9e990ffc091503d13d533fad7c2c",
            },
          ].map((sample) => (
            <button
              className="sample"
              key={sample.hash}
              disabled={busy}
              onClick={() => void analyze(undefined, sample)}
            >
              <span>{sample.name} / recorded transaction</span>
              <code>
                {sample.hash.slice(0, 14)}…{sample.hash.slice(-8)}
              </code>
              <span>Inspect evidence ↗</span>
            </button>
          ))}
        </div>
      </section>
    </>
  );
}
