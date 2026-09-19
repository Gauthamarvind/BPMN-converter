import { defineConfig, devices } from '@playwright/test';

/**
 * The smoke test drives the real app: the built SPA served by uvicorn on :8000, which is the
 * production single-server mode. `npm run build` must have run first (CI does it, and the
 * webServer command below does it locally).
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'python3 -m uvicorn backend.server:app --host 127.0.0.1 --port 8000',
    url: 'http://127.0.0.1:8000/api/health',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: { LLM_PROVIDER: 'mock' },
  },
});
