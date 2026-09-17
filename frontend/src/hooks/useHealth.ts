import { useEffect, useState } from "react";
import { getHealth } from "../api/client";

export function useHealth() {
  const [state, setState] = useState<"checking" | "online" | "offline">(
    "checking",
  );
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    getHealth(controller.signal)
      .then(() => {
        if (active) setState("online");
      })
      .catch(() => {
        if (active) setState("offline");
      })
      .finally(() => clearTimeout(timeout));
    return () => {
      active = false;
      clearTimeout(timeout);
      controller.abort();
    };
  }, [attempt]);
  return {
    state,
    retry: () => {
      setState("checking");
      setAttempt((value) => value + 1);
    },
  };
}
