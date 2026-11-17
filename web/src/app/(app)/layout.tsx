import { redirect } from "next/navigation";
import { serverClient } from "@/lib/supabase/server";
import { accountFromUser } from "@/lib/auth";
import { AuthProvider } from "@/components/providers";
import { AppShell } from "@/components/shell";
export const dynamic = "force-dynamic";
export default async function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const client = await serverClient();
  let account = null;
  if (client) {
    try {
      const { data, error } = await client.auth.getUser();
      if (!error && data.user) account = accountFromUser(data.user);
    } catch {
      /* No authenticated content on an unavailable/invalid session. */
    }
  }
  if (!account) redirect("/login");
  return (
    <AuthProvider initialAccount={account}>
      <AppShell>{children}</AppShell>
    </AuthProvider>
  );
}
