"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { AuthChangeEvent, Session } from "@supabase/supabase-js";
import { useRouter } from "next/navigation";
import { accountFromUser, type Account } from "@/lib/auth";
import { browserClient } from "@/lib/supabase/browser";
import { requireConfig } from "@/lib/config";
import {
  ApiClient,
  type StoredResume,
  type Analysis,
  type HistoryEntry,
} from "@/lib/api";
import { safeMessage } from "@/lib/format";
import { ToastProvider, Skeleton } from "./ui";
type Auth = { account: Account; api: ApiClient; signOut: () => Promise<void> };
const AuthContext = createContext<Auth | null>(null);
export function AuthProvider({
  initialAccount,
  children,
}: {
  initialAccount: Account;
  children: ReactNode;
}) {
  const [account, setAccount] = useState<Account | null>(initialAccount);
  const router = useRouter();
  const api = useMemo(
    () =>
      new ApiClient(requireConfig(), {
        getToken: async (refresh) => {
          const client = browserClient();
          const { data, error } = refresh
            ? await client.auth.refreshSession()
            : await client.auth.getSession();
          return error ? null : (data.session?.access_token ?? null);
        },
        onUnauthorized: () => {
          setAccount(null);
          router.replace("/login?reason=expired");
          router.refresh();
        },
      }),
    [router],
  );
  useEffect(() => {
    const { data } = browserClient().auth.onAuthStateChange(
      (event: AuthChangeEvent, session: Session | null) => {
        setAccount(session?.user ? accountFromUser(session.user) : null);
        if (event === "SIGNED_OUT") {
          router.replace("/login");
          router.refresh();
        }
      },
    );
    return () => data.subscription.unsubscribe();
  }, [router]);
  const signOut = useCallback(async () => {
    const { error } = await browserClient().auth.signOut({ scope: "local" });
    if (error) throw new Error("Sign-out could not be completed.");
    setAccount(null);
    router.replace("/login");
    router.refresh();
  }, [router]);
  if (!account)
    return (
      <main className="auth-transition">
        <Skeleton rows={2} />
        <p>Checking your session…</p>
      </main>
    );
  return (
    <AuthContext.Provider value={{ account, api, signOut }}>
      <ToastProvider>
        <WorkspaceProvider key={account.id}>{children}</WorkspaceProvider>
      </ToastProvider>
    </AuthContext.Provider>
  );
}
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("Account context unavailable.");
  return value;
}
export type Resource<T> = { data: T[] | null; error: string | null };
type Workspace = {
  resumes: Resource<StoredResume>;
  analyses: Resource<Analysis>;
  history: Resource<HistoryEntry>;
  loading: boolean;
  refresh: () => void;
};
const WorkspaceContext = createContext<Workspace | null>(null);
export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { api } = useAuth();
  const [version, setVersion] = useState(0);
  const [state, setState] = useState<Omit<Workspace, "refresh">>({
    resumes: { data: null, error: null },
    analyses: { data: null, error: null },
    history: { data: null, error: null },
    loading: true,
  });
  const refresh = useCallback(() => {
    setState((state) => ({ ...state, loading: true }));
    setVersion((value) => value + 1);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      const result = await Promise.allSettled([
        api.resumes(controller.signal),
        api.analyses(controller.signal),
        api.history(controller.signal),
      ]);
      if (controller.signal.aborted) return;
      const resource = <T,>(result: PromiseSettledResult<T[]>): Resource<T> =>
        result.status === "fulfilled"
          ? { data: result.value, error: null }
          : { data: null, error: safeMessage(result.reason) };
      setState({
        resumes: resource(result[0]),
        analyses: resource(result[1]),
        history: resource(result[2]),
        loading: false,
      });
    })();
    return () => controller.abort();
  }, [api, version]);
  return (
    <WorkspaceContext.Provider value={{ ...state, refresh }}>
      {children}
    </WorkspaceContext.Provider>
  );
}
export function useWorkspace() {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("Workspace context unavailable.");
  return value;
}
