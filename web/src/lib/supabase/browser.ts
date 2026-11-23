"use client";
import { createBrowserClient } from "@supabase/ssr";
import { authCookieOptions } from "@/lib/cookies";
import { requireConfig } from "@/lib/config";
let client: ReturnType<typeof createBrowserClient> | undefined;
export function browserClient() {
  if (!client) {
    const config = requireConfig();
    client = createBrowserClient(config.supabaseUrl, config.publishableKey, {
      cookieOptions: authCookieOptions(),
    });
  }
  return client;
}
