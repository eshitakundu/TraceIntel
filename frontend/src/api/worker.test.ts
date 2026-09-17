import { afterEach, expect, it, vi } from "vitest";
import worker from "../../worker";

const assets = { fetch: async () => new Response("asset") };
afterEach(() => vi.unstubAllGlobals());

it("fails explicitly when the API origin is not configured", async () => {
  const response = await worker.fetch(
    new Request("https://site.test/api/v1/chains"),
    { ASSETS: assets },
  );
  expect(response.status).toBe(503);
});
it("overwrites caller-supplied proxy identity and forwards JSON", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response("{}"));
  vi.stubGlobal("fetch", fetch);
  await worker.fetch(
    new Request("https://site.test/api/v1/analyses", {
      method: "POST",
      headers: {
        "CF-Connecting-IP": "203.0.113.1",
        "X-TraceIntel-Client-IP": "spoofed",
      },
      body: "{}",
    }),
    {
      ASSETS: assets,
      API_ORIGIN: "https://api.test",
      API_PROXY_TOKEN: "configured-secret",
    },
  );
  const init = fetch.mock.calls[0][1] as RequestInit;
  const headers = new Headers(init.headers);
  expect(headers.get("X-TraceIntel-Client-IP")).toBe("203.0.113.1");
  expect(headers.get("X-TraceIntel-Proxy-Token")).toBe("configured-secret");
});
it("rejects a body that exceeds the API limit", async () => {
  const response = await worker.fetch(
    new Request("https://site.test/api/v1/analyses", {
      method: "POST",
      body: "x".repeat(4097),
    }),
    {
      ASSETS: assets,
      API_ORIGIN: "https://api.test",
      API_PROXY_TOKEN: "configured-secret",
    },
  );
  expect(response.status).toBe(413);
});
