/**
 * Fail before Next.js inlines public values into JavaScript. Runtime validation
 * alone cannot prevent a mistakenly supplied secret from entering the bundle.
 * @param {Record<string, string | undefined>} env
 */
export function assertPublicEnvironment(env) {
  for (const [name, value] of Object.entries(env)) {
    if (!name.startsWith("NEXT_PUBLIC_") || !value) continue;
    if (
      /SECRET|SERVICE_ROLE|DATABASE|PASSWORD|ACCESS_TOKEN|REFRESH_TOKEN|OPENAI/.test(
        name,
      ) ||
      /^(sb_secret_|sk-|postgres(?:ql)?(?:\+psycopg)?:\/\/)/.test(value)
    ) {
      throw new Error(
        "Backend secrets are not permitted in public environment variables.",
      );
    }
  }
  const key = env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (key && !/^sb_publishable_[A-Za-z0-9_-]+$/.test(key)) {
    throw new Error(
      "The public Supabase key must be a modern publishable key.",
    );
  }
  for (const name of ["NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_API_URL"]) {
    const value = env[name];
    if (!value) continue; // An unconfigured installation can render its setup notice.
    let valid = false;
    try {
      const url = new URL(value);
      valid =
        value === url.origin &&
        !url.username &&
        !url.password &&
        (url.protocol === "https:" ||
          (name === "NEXT_PUBLIC_API_URL" &&
            url.protocol === "http:" &&
            ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)));
    } catch {
      /* Never include configuration values in the error. */
    }
    if (!valid)
      throw new Error(
        "Public service URLs must be exact secure origins without credentials.",
      );
  }
}
