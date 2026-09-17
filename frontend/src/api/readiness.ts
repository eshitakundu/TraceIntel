import { getHealth } from "./client";

export type ReadinessState =
  "checking" | "waking" | "connected" | "unavailable";

// At most eight 8-second requests and 67 seconds of backoff (131 seconds).
const delays = [3000, 5000, 8000, 10000, 12000, 14000, 15000];

export function watchReadiness(onState: (state: ReadinessState) => void) {
  let stopped = false;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  let controller: AbortController;
  onState("checking");

  async function attempt(index: number) {
    controller = new AbortController();
    timeout = setTimeout(() => controller.abort(), 8000);
    try {
      await getHealth(controller.signal);
      if (!stopped) onState("connected");
    } catch {
      if (stopped) return;
      if (index === delays.length) onState("unavailable");
      else {
        onState("waking");
        retryTimer = setTimeout(() => void attempt(index + 1), delays[index]);
      }
    } finally {
      clearTimeout(timeout);
    }
  }
  void attempt(0);
  return () => {
    stopped = true;
    clearTimeout(retryTimer);
    clearTimeout(timeout);
    controller.abort();
  };
}

// Recheck immediately before a submission: a previously ready free service may sleep.
export function waitForReadiness(
  signal: AbortSignal,
  onState: (state: ReadinessState) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(signal.reason);
      return;
    }
    let stop: () => void = () => {};
    const cleanup = () => {
      stop();
      signal.removeEventListener("abort", abort);
    };
    const abort = () => {
      cleanup();
      reject(signal.reason);
    };
    signal.addEventListener("abort", abort, { once: true });
    stop = watchReadiness((state) => {
      onState(state);
      if (state === "connected") {
        cleanup();
        resolve();
      }
      if (state === "unavailable") {
        cleanup();
        reject(
          new Error(
            "The backend did not become ready within two minutes. Your transaction has not been submitted. Please retry the connection.",
          ),
        );
      }
    });
  });
}
