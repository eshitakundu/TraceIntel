interface Env {
  ASSETS: { fetch(request: Request): Promise<Response> };
  API_ORIGIN?: string;
  API_PROXY_TOKEN?: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (
      url.pathname.startsWith("/api/") ||
      ["/docs", "/redoc", "/openapi.json"].includes(url.pathname)
    ) {
      if (!env.API_ORIGIN || !env.API_PROXY_TOKEN) {
        return Response.json(
          { detail: "The API deployment is not configured." },
          { status: 503 },
        );
      }
      const origin = new URL(env.API_ORIGIN);
      if (origin.protocol !== "https:")
        return Response.json(
          { detail: "Invalid API configuration." },
          { status: 503 },
        );
      if (!["GET", "POST", "OPTIONS"].includes(request.method))
        return new Response(null, { status: 405 });
      const headers = new Headers();
      headers.set(
        "Accept",
        request.headers.get("Accept") ?? "application/json",
      );
      headers.set(
        "Content-Type",
        request.headers.get("Content-Type") ?? "application/json",
      );
      headers.set("X-TraceIntel-Proxy-Token", env.API_PROXY_TOKEN);
      headers.set(
        "X-TraceIntel-Client-IP",
        request.headers.get("CF-Connecting-IP") ?? "unknown",
      );
      let body: ArrayBuffer | undefined;
      if (request.method === "POST") {
        const reader = request.body?.getReader();
        const chunks: Uint8Array[] = [];
        let size = 0;
        if (reader) {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            size += value.byteLength;
            if (size > 4096) {
              await reader.cancel();
              return Response.json(
                { detail: "Request too large." },
                { status: 413 },
              );
            }
            chunks.push(value);
          }
        }
        const bytes = new Uint8Array(size);
        let offset = 0;
        for (const chunk of chunks) {
          bytes.set(chunk, offset);
          offset += chunk.length;
        }
        body = bytes.buffer;
      }
      try {
        return await fetch(new URL(url.pathname + url.search, origin), {
          method: request.method,
          headers,
          body,
          redirect: "manual",
          signal: AbortSignal.timeout(30_000),
        });
      } catch {
        return Response.json(
          { detail: "The API is temporarily unavailable." },
          { status: 502 },
        );
      }
    }
    return env.ASSETS.fetch(request);
  },
};
