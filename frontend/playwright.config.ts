import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  grepInvert: process.env.TRACEINTEL_LIVE_E2E ? undefined : /@live/,
  use: { baseURL: "http://127.0.0.1:5173" },
  webServer: [
    {
      command:
        "uv run alembic upgrade head && uv run uvicorn app.main:app --app-dir backend --port 8000",
      cwd: "..",
      url: "http://127.0.0.1:8000/api/v1/health",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: "npm run dev -- --host 127.0.0.1",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: !process.env.CI,
    },
  ],
});
