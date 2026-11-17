import "server-only";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { authCookieOptions } from "@/lib/cookies";
import { publicConfig } from "@/lib/config";
export async function serverClient() {
  const config = publicConfig();
  if (!config) return null;
  const store = await cookies();
  return createServerClient(config.supabaseUrl, config.publishableKey, {
    cookieOptions: authCookieOptions(),
    cookies: {
      getAll: () => store.getAll(),
      setAll: (values) => {
        try {
          values.forEach(({ name, value, options }) =>
            store.set(name, value, options),
          );
        } catch {
          /* Server Components cannot write cookies; Proxy refreshes them. */
        }
      },
    },
  });
}
