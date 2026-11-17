import { beforeEach, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AuthForm } from "./auth-form";
const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  refresh: vi.fn(),
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  resetPasswordForEmail: vi.fn(),
  getUser: vi.fn(),
  updateUser: vi.fn(),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace, refresh: mocks.refresh }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/supabase/browser", () => ({
  browserClient: () => ({ auth: mocks }),
}));
vi.mock("@/lib/config", () => ({ publicConfig: () => ({}) }));
beforeEach(() => {
  mocks.signInWithPassword.mockResolvedValue({
    data: { session: {} },
    error: null,
  });
  mocks.signUp.mockResolvedValue({ data: { session: null }, error: null });
  mocks.resetPasswordForEmail.mockResolvedValue({ error: null });
});
it("signs in through Supabase and refreshes the protected route", async () => {
  const user = userEvent.setup();
  render(<AuthForm mode="login" />);
  await user.type(
    screen.getByLabelText("Email address"),
    "synthetic@example.invalid",
  );
  await user.type(
    screen.getByLabelText("Password", { exact: true }),
    "test-password",
  );
  await user.click(
    screen.getByRole("button", { name: "Sign in to your workspace" }),
  );
  await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/dashboard"));
  expect(mocks.signInWithPassword).toHaveBeenCalledWith({
    email: "synthetic@example.invalid",
    password: "test-password",
  });
  expect(mocks.refresh).toHaveBeenCalled();
});
it("sanitizes login failure instead of displaying provider errors", async () => {
  mocks.signInWithPassword.mockResolvedValue({
    data: { session: null },
    error: { message: "do-not-echo-provider-value" },
  });
  const user = userEvent.setup();
  render(<AuthForm mode="login" />);
  await user.type(
    screen.getByLabelText("Email address"),
    "synthetic@example.invalid",
  );
  await user.type(
    screen.getByLabelText("Password", { exact: true }),
    "invalid",
  );
  await user.click(
    screen.getByRole("button", { name: "Sign in to your workspace" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Unable to sign in",
  );
  expect(screen.queryByText(/do-not-echo/)).not.toBeInTheDocument();
});
it("shows email confirmation when signup creates no session", async () => {
  const user = userEvent.setup();
  render(<AuthForm mode="signup" />);
  await user.type(
    screen.getByLabelText("Email address"),
    "synthetic@example.invalid",
  );
  await user.type(
    screen.getByLabelText("Password", { exact: true }),
    "new-test-password",
  );
  await user.type(
    screen.getByLabelText("Confirm password"),
    "new-test-password",
  );
  await user.click(screen.getByRole("button", { name: "Create your account" }));
  expect(await screen.findByText(/Check your inbox/)).toBeInTheDocument();
  expect(mocks.signUp).toHaveBeenCalled();
});
it("requests a reset link without revealing account existence", async () => {
  const user = userEvent.setup();
  render(<AuthForm mode="forgot" />);
  await user.type(
    screen.getByLabelText("Email address"),
    "synthetic@example.invalid",
  );
  await user.click(screen.getByRole("button", { name: "Send reset link" }));
  expect(await screen.findByText(/If an account exists/)).toBeInTheDocument();
  expect(mocks.resetPasswordForEmail.mock.calls[0][1].redirectTo).toContain(
    "/auth/callback?next=%2Freset-password",
  );
});
it("rejects reset submission without a valid user session", async () => {
  mocks.getUser.mockResolvedValue({ data: { user: null }, error: {} });
  const user = userEvent.setup();
  render(<AuthForm mode="reset" />);
  await user.type(screen.getByLabelText("New password"), "new-test-password");
  await user.type(
    screen.getByLabelText("Confirm password"),
    "new-test-password",
  );
  await user.click(screen.getByRole("button", { name: "Save new password" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("expired");
  expect(mocks.updateUser).not.toHaveBeenCalled();
});
it("validates forms before making authentication requests", async () => {
  const user = userEvent.setup();
  render(<AuthForm mode="login" />);
  await user.click(
    screen.getByRole("button", { name: "Sign in to your workspace" }),
  );
  expect(
    await screen.findByText("Enter a valid email address."),
  ).toBeInTheDocument();
  expect(mocks.signInWithPassword).not.toHaveBeenCalled();
});
it("updates a password only after validating the signed-in user", async () => {
  mocks.getUser.mockResolvedValue({
    data: { user: { id: "synthetic" } },
    error: null,
  });
  mocks.updateUser.mockResolvedValue({ error: null });
  const user = userEvent.setup();
  render(<AuthForm mode="reset" />);
  await user.type(screen.getByLabelText("New password"), "new-test-password");
  await user.type(
    screen.getByLabelText("Confirm password"),
    "new-test-password",
  );
  await user.click(screen.getByRole("button", { name: "Save new password" }));
  expect(
    await screen.findByText(
      "Your password has been updated. You can return to your workspace.",
    ),
  ).toBeInTheDocument();
  expect(mocks.updateUser).toHaveBeenCalledWith({
    password: "new-test-password",
  });
});
it("shows a connection-safe reset request error without provider details", async () => {
  mocks.resetPasswordForEmail.mockResolvedValue({
    error: { code: "unexpected_failure", message: "private-provider-error" },
  });
  const user = userEvent.setup();
  render(<AuthForm mode="forgot" />);
  await user.type(
    screen.getByLabelText("Email address"),
    "synthetic@example.invalid",
  );
  await user.click(screen.getByRole("button", { name: "Send reset link" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Could not request a reset link",
  );
  expect(screen.queryByText(/private-provider-error/)).not.toBeInTheDocument();
});
it("never permits native GET submission before hydration", async () => {
  const { renderToString } = await import("react-dom/server");
  const html = renderToString(<AuthForm mode="login" />);
  expect(html).toContain('method="post"');
  expect(html).toContain('disabled=""');
  expect(html).toContain("JavaScript is required");
});
