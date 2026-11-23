export function authCookieOptions(
  production = process.env.NODE_ENV === "production",
) {
  // The browser SDK needs readable session cookies; require HTTPS in production.
  return { path: "/", sameSite: "lax" as const, secure: production };
}
