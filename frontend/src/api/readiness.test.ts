import { afterEach, expect, it, vi } from "vitest";
import {
  watchReadiness,
  waitForReadiness,
  type ReadinessState,
} from "./readiness";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
const healthy = () =>
  Response.json({ status: "ok", service: "traceintel-api", version: "0.1.0" });

it("connects only after valid readiness JSON, recovering from cold starts", async () => {
  vi.useFakeTimers();
  const fetcher = vi
    .fn()
    .mockResolvedValueOnce(new Response("", { status: 503 }))
    .mockResolvedValueOnce(Response.json({ status: "ok" }))
    .mockResolvedValueOnce(healthy());
  vi.stubGlobal("fetch", fetcher);
  const states: ReadinessState[] = [];
  const stop = watchReadiness((state) => states.push(state));
  await vi.advanceTimersByTimeAsync(0);
  expect(states).toEqual(["checking", "waking"]);
  await vi.advanceTimersByTimeAsync(2999);
  expect(fetcher).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(5001);
  expect(states).toEqual(["checking", "waking", "waking", "connected"]);
  expect(fetcher.mock.calls[0][0]).toBe("/api/v1/ready");
  await vi.advanceTimersByTimeAsync(200000);
  expect(fetcher).toHaveBeenCalledTimes(3);
  stop();
});

it("exhausts bounded retries and permits a fresh manual attempt", async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn().mockRejectedValue(new Error("asleep"));
  vi.stubGlobal("fetch", fetcher);
  const states: ReadinessState[] = [];
  const stop = watchReadiness((state) => states.push(state));
  await vi.runAllTimersAsync();
  expect(fetcher).toHaveBeenCalledTimes(8);
  expect(states.at(-1)).toBe("unavailable");
  stop();
  fetcher.mockResolvedValue(healthy());
  const retry = watchReadiness((state) => states.push(state));
  await vi.runAllTimersAsync();
  expect(states.slice(-2)).toEqual(["checking", "connected"]);
  retry();
});

it("times out hung requests within the total retry budget", async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn(
    (_url, options: RequestInit) =>
      new Promise((_resolve, reject) => {
        options.signal?.addEventListener(
          "abort",
          () => reject(new Error("timeout")),
          { once: true },
        );
      }),
  );
  vi.stubGlobal("fetch", fetcher);
  const states: ReadinessState[] = [];
  const stop = watchReadiness((state) => states.push(state));
  await vi.advanceTimersByTimeAsync(131000);
  expect(states.at(-1)).toBe("unavailable");
  expect(fetcher).toHaveBeenCalledTimes(8);
  expect(vi.getTimerCount()).toBe(0);
  stop();
});

it("cancels pending retries on unmount", async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn().mockRejectedValue(new Error("asleep"));
  vi.stubGlobal("fetch", fetcher);
  const states: ReadinessState[] = [];
  const stop = watchReadiness((state) => states.push(state));
  await vi.advanceTimersByTimeAsync(0);
  stop();
  await vi.runAllTimersAsync();
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(states).toEqual(["checking", "waking"]);
});

it("ignores a late response after cancellation", async () => {
  let resolve!: (response: Response) => void;
  vi.stubGlobal(
    "fetch",
    vi.fn(
      () =>
        new Promise<Response>((done) => {
          resolve = done;
        }),
    ),
  );
  const states: ReadinessState[] = [];
  const stop = watchReadiness((state) => states.push(state));
  stop();
  resolve(healthy());
  await new Promise((done) => setTimeout(done, 0));
  expect(states).toEqual(["checking"]);
});

it("preflight resolves only after recovery and clears its timers", async () => {
  vi.useFakeTimers();
  const fetcher = vi
    .fn()
    .mockRejectedValueOnce(new Error("asleep"))
    .mockResolvedValueOnce(healthy());
  vi.stubGlobal("fetch", fetcher);
  const states: ReadinessState[] = [];
  const pending = waitForReadiness(new AbortController().signal, (state) =>
    states.push(state),
  );
  await vi.advanceTimersByTimeAsync(3000);
  await expect(pending).resolves.toBeUndefined();
  expect(states).toEqual(["checking", "waking", "connected"]);
  expect(vi.getTimerCount()).toBe(0);
});

it("cancelled preflight never retries or submits", async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn().mockRejectedValue(new Error("asleep"));
  vi.stubGlobal("fetch", fetcher);
  const controller = new AbortController();
  const outcome = waitForReadiness(controller.signal, () => {}).catch(
    (error) => error,
  );
  await vi.advanceTimersByTimeAsync(0);
  controller.abort();
  await vi.runAllTimersAsync();
  expect((await outcome).name).toBe("AbortError");
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(vi.getTimerCount()).toBe(0);
});
