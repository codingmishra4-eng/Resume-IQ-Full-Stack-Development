import { z } from "zod";
const exactOrigin = (local: boolean) =>
  z.string().refine((value) => {
    try {
      const url = new URL(value);
      return (
        value === url.origin &&
        !url.username &&
        !url.password &&
        (url.protocol === "https:" ||
          (local &&
            url.protocol === "http:" &&
            ["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)))
      );
    } catch {
      return false;
    }
  });
const schema = z.object({
  supabaseUrl: exactOrigin(false),
  publishableKey: z.string().regex(/^sb_publishable_[A-Za-z0-9_-]+$/),
  apiUrl: exactOrigin(true),
});
export type PublicConfig = z.infer<typeof schema>;
export function publicConfig(): PublicConfig | null {
  const result = schema.safeParse({
    supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL,
    publishableKey: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    apiUrl: process.env.NEXT_PUBLIC_API_URL,
  });
  return result.success ? result.data : null;
}
export function requireConfig(): PublicConfig {
  const config = publicConfig();
  if (!config)
    throw new Error(
      "This workspace is not configured. Contact the administrator.",
    );
  return config;
}
