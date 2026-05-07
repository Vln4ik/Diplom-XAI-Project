import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const e2eStateDir = path.join(repoRoot, ".tmp", "playwright");
const e2eDatabasePath = path.join(e2eStateDir, "playwright-e2e.db");
const e2eStoragePath = path.join(e2eStateDir, "storage");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  timeout: 180_000,
  expect: {
    timeout: 15_000,
  },
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4174",
    acceptDownloads: true,
    trace: "on-first-retry",
  },
  webServer: [
    {
      command: `zsh -lc 'rm -rf "${e2eStateDir}" && mkdir -p "${e2eStoragePath}" && ../.venv/bin/alembic upgrade head && ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010'`,
      cwd: path.join(repoRoot, "backend"),
      url: "http://127.0.0.1:8010/docs",
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        XAI_APP_ALLOWED_ORIGINS: JSON.stringify(["http://127.0.0.1:4174", "http://localhost:4174"]),
        XAI_APP_BOOTSTRAP_ADMIN_EMAIL: "admin@example.com",
        XAI_APP_BOOTSTRAP_ADMIN_PASSWORD: "ChangeMe123!",
        XAI_APP_BOOTSTRAP_ADMIN_FULL_NAME: "Browser E2E Admin",
        XAI_APP_CELERY_TASK_ALWAYS_EAGER: "true",
        XAI_APP_DATABASE_URL: `sqlite:///${e2eDatabasePath}`,
        XAI_APP_SECRET_KEY: "playwright-e2e-secret-key-with-32-plus-bytes",
        XAI_APP_STORAGE_PATH: e2eStoragePath,
      },
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 4174",
      cwd: __dirname,
      url: "http://127.0.0.1:4174/login",
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        VITE_API_BASE_URL: "http://127.0.0.1:8010",
      },
    },
  ],
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
  ],
});
