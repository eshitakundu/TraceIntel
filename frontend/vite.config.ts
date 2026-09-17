import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { include: ["src/**/*.test.ts"] },
  server: {
    proxy: {
      "/api": process.env.TRACEINTEL_DEV_API_ORIGIN ?? "http://127.0.0.1:8000",
      "/openapi.json":
        process.env.TRACEINTEL_DEV_API_ORIGIN ?? "http://127.0.0.1:8000",
      "/docs": process.env.TRACEINTEL_DEV_API_ORIGIN ?? "http://127.0.0.1:8000",
    },
  },
});
