import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "@playwright/test";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(frontendRoot, "..");
const tmpRoot = path.join(projectRoot, ".tmp", "playwright");
const backendDb = path.join(tmpRoot, "backend.sqlite3");
const backendData = path.join(tmpRoot, "data");
const backendPort = process.env.SCHOLARFLOW_E2E_BACKEND_PORT ?? "8000";
const frontendPort = process.env.SCHOLARFLOW_E2E_FRONTEND_PORT ?? "4173";
const backendBaseUrl = `http://127.0.0.1:${backendPort}`;
const frontendBaseUrl = `http://127.0.0.1:${frontendPort}`;
const forceServerStart = process.env.PLAYWRIGHT_FORCE_SERVER_START === "1";
const authRequired = process.env.AUTH_REQUIRED === "1";
const authSecret = authRequired ? (process.env.AUTH_SECRET ?? "phase6-secret") : "";
const apiToken = authRequired ? (process.env.API_TOKEN ?? "") : "";
const reuseExistingServer =
  !forceServerStart && !process.env.CI && !authRequired;
const backendCommand = [
  `if [ -x "${path.join(projectRoot, ".venv", "bin", "python")}" ]; then`,
  `  "${path.join(projectRoot, ".venv", "bin", "python")}" "${path.join(projectRoot, "scripts", "run_e2e_backend.py")}";`,
  "else",
  `  python3 "${path.join(projectRoot, "scripts", "run_e2e_backend.py")}";`,
  "fi",
].join(" ");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  use: {
    baseURL: frontendBaseUrl,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  webServer: [
    {
      command: backendCommand,
      url: `${backendBaseUrl}/health`,
      reuseExistingServer,
      env: {
        DATABASE_URL: `sqlite+pysqlite:///${backendDb}`,
        DATA_DIR: backendData,
        CORS_ORIGINS: `http://127.0.0.1:${frontendPort},http://localhost:${frontendPort}`,
        SCHOLARFLOW_OFFLINE_LLM: "1",
        SCHOLARFLOW_E2E_BACKEND_PORT: backendPort,
        AUTH_REQUIRED: authRequired ? "1" : "",
        AUTH_SECRET: authSecret,
        API_TOKEN: apiToken,
      },
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      cwd: frontendRoot,
      url: frontendBaseUrl,
      reuseExistingServer,
      env: {
        VITE_API_BASE_URL: backendBaseUrl,
      },
    },
  ],
});
