import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 120_000,
  expect: { timeout: 10_000 },
  workers: 1,
  use: { baseURL: "http://127.0.0.1:8321", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
    { name: "mobile", use: { viewport: { width: 390, height: 844 } } },
  ],
  webServer: {
    command: "bash ../scripts/e2e-server.sh",
    url: "http://127.0.0.1:8321/api/health",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
