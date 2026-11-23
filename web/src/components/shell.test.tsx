import { expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppShell } from "./shell";
import { ToastProvider } from "./ui";
import { account } from "@/test/fixtures";
vi.mock("next/navigation", () => ({ usePathname: () => "/documents" }));
const signOut = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));
vi.mock("./providers", () => ({ useAuth: () => ({ account, signOut }) }));
it("exposes horizontal navigation, active page and a working mobile disclosure", async () => {
  const user = userEvent.setup();
  render(
    <ToastProvider>
      <AppShell>
        <h1>Content</h1>
      </AppShell>
    </ToastProvider>,
  );
  expect(
    screen.getByRole("navigation", { name: "Main navigation" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await user.click(screen.getByRole("button", { name: "Open navigation" }));
  expect(
    screen.getByRole("button", { name: "Close navigation" }),
  ).toHaveAttribute("aria-expanded", "true");
  screen
    .getByRole("link", { name: "Job Match" })
    .addEventListener("click", (event) => event.preventDefault(), {
      once: true,
    });
  await user.click(screen.getByRole("link", { name: "Job Match" }));
  expect(
    screen.getByRole("button", { name: "Open navigation" }),
  ).toHaveAttribute("aria-expanded", "false");
  expect(screen.getByRole("link", { name: "Skip to content" })).toHaveAttribute(
    "href",
    "#main-content",
  );
});
it("signs out through the shared account controller", async () => {
  const user = userEvent.setup();
  render(
    <ToastProvider>
      <AppShell>Content</AppShell>
    </ToastProvider>,
  );
  await user.click(screen.getByRole("button", { name: "Sign out" }));
  expect(signOut).toHaveBeenCalledOnce();
});
