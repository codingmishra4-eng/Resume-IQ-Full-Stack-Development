import { test, expect } from "@playwright/test";
import { createServer, type ViteDevServer } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Isolated component harness: no Supabase config, auth client, backend or live data.
const web = path.resolve(__dirname, "..");
const fixture = path.join(web, "e2e/report-fixture");
let server: ViteDevServer;
let base: string;
test.beforeAll(async () => {
  server = await createServer({
    configFile: false,
    root: fixture,
    logLevel: "error",
    envFile: false,
    plugins: [react()],
    resolve: {
      alias: [
        { find: "@", replacement: path.join(web, "src") },
        {
          find: /^\.\/providers$/,
          replacement: path.join(fixture, "providers.ts"),
        },
        { find: "next/link", replacement: path.join(fixture, "next-link.tsx") },
        {
          find: "next/navigation",
          replacement: path.join(fixture, "next-navigation.ts"),
        },
      ],
    },
    server: { host: "127.0.0.1", port: 0, fs: { allow: [web] } },
  });
  await server.listen();
  const address = server.httpServer!.address();
  if (!address || typeof address === "string")
    throw new Error("Local UI server unavailable");
  base = `http://127.0.0.1:${address.port}`;
});
test.afterAll(async () => {
  await server?.close();
});
test.beforeEach(async ({ page }) => {
  // A fixture accidentally adding a remote request must fail, not reach a service.
  await page.route("**/*", (route) => {
    const url = new URL(route.request().url());
    return url.hostname === "127.0.0.1" ? route.continue() : route.abort();
  });
});
for (const width of [360, 390, 400, 768, 1024, 1440]) {
  test(`report is readable and navigable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(base);
    await expect(
      page.getByRole("heading", { name: "Resume overview", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("meter", { name: "Estimated ATS score", exact: true }),
    ).toHaveAttribute("aria-valuenow", "72");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await expect(page.locator(".ar-section[open]")).toHaveCount(3);
    const section = page.locator("#report-repetition");
    await expect(section).not.toHaveAttribute("open", "");
    await section.locator(":scope > summary").focus();
    await page.keyboard.press("Enter");
    await expect(section).toHaveAttribute("open", "");
    await page.keyboard.press("Space");
    await expect(section).not.toHaveAttribute("open", "");
    const link = page.locator('.ar-section-nav a[href="#report-repetition"]');
    if (width <= 680) {
      await expect(
        page.getByRole("navigation", { name: "Report sections" }),
      ).toBeHidden();
      const select = page.getByLabel("Jump to report section");
      await expect(select.locator("option")).toHaveCount(12);
      await select.selectOption("repetition");
      await expect(section).not.toHaveAttribute("open", "");
      await select.focus();
      await page.keyboard.press("Tab");
      await expect(
        page.getByRole("button", { name: "Go to selected report section" }),
      ).toBeFocused();
      await page.keyboard.press("Enter");
    } else {
      await expect(page.getByLabel("Jump to report section")).toBeHidden();
      await link.focus();
      await page.keyboard.press("Enter");
    }
    await expect(section).toHaveAttribute("open", "");
    await expect(section.locator(":scope > summary")).toBeFocused();
    await expect(
      page.getByRole("row", { name: "testing 4", exact: true }),
    ).toBeVisible();
    // Anchor targets must clear the real sticky application header.
    await expect
      .poll(async () => (await section.boundingBox())!.y)
      .toBeLessThan(200);
    await expect(link).toHaveAttribute("aria-current", "location");
    const target = await section.boundingBox();
    const header = await page.locator(".topbar").boundingBox();
    expect(target!.y).toBeGreaterThanOrEqual(header!.y + header!.height);
  });
}
test("loading, error, initial and no-findings states are honest", async ({
  page,
}) => {
  await page.goto(`${base}?state=loading`);
  await expect(page.getByRole("status")).toContainText("Loading your report");
  await expect(page.getByRole("meter")).toHaveCount(0);
  await page.goto(`${base}?state=error`);
  await expect(page.getByRole("alert")).toContainText(
    "Synthetic report unavailable",
  );
  await page.getByRole("button", { name: "Run analysis" }).click();
  await expect(
    page.getByRole("meter", { name: "Estimated ATS score", exact: true }),
  ).toBeVisible();
  await page.goto(`${base}?state=initial`);
  await expect(
    page.getByRole("heading", { name: "Ready for a closer look?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Run analysis" }).click();
  await expect(
    page.getByRole("meter", { name: "Estimated ATS score", exact: true }),
  ).toBeVisible();
  await page.goto(`${base}?state=empty`);
  await expect(page.locator(".ar-section[open]")).toHaveCount(1);
  await page.locator("#report-repetition > summary").click();
  await page.locator("#report-grammar > summary").click();
  await expect(
    page.getByText(
      "No repeated terms were flagged by the word-frequency check.",
    ),
  ).toBeVisible();
  await expect(
    page.getByText("No spelling issues flagged by these checks."),
  ).toBeVisible();
  await expect(
    page.getByRole("meter", { name: "Bullets containing quantified evidence" }),
  ).toHaveCount(0);
});
test("long findings, upload controls and reduced motion fit a small screen", async ({
  page,
}) => {
  await page.setViewportSize({ width: 360, height: 900 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(`${base}?state=long`);
  await expect(page.getByText(/SyntheticLongEvidence/)).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.locator(".ar-upload-another > summary").click();
  await expect(
    page.getByRole("button", { name: "Upload resume", exact: true }),
  ).toBeVisible();
  expect(
    (await page
      .getByRole("button", { name: "Upload resume", exact: true })
      .boundingBox())!.height,
  ).toBeGreaterThanOrEqual(44);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.goto(`${base}?state=upload`);
  await expect(
    page.getByRole("heading", { name: "Start with your document" }),
  ).toBeVisible();
});

test("desktop polish keeps secondary text readable, the score restrained and empty rows compact", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto(`${base}?state=empty`);
  await expect(page.locator(".ar-score strong")).toHaveText("72.0");
  const metrics = await page.evaluate(() => {
    const size = (selector: string) =>
      parseFloat(getComputedStyle(document.querySelector(selector)!).fontSize);
    return {
      body: size(".ar-overview-intro"),
      note: size(".ar-sidebar-score .ar-note"),
      label: size("label[for=analysis-resume]"),
      score: size(".ar-score strong"),
      ring: document.querySelector(".ar-score")!.getBoundingClientRect().width,
    };
  });
  expect(metrics.body).toBeGreaterThanOrEqual(15);
  expect(metrics.note).toBeGreaterThanOrEqual(14);
  expect(metrics.label).toBeGreaterThanOrEqual(14);
  expect(metrics.score).toBeGreaterThanOrEqual(38);
  expect(metrics.ring).toBeLessThanOrEqual(160);
  await page.locator("#report-grammar > summary").click();
  for (const row of await page.locator(".ar-writing-group-empty").all()) {
    expect((await row.boundingBox())!.height).toBeLessThan(100);
  }
});

for (const width of [360, 390, 400]) {
  test(`mobile controls, long evidence and recommendations fit at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`${base}?state=long`);
    await expect(page.getByText(/SyntheticLongEvidence/)).toBeVisible();
    await expect(page.getByText(/SyntheticLongRecommendation/)).toBeVisible();
    const sizes = await page.evaluate(() => {
      const select = document.querySelector("#report-section-destination")!;
      const score = document.querySelector(".ar-sidebar-score")!;
      return {
        font: parseFloat(getComputedStyle(select).fontSize),
        line: parseFloat(
          getComputedStyle(document.querySelector(".ar-edit")!).lineHeight,
        ),
        score: score.getBoundingClientRect().height,
      };
    });
    expect(sizes.font).toBeGreaterThanOrEqual(16);
    expect(sizes.line).toBeGreaterThanOrEqual(24);
    expect(sizes.score).toBeLessThan(160);
    for (const selector of [
      ".ar-mobile-nav button",
      "#report-section-destination",
      ".ar-run-button",
      "#analysis-history",
      ".ar-job-context > summary",
    ]) {
      const box = await page.locator(selector).boundingBox();
      expect(box!.height).toBeGreaterThanOrEqual(44);
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });
}
