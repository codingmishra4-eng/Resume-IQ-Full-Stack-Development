import { defineConfig, devices } from "@playwright/test";
const enabled = process.env.PHASE5_ALLOW_LIVE_WRITES === "true";
if (
  enabled &&
  (!process.env.PHASE5_BROWSER_BASE_URL || !process.env.PHASE5_API_URL)
)
  throw new Error("Explicit staging browser and API origins required.");
export default defineConfig({
  testDir: "./e2e",
  testMatch: "live.spec.ts",
  workers: 1,
  retries: 0,
  timeout: 240000,
  reporter: [["./e2e/safe-reporter.ts"]],
  outputDir: "../work/phase5-browser",
  use: {
    baseURL: process.env.PHASE5_BROWSER_BASE_URL ?? "http://127.0.0.1:3000",
    trace: "off",
    screenshot: "off",
    video: "off",
    actionTimeout: 20000,
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    },
  },
  projects: [
    { name: "desktop-live", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-live", use: { ...devices["Pixel 7"] } },
  ],
});
