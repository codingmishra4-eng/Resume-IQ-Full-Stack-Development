import { expect, test } from "@playwright/test";
test("public auth layout fits the viewport and has accessible inputs", async ({
  page,
}) => {
  await page.goto("/login");
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  await expect(page.getByLabel("Email address")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("link", { name: "Create an account" }).click();
  await expect(
    page.getByRole("heading", { name: "Make your next move." }),
  ).toBeVisible();
  await page.goto("/forgot-password");
  await expect(
    page.getByRole("button", { name: "Send reset link" }),
  ).toBeVisible();
});
test("unauthenticated protected routes redirect without rendering private content", async ({
  page,
}) => {
  for (const path of [
    "/dashboard",
    "/documents",
    "/analyzer",
    "/job-match",
    "/improve",
    "/builder",
    "/profile",
    "/upgrade",
  ]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/login$/);
    await expect(
      page.getByRole("heading", { name: "Welcome back." }),
    ).toBeVisible();
  }
});
