import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { AuthProvider, useAuth, useWorkspace } from "./providers";
import { account, config, resume } from "@/test/fixtures";
import type { TokenSource } from "@/lib/api";
import type { AuthChangeEvent, Session } from "@supabase/supabase-js";
const mocks = vi.hoisted(() => ({
  router: { replace: vi.fn(), refresh: vi.fn() },
  resumes: vi.fn(),
  analyses: vi.fn(),
  history: vi.fn(),
  getSession: vi.fn(),
  refreshSession: vi.fn(),
  signOut: vi.fn(),
  unsubscribe: vi.fn(),
  change: null as
    null | ((event: AuthChangeEvent, session: Session | null) => void),
  tokenSource: null as TokenSource | null,
}));
vi.mock("next/navigation", () => ({ useRouter: () => mocks.router }));
vi.mock("@/lib/config", () => ({ requireConfig: () => config }));
vi.mock("@/lib/api", () => ({
  ApiClient: class {
    resumes = mocks.resumes;
    analyses = mocks.analyses;
    history = mocks.history;
    constructor(_config: unknown, source: TokenSource) {
      mocks.tokenSource = source;
    }
  },
}));
vi.mock("@/lib/supabase/browser", () => ({
  browserClient: () => ({
    auth: {
      getSession: mocks.getSession,
      refreshSession: mocks.refreshSession,
      signOut: mocks.signOut,
      onAuthStateChange: (callback: typeof mocks.change) => {
        mocks.change = callback;
        return { data: { subscription: { unsubscribe: mocks.unsubscribe } } };
      },
    },
  }),
}));
function Reader() {
  const { account, signOut } = useAuth();
  const { resumes } = useWorkspace();
  return (
    <>
      <span>{account.email}</span>
      <span data-testid="records">
        {resumes.data?.map((item) => item.id).join(",") ?? "loading"}
      </span>
      <button onClick={() => void signOut()}>Logout</button>
    </>
  );
}
beforeEach(() => {
  mocks.resumes.mockResolvedValue([]);
  mocks.analyses.mockResolvedValue([]);
  mocks.history.mockResolvedValue([]);
  mocks.signOut.mockResolvedValue({ error: null });
  mocks.getSession.mockResolvedValue({
    data: { session: { access_token: "synthetic-token" } },
    error: null,
  });
  mocks.refreshSession.mockResolvedValue({
    data: { session: { access_token: "fresh-synthetic-token" } },
    error: null,
  });
});
it("obtains user tokens through Supabase and refreshes only when requested", async () => {
  render(
    <AuthProvider initialAccount={account}>
      <Reader />
    </AuthProvider>,
  );
  await waitFor(() =>
    expect(screen.getByTestId("records")).not.toHaveTextContent("loading"),
  );
  expect(await mocks.tokenSource?.getToken()).toBe("synthetic-token");
  expect(await mocks.tokenSource?.getToken(true)).toBe("fresh-synthetic-token");
});
it("signs out only the local session and clears protected content", async () => {
  const user = userEvent.setup();
  render(
    <AuthProvider initialAccount={account}>
      <Reader />
    </AuthProvider>,
  );
  await user.click(screen.getByRole("button", { name: "Logout" }));
  expect(mocks.signOut).toHaveBeenCalledWith({ scope: "local" });
  expect(mocks.router.replace).toHaveBeenCalledWith("/login");
  expect(screen.queryByText(account.email)).not.toBeInTheDocument();
});
it("does not display a prior account’s in-flight results after account switching", async () => {
  let resolveOld: (value: (typeof resume)[]) => void = () => {};
  mocks.resumes
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve;
        }),
    )
    .mockResolvedValueOnce([]);
  const other = {
    id: "22222222-2222-4222-8222-222222222222",
    email: "other@example.invalid",
    created_at: "2026-11-18T08:30:00Z",
  };
  render(
    <AuthProvider initialAccount={account}>
      <Reader />
    </AuthProvider>,
  );
  await act(async () => {
    mocks.change?.("SIGNED_IN", { user: other } as Session);
  });
  await waitFor(() =>
    expect(screen.getByText(other.email)).toBeInTheDocument(),
  );
  await act(async () => resolveOld([resume]));
  expect(screen.getByTestId("records")).not.toHaveTextContent(resume.id);
  expect(screen.queryByText(account.email)).not.toBeInTheDocument();
});
