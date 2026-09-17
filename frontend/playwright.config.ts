import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  grepInvert: process.env.TRACEINTEL_LIVE_E2E ? undefined : /@live/,
  use: { baseURL: "http://127.0.0.1:15173" },
  webServer: [
    {
      command:
        "uv run alembic upgrade head && uv run uvicorn app.main:app --app-dir backend --port 18000",
      cwd: "..",
      url: "http://127.0.0.1:18000/api/v1/ready",
      reuseExistingServer: false,
    },
    {
      command:
        "TRACEINTEL_DEV_API_ORIGIN=http://127.0.0.1:18000 npm run dev -- --host 127.0.0.1 --port 15173 --strictPort",
      url: "http://127.0.0.1:15173",
      reuseExistingServer: false,
    },
  ],
});
