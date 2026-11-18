import { test, expect, type Page } from "@playwright/test";
import { createHash, randomUUID } from "node:crypto";
import { mkdirSync, writeFileSync, renameSync, unlinkSync } from "node:fs";
import { resolve } from "node:path";
const permitted = process.env.PHASE5_ALLOW_LIVE_WRITES === "true";
test.skip(
  !permitted,
  "PENDING: explicit staging write permission and dedicated accounts required.",
);
async function login(page: Page, letter: "A" | "B") {
  await page.goto("/login");
  await page
    .getByLabel("Email address")
    .fill(process.env[`PHASE2_TEST_USER_${letter}_EMAIL`]!);
  await page
    .getByLabel("Password", { exact: true })
    .fill(process.env[`PHASE2_TEST_USER_${letter}_PASSWORD`]!);
  await page.getByRole("button", { name: "Sign in to your workspace" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
}
function exactOrigin(value: string, local = false) {
  const url = new URL(value);
  if (
    value !== url.origin ||
    !(
      url.protocol === "https:" ||
      (local &&
        url.protocol === "http:" &&
        ["localhost", "127.0.0.1"].includes(url.hostname))
    )
  )
    throw new Error("Invalid staging origin.");
  return value;
}
test("synthetic full workspace, isolation, account switching and session expiration", async ({
  page,
  context,
  request,
}) => {
  test.setTimeout(240000);
  for (const key of [
    "PHASE2_TEST_USER_A_EMAIL",
    "PHASE2_TEST_USER_A_PASSWORD",
    "PHASE2_TEST_USER_B_EMAIL",
    "PHASE2_TEST_USER_B_PASSWORD",
    "PHASE5_API_URL",
    "PHASE5_BROWSER_BASE_URL",
    "NEXT_PUBLIC_SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
  ])
    if (!process.env[key])
      throw new Error("Dedicated staging settings missing.");
  const api = exactOrigin(process.env.PHASE5_API_URL!, true),
    supabase = exactOrigin(process.env.NEXT_PUBLIC_SUPABASE_URL!);
  exactOrigin(process.env.PHASE5_BROWSER_BASE_URL!, true);
  if (
    process.env.PHASE2_TEST_USER_A_EMAIL ===
    process.env.PHASE2_TEST_USER_B_EMAIL
  )
    throw new Error("Distinct test accounts required.");
  // An actual DOCX is supplied by the safe Python generator command in the runbook.
  // Only that generated synthetic file is allowed (hash verified below).
  const { readFileSync } = await import("node:fs");
  const generated = JSON.parse(
    readFileSync(resolve("../work/phase5-browser-document.json"), "utf8"),
  ) as { bytes: string; sha256: string };
  const bytes = Buffer.from(generated.bytes, "base64");
  if (createHash("sha256").update(bytes).digest("hex") !== generated.sha256)
    throw new Error("Synthetic fixture hash mismatch.");
  const journal = resolve(`../work/phase5-browser-${randomUUID()}.json`);
  mkdirSync(resolve("../work"), { recursive: true });
  const resources: { resumes: string[]; drafts: string[]; uncertain: boolean } =
    { resumes: [], drafts: [], uncertain: false };
  const save = () => {
    const tmp = journal + ".tmp";
    writeFileSync(
      tmp,
      JSON.stringify({
        version: 1,
        kind: "phase5-browser",
        ...resources,
        document_sha256: generated.sha256,
      }),
      { mode: 0o600 },
    );
    renameSync(tmp, journal);
  };
  let token = "";
  let clean = true;
  const browserTokens = new Set<string>();
  page.on("response", async (response) => {
    if (response.url().startsWith(supabase + "/auth/v1/token")) {
      try {
        const data = await response.json();
        if (data.access_token) browserTokens.add(data.access_token);
      } catch {
        /* no logging */
      }
    }
  });
  try {
    const auth = await request.post(
      supabase + "/auth/v1/token?grant_type=password",
      {
        headers: { apikey: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY! },
        data: {
          email: process.env.PHASE2_TEST_USER_A_EMAIL,
          password: process.env.PHASE2_TEST_USER_A_PASSWORD,
        },
      },
    );
    expect(auth.ok()).toBeTruthy();
    token = (await auth.json()).access_token;
    await login(page, "A");
    // Simulate a recoverable backend outage and loading state without changing infrastructure.
    await page.route(api + "/api/v1/resumes?*", async (route) => {
      await new Promise((done) => setTimeout(done, 250));
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: '{"code":"cloud_unavailable"}',
      });
    });
    await page.goto("/documents");
    await expect(
      page.getByText(/temporarily unavailable/).first(),
    ).toBeVisible();
    await page.unroute(api + "/api/v1/resumes?*");
    await page.goto("/analyzer");
    resources.uncertain = true;
    save();
    const uploaded = page.waitForResponse(
      (response) =>
        response.url() === api + "/api/v1/resumes" &&
        response.request().method() === "POST",
    );
    await page
      .locator("input[type=file]")
      .setInputFiles({
        name: "synthetic.docx",
        mimeType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        buffer: bytes,
      });
    await page
      .getByRole("button", { name: "Upload resume", exact: true })
      .click();
    const upload = await uploaded;
    expect(upload.status()).toBe(201);
    const resume = (await upload.json()).id;
    resources.resumes.push(resume);
    resources.uncertain = false;
    save();
    await page
      .getByRole("button", { name: "Run analysis", exact: true })
      .click();
    await expect(page.getByText(/Estimated ATS score:/)).toBeVisible({
      timeout: 90000,
    });
    expect(
      await page
        .getByRole("navigation", { name: "Report sections" })
        .locator("a")
        .count(),
    ).toBe(12);
    for (const name of [
      "Resume overview",
      "Estimated ATS parseability",
      "Quantified impact",
      "Repeated words",
      "Spelling and grammar",
      "Essential sections",
      "Contact information",
      "ATS formatting",
      "Job description match",
      "Skill gaps",
      "Templates",
      "Recommendations",
    ])
      await expect(
        page.getByRole("heading", { name, exact: true }),
      ).toBeVisible();
    await page.reload();
    await expect(page.getByText(/Estimated ATS score:/)).toBeVisible();
    await page.goto("/job-match");
    await page.getByLabel("Choose your resume").selectOption(resume);
    await page
      .getByLabel("Job description", { exact: true })
      .fill(
        "Python SQL Docker engineer for synthetic testing and software delivery with real projects.",
      );
    await page.getByRole("button", { name: "Compare resumes" }).click();
    await expect(page.getByRole("meter")).toBeVisible({ timeout: 90000 });
    await page.goto("/improve");
    await page.getByLabel("Choose your resume").selectOption(resume);
    await page
      .getByRole("button", { name: "Keyword guidance", exact: true })
      .click();
    await page
      .getByLabel("Job description (required)")
      .fill(
        "Python SQL Docker engineer for synthetic testing and software delivery with real projects.",
      );
    await page.getByRole("button", { name: "Suggest improvements" }).click();
    await expect(
      page.getByText("Rule-based", { exact: true }).first(),
    ).toBeVisible({ timeout: 90000 });
    await page.goto("/builder");
    await page
      .getByLabel("Full name", { exact: true })
      .fill("Synthetic Browser Candidate");
    resources.uncertain = true;
    save();
    const saved = page.waitForResponse(
      (response) =>
        response.url() === api + "/api/v1/builder/drafts" &&
        response.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Save private draft", exact: true })
      .click();
    const response = await saved;
    expect(response.status()).toBe(201);
    const draft = (await response.json()).id;
    resources.drafts.push(draft);
    resources.uncertain = false;
    save();
    for (const format of ["PDF", "DOCX"]) {
      const download = page.waitForEvent("download");
      await page
        .getByRole("button", { name: `Save and download ${format}` })
        .click();
      const file = await download;
      expect(file.suggestedFilename()).toBe("resume." + format.toLowerCase());
      await file.delete();
    }
    await page.goto("/documents");
    await expect(
      page.getByText("resume.docx", { exact: true }).first(),
    ).toBeVisible();
    await page.goto("/documents");
    await page
      .getByRole("button", { name: "Activity history", exact: true })
      .click();
    await expect(
      page.getByText("Analysis generated", { exact: true }).first(),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    await page.goto("/profile");
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(page).toHaveURL(/\/login/);
    await login(page, "B");
    await page.goto("/builder");
    await expect(page.getByLabel("Full name", { exact: true })).toHaveValue("");
    const authB = await request.post(
      supabase + "/auth/v1/token?grant_type=password",
      {
        headers: { apikey: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY! },
        data: {
          email: process.env.PHASE2_TEST_USER_B_EMAIL,
          password: process.env.PHASE2_TEST_USER_B_PASSWORD,
        },
      },
    );
    expect(authB.ok()).toBeTruthy();
    const tokenB = (await authB.json()).access_token;
    try {
      for (const path of [`/resumes/${resume}`, `/builder/drafts/${draft}`])
        expect(
          (
            await request.get(api + "/api/v1" + path, {
              headers: { Authorization: "Bearer " + tokenB },
            })
          ).status(),
        ).toBe(404);
      for (const format of ["pdf", "docx"])
        expect(
          (
            await request.post(
              api + `/api/v1/builder/drafts/${draft}/exports/${format}`,
              { headers: { Authorization: "Bearer " + tokenB } },
            )
          ).status(),
        ).toBe(404);
    } finally {
      await request.post(supabase + "/auth/v1/logout?scope=local", {
        headers: {
          apikey: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
          Authorization: "Bearer " + tokenB,
        },
      });
    }
    await context.clearCookies();
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  } finally {
    if (token) {
      for (const id of resources.drafts) {
        try {
          if (
            ![204, 404].includes(
              (
                await request.delete(api + "/api/v1/builder/drafts/" + id, {
                  headers: { Authorization: "Bearer " + token },
                })
              ).status(),
            )
          )
            clean = false;
        } catch {
          clean = false;
        }
      }
      for (const id of resources.resumes) {
        try {
          if (
            ![204, 404].includes(
              (
                await request.delete(api + "/api/v1/resumes/" + id, {
                  headers: { Authorization: "Bearer " + token },
                })
              ).status(),
            )
          )
            clean = false;
        } catch {
          clean = false;
        }
      }
      await request.post(supabase + "/auth/v1/logout?scope=local", {
        headers: {
          apikey: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
          Authorization: "Bearer " + token,
        },
      });
    }
    for (const browserToken of browserTokens) {
      try {
        const logout = await request.post(
          supabase + "/auth/v1/logout?scope=local",
          {
            headers: {
              apikey: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!,
              Authorization: "Bearer " + browserToken,
            },
          },
        );
        if (![200, 204, 401].includes(logout.status())) clean = false;
      } catch {
        clean = false;
      }
    }
    if (clean && !resources.uncertain) {
      try {
        unlinkSync(journal);
      } catch {
        /* no resources created */
      }
    } else {
      save();
      throw new Error(
        "Cleanup incomplete; retain the local identifier journal for operator review.",
      );
    }
  }
});
