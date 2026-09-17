import ActivityStatus from "./ActivityStatus";
import { useOutletContext } from "react-router-dom";
import type { useHealth } from "../hooks/useHealth";

export default function BackendStatus() {
  const { state, retry } = useOutletContext<ReturnType<typeof useHealth>>();
  if (state !== "unavailable")
    return (
      <ActivityStatus
        title={
          state === "waking" ? "Backend waking up…" : "Checking connection…"
        }
        description="Your saved analysis will load automatically when the backend is ready."
      />
    );
  return (
    <section className="panel">
      <p role="status">
        {state === "unavailable"
          ? "API unavailable"
          : state === "waking"
            ? "Backend waking up…"
            : "Checking connection…"}
      </p>
      <p>
        Your saved analysis will load automatically when the backend is ready.
      </p>
      {state === "unavailable" && (
        <button onClick={retry}>Retry connection</button>
      )}
    </section>
  );
}
