import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: { include: ["src/**/*.test.ts"] },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/openapi.json": "http://127.0.0.1:8000",
      "/docs": "http://127.0.0.1:8000",
    },
  },
});
