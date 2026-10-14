import { defineConfig, devices } from "@playwright/test";

// End-to-end tests run the real stack: FastAPI on :8000 and Next.js on :3000.
// The backend uses a throwaway SQLite file so tests never touch your local experiment log.
const isCI = !!process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  forbidOnly: isCI,
  reporter: isCI ? [["github"], ["list"]] : "list",
  use: { baseURL: "http://127.0.0.1:3000", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "uv run uvicorn simforge.main:app --host 127.0.0.1 --port 8000",
      cwd: "../backend",
      url: "http://127.0.0.1:8000/api/v1/health",
      env: { SIMFORGE_DB_PATH: "/tmp/simforge-e2e.sqlite3" },
      reuseExistingServer: !isCI,
      timeout: 60_000,
    },
    {
      command: isCI
        ? "npm run start -- --hostname 127.0.0.1"
        : "npm run dev -- --hostname 127.0.0.1",
      url: "http://127.0.0.1:3000",
      reuseExistingServer: !isCI,
      timeout: 120_000,
    },
  ],
});
