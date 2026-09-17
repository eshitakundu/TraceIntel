import { useEffect, useState } from "react";
import { watchReadiness, type ReadinessState } from "../api/readiness";

export function useHealth() {
  const [state, setState] = useState<ReadinessState>("checking");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => watchReadiness(setState), [attempt]);
  return {
    state,
    retry: () => {
      setState("checking");
      setAttempt((value) => value + 1);
    },
  };
}
