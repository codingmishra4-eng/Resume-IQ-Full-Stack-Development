import { NextRequest, NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase/server";
import { safeNext } from "@/lib/auth";
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const client = await serverClient();
  try {
    if (client) {
      const code = params.get("code");
      const hash = params.get("token_hash");
      const type = params.get("type");
      const result = code
        ? await client.auth.exchangeCodeForSession(code)
        : hash && (type === "signup" || type === "recovery")
          ? await client.auth.verifyOtp({ token_hash: hash, type })
          : null;
      if (result && !result.error) {
        const target =
          type === "recovery"
            ? "/reset-password"
            : safeNext(params.get("next"));
        const response = NextResponse.redirect(new URL(target, request.url));
        response.headers.set("Cache-Control", "private, no-store");
        return response;
      }
    }
  } catch {
    /* Never expose callback codes, tokens or provider errors. */
  }
  return NextResponse.redirect(new URL("/login?error=callback", request.url));
}
