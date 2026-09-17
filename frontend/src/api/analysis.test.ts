import { afterEach, expect, it, vi } from "vitest";
import { ApiError, submitAnalysis } from "./analysis";
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
it("preserves gateway status even for an HTML failure", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response("<html>Bad Gateway</html>", { status: 502 }),
      ),
  );
  await expect(submitAnalysis("ethereum", "0x")).rejects.toMatchObject({
    status: 502,
  });
});
it("times out a stuck submission without replaying it", async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn(
    (_url, options: RequestInit) =>
      new Promise((_resolve, reject) => {
        options.signal?.addEventListener(
          "abort",
          () => reject(new DOMException("Aborted", "AbortError")),
          { once: true },
        );
      }),
  );
  vi.stubGlobal("fetch", fetcher);
  const outcome = submitAnalysis("monad", "0x").catch((error) => error);
  await vi.advanceTimersByTimeAsync(35000);
  expect(await outcome).toBeInstanceOf(ApiError);
  expect((await outcome).message).toContain("timed out");
  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(vi.getTimerCount()).toBe(0);
});
it("preserves actionable request errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        Response.json(
          { detail: "Hourly request limit reached." },
          { status: 429 },
        ),
      ),
  );
  await expect(submitAnalysis("ethereum", "0x")).rejects.toMatchObject({
    status: 429,
    message: "Hourly request limit reached.",
  });
});
