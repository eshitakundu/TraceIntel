import { afterEach, expect, it, vi } from "vitest";
import { getHealth } from "./client";

afterEach(() => vi.unstubAllGlobals());
it("checks the backend response contract", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({
            status: "ok",
            service: "traceintel-api",
            version: "0.1.0",
          }),
        ),
      ),
  );
  expect((await getHealth()).status).toBe("ok");
});
it("rejects an HTML fallback instead of claiming connectivity", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ wrong: true }))),
  );
  await expect(getHealth()).rejects.toThrow("unexpected");
});
it("surfaces backend failures", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response("", { status: 503 })),
  );
  await expect(getHealth()).rejects.toThrow("unavailable");
});
