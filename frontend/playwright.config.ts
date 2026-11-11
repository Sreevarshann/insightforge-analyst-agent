import { defineConfig, devices } from "@playwright/test";

/**
 * E2E runs an isolated stack on ports 8191 (API) / 3191 (web) with the deterministic
 * fixture provider and freshly seeded SYNTHETIC demo data, so it never touches the
 * development database or needs a local LLM. Screenshot capture (`screenshots.spec.ts`)
 * instead targets an already running dev stack (SCREENSHOT_BASE_URL) with a real model.
 */
const E2E = !process.env.SCREENSHOT_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  testMatch: E2E ? /.*\.e2e\.ts/ : /screenshots\.spec\.ts/,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.SCREENSHOT_BASE_URL ?? "http://127.0.0.1:3191",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } }],
  webServer: E2E
    ? [
        {
          command: "cd ../backend && rm -rf var-e2e && INSIGHTFORGE_DATA_DIR=var-e2e uv run python -m insightforge.demo.seed && INSIGHTFORGE_DATA_DIR=var-e2e INSIGHTFORGE_LLM_PROVIDER=fixture INSIGHTFORGE_CORS_ORIGINS='[\"http://127.0.0.1:3191\"]' uv run uvicorn insightforge.main:app --host 127.0.0.1 --port 8191",
          url: "http://127.0.0.1:8191/api/health",
          reuseExistingServer: false,
          timeout: 180_000,
        },
        {
          command: "INSIGHTFORGE_API_ORIGIN=http://127.0.0.1:8191 npm run build && INSIGHTFORGE_API_ORIGIN=http://127.0.0.1:8191 npx next start --port 3191 --hostname 127.0.0.1",
          url: "http://127.0.0.1:3191",
          reuseExistingServer: false,
          timeout: 300_000,
        },
      ]
    : undefined,
});
