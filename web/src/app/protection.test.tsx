import { beforeEach, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import ProtectedLayout from "./(app)/layout";
import { GET } from "./auth/callback/route";
import { account } from "@/test/fixtures";
const mocks = vi.hoisted(() => ({
  getUser: vi.fn(),
  exchangeCodeForSession: vi.fn(),
  verifyOtp: vi.fn(),
  configured: true,
}));
vi.mock("@/lib/supabase/server", () => ({
  serverClient: async () => (mocks.configured ? { auth: mocks } : null),
}));
vi.mock("next/navigation", () => ({
  redirect: (path: string) => {
    throw new Error("redirect:" + path);
  },
}));
vi.mock("@/components/providers", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("@/components/shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => children,
}));
beforeEach(() => {
  mocks.configured = true;
});
it("redirects protected routes when configuration/session is missing", async () => {
  mocks.configured = false;
  await expect(ProtectedLayout({ children: "private" })).rejects.toThrow(
    "redirect:/login",
  );
  mocks.configured = true;
  mocks.getUser.mockResolvedValue({ data: { user: null }, error: {} });
  await expect(ProtectedLayout({ children: "private" })).rejects.toThrow(
    "redirect:/login",
  );
});
it("does not treat a provider failure as an authenticated user", async () => {
  mocks.getUser.mockRejectedValue(new Error("unavailable"));
  await expect(ProtectedLayout({ children: "private" })).rejects.toThrow(
    "redirect:/login",
  );
});
it("renders protected content only for a server-validated identity", async () => {
  mocks.getUser.mockResolvedValue({
    data: { user: { id: account.id, email: account.email } },
    error: null,
  });
  expect(await ProtectedLayout({ children: "private" })).toBeTruthy();
});
it("exchanges a PKCE code and refuses an external next destination", async () => {
  mocks.exchangeCodeForSession.mockResolvedValue({ error: null });
  const response = await GET(
    new NextRequest(
      "http://localhost/auth/callback?code=synthetic&next=https://attacker.invalid",
    ),
  );
  expect(response.headers.get("location")).toBe("http://localhost/dashboard");
  expect(response.headers.get("cache-control")).toBe("private, no-store");
});
it("supports hashed recovery links and sanitizes callback errors", async () => {
  mocks.verifyOtp.mockResolvedValue({ error: null });
  const result = await GET(
    new NextRequest(
      "http://localhost/auth/callback?token_hash=synthetic&type=recovery",
    ),
  );
  expect(result.headers.get("location")).toBe(
    "http://localhost/reset-password",
  );
  mocks.exchangeCodeForSession.mockResolvedValue({
    error: { message: "private-token-error" },
  });
  const error = await GET(
    new NextRequest("http://localhost/auth/callback?code=invalid"),
  );
  expect(error.headers.get("location")).toBe(
    "http://localhost/login?error=callback",
  );
});
