"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Copy, KeyRound, LogOut, ShieldCheck, UserRound } from "lucide-react";
import { useAuth } from "./providers";
import { Badge, Button, Notice, PageHeading, Panel, useToast } from "./ui";
import { date } from "@/lib/format";
export function Profile() {
  const { account, api, signOut } = useAuth();
  const toast = useToast();
  const [status, setStatus] = useState<"loading" | "verified" | "error">(
    "loading",
  );
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      api.me(controller.signal),
      api.versionedMe(controller.signal),
    ])
      .then((identities) => {
        if (!controller.signal.aborted)
          setStatus(
            identities.every((item) => item.id === account.id)
              ? "verified"
              : "error",
          );
      })
      .catch(() => {
        if (!controller.signal.aborted) setStatus("error");
      });
    return () => controller.abort();
  }, [api, account.id]);
  return (
    <>
      <PageHeading
        eyebrow="YOUR ACCOUNT"
        title="A workspace that’s yours."
        description="Your identity, security and account controls in one place."
      />
      <div className="profile-grid">
        <Panel>
          <div className="profile-identity">
            <span className="profile-avatar">
              <UserRound size={33} />
            </span>
            <div>
              <h2>{account.email ?? "ResumeIQ account"}</h2>
              <Badge tone={status === "verified" ? "mint" : "muted"}>
                {status === "verified"
                  ? "API identity verified"
                  : status === "error"
                    ? "Verification unavailable"
                    : "Checking identity…"}
              </Badge>
            </div>
          </div>
          {status === "error" && (
            <Notice error>
              Your workspace identity could not be verified. Refresh or sign out
              and try again.
            </Notice>
          )}
          <dl className="account-details">
            <div>
              <dt>Email address</dt>
              <dd>{account.email ?? "Not provided"}</dd>
            </div>
            <div>
              <dt>Account created</dt>
              <dd>
                {account.createdAt ? date(account.createdAt) : "Not available"}
              </dd>
            </div>
            <div>
              <dt>Account ID</dt>
              <dd className="account-id">
                <code>{account.id}</code>
                <button
                  className="icon-button"
                  aria-label="Copy account ID"
                  onClick={() => {
                    void navigator.clipboard
                      .writeText(account.id)
                      .then(() => toast("Account ID copied."))
                      .catch(() => toast("Copy is unavailable.", true));
                  }}
                >
                  <Copy size={15} />
                </button>
              </dd>
            </div>
          </dl>
          <p className="muted text-sm">
            Your documents stay private and associated with this account.
          </p>
        </Panel>
        <div className="profile-controls">
          <Panel>
            <span className="feature-icon small">
              <KeyRound size={20} />
            </span>
            <h2>Keep your account secure.</h2>
            <p className="muted">
              Request a password reset link whenever you need a fresh start.
            </p>
            <Link href="/forgot-password" className="button secondary">
              Reset password
            </Link>
          </Panel>
          <Panel>
            <span className="feature-icon small">
              <ShieldCheck size={20} />
            </span>
            <h2>Done for now?</h2>
            <p className="muted">
              Sign out of this browser session. Your stored documents remain in
              your private workspace.
            </p>
            <Button
              variant="secondary"
              loading={busy}
              onClick={() => {
                setBusy(true);
                void signOut()
                  .catch(() =>
                    toast("Could not complete sign-out. Try again.", true),
                  )
                  .finally(() => setBusy(false));
              }}
            >
              <LogOut size={16} /> Sign out
            </Button>
          </Panel>
        </div>
      </div>
    </>
  );
}
export function Upgrade() {
  return (
    <>
      <PageHeading
        eyebrow="BUILT WITH INTENTION"
        title="Built for what comes next."
        description="Your current workspace is focused on secure document management. Billing is not connected."
      />
      <Panel className="upgrade-panel">
        <Badge tone="mint">Available now</Badge>
        <h2>A private home for your next chapter.</h2>
        <p>
          Use your account to upload resumes, manage versions, request
          short-lived downloads and review your document activity.
        </p>
        <ul className="check-list">
          <li>
            <ShieldCheck size={16} /> Authenticated personal workspace
          </li>
          <li>
            <ShieldCheck size={16} /> Private PDF and DOCX storage
          </li>
          <li>
            <ShieldCheck size={16} /> Owner-only document management
          </li>
        </ul>
        <Link href="/documents" className="button primary">
          Open your documents
        </Link>
        <hr />
        <h3>What comes next</h3>
        <p className="muted">
          Detailed analysis, role comparisons, source-grounded writing
          assistance and private PDF/DOCX exports are available in your
          workspace. AI provider use requires consent and server opt-in. Billing
          remains unavailable.
        </p>
        <span className="muted text-sm">
          No checkout, subscriptions or payment collection.
        </span>
      </Panel>
    </>
  );
}
