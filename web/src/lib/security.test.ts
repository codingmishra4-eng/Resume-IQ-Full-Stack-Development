import { afterEach, describe, expect, it, vi } from "vitest";
import { publicConfig } from "./config";
import { safeNext } from "./auth";
import { authSchema } from "@/components/auth-form";
afterEach(() => vi.unstubAllEnvs());
describe("public configuration", () => {
  it("accepts publishable configuration and rejects backend keys", () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://synthetic.supabase.co");
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://127.0.0.1:8000");
    vi.stubEnv(
      "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
      "sb_publishable_unit_test_only",
    );
    expect(publicConfig()).not.toBeNull();
    vi.stubEnv(
      "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
      "sb_secret_unit_test_only",
    );
    expect(publicConfig()).toBeNull();
  });
  it("fails closed without valid environment values", () => {
    vi.stubEnv(
      "NEXT_PUBLIC_SUPABASE_URL",
      "https://user:password@invalid.example",
    );
    expect(publicConfig()).toBeNull();
  });
});
describe("safe redirects", () => {
  it.each([
    "https://attacker.invalid",
    "//attacker.invalid",
    "/\\attacker.invalid",
    "/dashboard/../../evil",
    "/dashboard?next=https://attacker.invalid",
    "/auth/callback",
    "javascript:alert(1)",
  ])("rejects an unsafe callback destination: %s", (value) =>
    expect(safeNext(value)).toBe("/dashboard"),
  );
  it("allows explicit application routes and reset-password", () => {
    expect(safeNext("/documents")).toBe("/documents");
    expect(safeNext("/reset-password")).toBe("/reset-password");
  });
});
describe("auth input schemas", () => {
  it("allows existing login passwords without imposing new signup policy", () => {
    expect(
      authSchema("login").safeParse({
        email: "synthetic@example.invalid",
        password: "old",
        confirm: "",
      }).success,
    ).toBe(true);
  });
  it("requires strong matching new passwords", () => {
    expect(
      authSchema("signup").safeParse({
        email: "synthetic@example.invalid",
        password: "short",
        confirm: "short",
      }).success,
    ).toBe(false);
    expect(
      authSchema("reset").safeParse({
        email: "",
        password: "a-secure-test-password",
        confirm: "different",
      }).success,
    ).toBe(false);
  });
});
describe("pre-bundle environment guard", () => {
  it.each([
    { NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_secret_unit_test_only" },
    { NEXT_PUBLIC_SUPABASE_SECRET_KEY: "sb_secret_unit_test_only" },
    { NEXT_PUBLIC_API_URL: "https://user:password@example.invalid" },
  ])(
    "blocks unsafe public settings before they reach client JavaScript",
    async (env) => {
      const { assertPublicEnvironment } = await import("../../public-env.mjs");
      expect(() => assertPublicEnvironment(env)).toThrow();
      try {
        assertPublicEnvironment(env);
      } catch (error) {
        expect(String(error)).not.toContain("sb_secret_unit_test_only");
        expect(String(error)).not.toContain("user:password");
      }
    },
  );
});
describe("session cookie policy", () => {
  it("requires secure transport for production cookies", async () => {
    const { authCookieOptions } = await import("./cookies");
    expect(authCookieOptions(true)).toEqual({
      path: "/",
      sameSite: "lax",
      secure: true,
    });
  });
  it("allows explicit loopback development while keeping SameSite protection", async () => {
    const { authCookieOptions } = await import("./cookies");
    expect(authCookieOptions(false)).toEqual({
      path: "/",
      sameSite: "lax",
      secure: false,
    });
  });
});
