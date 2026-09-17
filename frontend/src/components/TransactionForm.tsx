import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import {
  getChains,
  submitAnalysis,
  isTemporaryApiError,
} from "../api/analysis";
import { waitForReadiness } from "../api/readiness";
import type { useHealth } from "../hooks/useHealth";
import ActivityStatus from "./ActivityStatus";
import type { Chain } from "../types/report";

export default function TransactionForm({ ready }: { ready: boolean }) {
  const [chains, setChains] = useState<Chain[]>([]);
  const [chain, setChain] = useState("ethereum");
  const [hash, setHash] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const { state, retry, markUnavailable } =
    useOutletContext<ReturnType<typeof useHealth>>();
  const [phase, setPhase] = useState<"checking" | "waking" | "submitting">(
    "checking",
  );
  const submission = useRef<AbortController | null>(null);
  useEffect(() => () => submission.current?.abort(), []);
  useEffect(() => {
    if (!ready) return;
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
  }, [ready]);
  async function analyze(
    event?: FormEvent,
    sample?: { chain: string; hash: string },
  ) {
    event?.preventDefault();
    if (!ready || busy || submission.current || !chains.length) return;
    const value = (sample?.hash ?? hash).trim();
    if (!/^0x[0-9a-fA-F]{64}$/.test(value)) {
      setError("Enter a 0x-prefixed, 64-digit transaction hash.");
      return;
    }
    const selectedChain = sample?.chain ?? chain;
    setChain(selectedChain);
    setHash(value);
    const controller = new AbortController();
    submission.current = controller;
    setPhase("checking");
    setBusy(true);
    setError("");
    let submitted = false;
    try {
      await waitForReadiness(controller.signal, (next) => {
        if (next === "checking" || next === "waking") setPhase(next);
      });
      if (controller.signal.aborted) return;
      setPhase("submitting");
      submitted = true;
      const job = await submitAnalysis(selectedChain, value, controller.signal);
      navigate("/analysis/" + job.id);
    } catch (error) {
      if (controller.signal.aborted) return;
      if (!submitted) markUnavailable();
      if (isTemporaryApiError(error)) {
        setError(
          "The API connection failed before we could confirm your analysis. It may already have been accepted. Your hash is preserved; retry once the connection is restored.",
        );
        retry();
      } else {
        setError(
          error instanceof Error ? error.message : "Analysis could not start.",
        );
      }
    } finally {
      submission.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  return (
    <>
      <section className="panel transaction-panel">
        <div className="section-heading">
          <h2>Analyze a transaction</h2>
          <span className="badge">READ-ONLY</span>
        </div>
        <form aria-busy={busy} onSubmit={(event) => void analyze(event)}>
          <div className="form-grid">
            <fieldset className="network-selector" disabled={busy || !ready}>
              <legend>Network</legend>
              <div className="network-options">
                {(chains.length
                  ? chains
                  : [
                      { slug: "ethereum", name: "Ethereum" },
                      { slug: "monad", name: "Monad" },
                    ]
                ).map((item) => (
                  <label
                    key={item.slug}
                    className={"network-option " + item.slug}
                  >
                    <input
                      type="radio"
                      name="network"
                      value={item.slug}
                      checked={chain === item.slug}
                      onChange={() => setChain(item.slug)}
                    />
                    <span>
                      <i aria-hidden="true" />
                      {item.name}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
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
            <button disabled={busy || !ready || !chains.length}>
              {busy
                ? "Please wait…"
                : error
                  ? "Retry analysis →"
                  : "Analyze transaction →"}
            </button>
          </div>
          {busy && (
            <ActivityStatus
              title={
                phase === "submitting"
                  ? "Submitting transaction…"
                  : phase === "waking"
                    ? "Backend waking up…"
                    : "Checking backend before submission…"
              }
              description={
                phase === "submitting"
                  ? "Waiting for a job ID. The analysis stages will appear as soon as the API accepts your request."
                  : "Render may need time to wake after inactivity. Retrying automatically for up to about two minutes."
              }
            />
          )}
          {!busy &&
            !ready &&
            (state === "unavailable" ? (
              <div className="readiness-note">
                <p>
                  The backend could not be reached. Your input is preserved.
                </p>
                <button type="button" className="secondary" onClick={retry}>
                  Retry backend connection
                </button>
              </div>
            ) : (
              <ActivityStatus
                title={
                  state === "waking"
                    ? "Backend waking up…"
                    : "Checking connection…"
                }
                description="Analysis will become available automatically when the backend is ready."
              />
            ))}
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
              name: "Recorded transaction",
              hash: "0xa5e6aec48fffd1c35d8410e2e81b63e1fca740bde922f5f2d4b7da50f65f532f",
            },
            {
              chain: "monad",
              name: "Recorded transaction",
              hash: "0x3284afdd9fe66c9d0832cf640c1dd0da02ea9e990ffc091503d13d533fad7c2c",
            },
          ].map((sample) => (
            <button
              className="sample"
              key={sample.hash}
              disabled={busy || !ready || !chains.length}
              onClick={() => void analyze(undefined, sample)}
            >
              <span className={"sample-network " + sample.chain}>
                {sample.chain === "ethereum" ? "Ethereum" : "Monad"}
              </span>
              <strong>{sample.name}</strong>
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
