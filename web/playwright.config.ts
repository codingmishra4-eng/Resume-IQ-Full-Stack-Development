import { defineConfig, devices } from "@playwright/test";
// Connect to an explicitly started local server. Never auto-start against production.
export default defineConfig({
  testDir: "./e2e",
  testIgnore: "live.spec.ts",
  fullyParallel: false,
  retries: 0,
  use: {
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    },
    baseURL: process.env.PHASE3_BROWSER_BASE_URL ?? "http://127.0.0.1:3000",
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
});
