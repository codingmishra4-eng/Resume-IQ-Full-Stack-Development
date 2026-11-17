export const appPaths = [
  "/dashboard",
  "/analyzer",
  "/job-match",
  "/improve",
  "/builder",
  "/documents",
  "/upgrade",
  "/profile",
];
export function safeNext(value: string | null | undefined): string {
  if (!value || value.includes("\\") || /[\u0000-\u0020]/.test(value))
    return "/dashboard";
  return [...appPaths, "/reset-password"].includes(value) ||
    /^\/documents\/[0-9a-f-]{36}$/i.test(value)
    ? value
    : "/dashboard";
}
export function callbackUrl(origin: string, next = "/dashboard") {
  const url = new URL("/auth/callback", origin);
  url.searchParams.set("next", safeNext(next));
  return url.toString();
}
export type Account = {
  id: string;
  email: string | null;
  createdAt: string | null;
};
export function accountFromUser(user: {
  id: string;
  email?: string;
  created_at?: string;
}): Account {
  return {
    id: user.id,
    email: user.email ?? null,
    createdAt: user.created_at ?? null,
  };
}
