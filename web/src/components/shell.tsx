"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import {
  ArrowUpRight,
  FileCheck2,
  Menu,
  ShieldCheck,
  X,
  LogOut,
} from "lucide-react";
import { useAuth } from "./providers";
import { Button, useToast } from "./ui";
const navigation = [
  ["/dashboard", "Overview"],
  ["/analyzer", "Analyzer"],
  ["/job-match", "Job Match"],
  ["/improve", "AI Improve"],
  ["/builder", "Builder"],
  ["/documents", "Documents"],
  ["/upgrade", "Upgrade"],
];
export function Brand() {
  return (
    <Link href="/dashboard" className="brand" aria-label="ResumeIQ home">
      <span className="brand-mark">
        <FileCheck2 size={21} strokeWidth={2} />
      </span>
      <span>
        Resume<span className="brand-iq">IQ</span>
      </span>
    </Link>
  );
}
export function AppShell({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { account, signOut } = useAuth();
  const toast = useToast();
  const [mobile, setMobile] = useState(false);
  return (
    <>
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <Brand />
          <nav
            className={`primary-nav ${mobile ? "is-open" : ""}`}
            id="primary-navigation"
            aria-label="Main navigation"
          >
            {navigation.map(([href, label]) => (
              <Link
                key={href}
                href={href}
                onClick={() => setMobile(false)}
                aria-current={
                  path === href || path.startsWith(href + "/")
                    ? "page"
                    : undefined
                }
              >
                {label}
              </Link>
            ))}
          </nav>
          <div className="account-nav">
            <Link
              href="/profile"
              className="avatar"
              aria-label="Open account profile"
            >
              {(account.email?.[0] ?? "R").toUpperCase()}
            </Link>
            <button
              className="icon-button desktop-logout"
              aria-label="Sign out"
              onClick={() =>
                void signOut().catch(() =>
                  toast("Could not complete sign-out. Please try again.", true),
                )
              }
            >
              <LogOut size={17} />
            </button>
            <button
              className="icon-button mobile-toggle"
              aria-label={mobile ? "Close navigation" : "Open navigation"}
              aria-expanded={mobile}
              aria-controls="primary-navigation"
              onClick={() => setMobile((value) => !value)}
            >
              {mobile ? <X size={23} /> : <Menu size={23} />}
            </button>
          </div>
        </div>
      </header>
      <div className="workspace-label">
        <span>
          <span className="status-dot" /> Personal workspace
        </span>
        <span>
          <ShieldCheck size={13} /> Private by design
        </span>
      </div>
      <main id="main-content" className="app-main" tabIndex={-1}>
        {children}
      </main>
      <footer className="app-footer">
        <span>
          ResumeIQ <span className="muted">/</span> Make your experience count.
        </span>
        <Link href="/profile">
          Your account <ArrowUpRight size={13} />
        </Link>
      </footer>
    </>
  );
}
export function RefreshButton({
  refresh,
  loading,
}: {
  refresh: () => void;
  loading: boolean;
}) {
  return (
    <Button variant="ghost" loading={loading} onClick={refresh}>
      Refresh
    </Button>
  );
}
