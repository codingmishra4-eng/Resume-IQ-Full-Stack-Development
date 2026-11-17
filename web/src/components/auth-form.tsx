"use client";
import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowRight,
  Eye,
  EyeOff,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";
import { browserClient } from "@/lib/supabase/browser";
import { publicConfig } from "@/lib/config";
import { useHydrated } from "@/lib/hydration";
import { callbackUrl, safeNext } from "@/lib/auth";
import { Button, Notice } from "./ui";
export type AuthMode = "login" | "signup" | "forgot" | "reset";
export function authSchema(mode: AuthMode) {
  return z
    .object({ email: z.string(), password: z.string(), confirm: z.string() })
    .superRefine((value, context) => {
      if (mode !== "reset" && !z.email().safeParse(value.email.trim()).success)
        context.addIssue({
          code: "custom",
          path: ["email"],
          message: "Enter a valid email address.",
        });
      if (
        mode !== "forgot" &&
        value.password.length < (mode === "login" ? 1 : 12)
      )
        context.addIssue({
          code: "custom",
          path: ["password"],
          message:
            mode === "login"
              ? "Enter your password."
              : "Use at least 12 characters.",
        });
      if (
        (mode === "signup" || mode === "reset") &&
        value.password !== value.confirm
      )
        context.addIssue({
          code: "custom",
          path: ["confirm"],
          message: "Passwords do not match.",
        });
    });
}
type Fields = { email: string; password: string; confirm: string };
const copy = {
  login: {
    title: "Welcome back.",
    description: "Your next opportunity starts with a clearer story.",
    action: "Sign in to your workspace",
  },
  signup: {
    title: "Make your next move.",
    description: "Create a private workspace for your professional story.",
    action: "Create your account",
  },
  forgot: {
    title: "A fresh start.",
    description: "We’ll email you a secure link to reset your password.",
    action: "Send reset link",
  },
  reset: {
    title: "Set a new password.",
    description: "Choose a strong password to secure your workspace.",
    action: "Save new password",
  },
};
export function AuthForm({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const params = useSearchParams();
  const config = publicConfig();
  const hydrated = useHydrated();
  const [show, setShow] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const schema = useMemo(() => authSchema(mode), [mode]);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "", confirm: "" },
  });
  async function submit(fields: Fields) {
    setNotice(null);
    setError(null);
    if (!config) return;
    try {
      const client = browserClient();
      if (mode === "login") {
        const result = await client.auth.signInWithPassword({
          email: fields.email.trim(),
          password: fields.password,
        });
        if (result.error || !result.data.session) {
          setError(
            "Unable to sign in. Check your email and password, then try again.",
          );
          return;
        }
        router.replace(safeNext(params.get("next")));
        router.refresh();
      } else if (mode === "signup") {
        const result = await client.auth.signUp({
          email: fields.email.trim(),
          password: fields.password,
          options: { emailRedirectTo: callbackUrl(window.location.origin) },
        });
        if (result.error) {
          setError(
            "Account creation could not be completed. Please try again later.",
          );
          return;
        }
        if (result.data.session) {
          router.replace("/dashboard");
          router.refresh();
        } else
          setNotice(
            "Check your inbox to confirm your email and finish setting up your account.",
          );
      } else if (mode === "forgot") {
        const result = await client.auth.resetPasswordForEmail(
          fields.email.trim(),
          {
            redirectTo: callbackUrl(window.location.origin, "/reset-password"),
          },
        );
        if (result.error && result.error.code !== "user_not_found") {
          setError(
            "Could not request a reset link. Please wait a moment and try again.",
          );
          return;
        }
        setNotice(
          "If an account exists for this email, a reset link will arrive shortly.",
        );
      } else {
        const user = await client.auth.getUser();
        if (user.error || !user.data.user) {
          setError("This reset link has expired. Request a new link.");
          return;
        }
        const result = await client.auth.updateUser({
          password: fields.password,
        });
        if (result.error) {
          setError(
            "Password could not be updated. Request a new link or try a different password.",
          );
          return;
        }
        setNotice(
          "Your password has been updated. You can return to your workspace.",
        );
      }
    } catch {
      setError("Could not connect to your account. Please try again.");
    }
  }
  const detail = copy[mode];
  return (
    <div className="auth-card">
      <BadgeAuth />
      <h1>{detail.title}</h1>
      <p className="auth-description">{detail.description}</p>
      {!config && (
        <Notice>
          Authentication is not configured for this installation. Contact the
          workspace administrator.
        </Notice>
      )}
      {params.get("error") && (
        <Notice error>
          The sign-in link could not be verified. Please request a new link.
        </Notice>
      )}
      {params.get("reason") === "expired" && (
        <Notice>Your session has expired. Sign in to continue.</Notice>
      )}
      {notice && <Notice>{notice}</Notice>}
      {error && <Notice error>{error}</Notice>}
      <form
        method="post"
        onSubmit={handleSubmit(submit)}
        noValidate
        className="auth-form"
      >
        <fieldset className="form-fields" disabled={!hydrated || !config}>
          {mode !== "reset" && (
            <div className="field">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                {...register("email")}
                aria-invalid={Boolean(errors.email)}
                aria-describedby={errors.email ? "email-error" : undefined}
              />
              {errors.email && (
                <p id="email-error" className="field-error">
                  {errors.email.message}
                </p>
              )}
            </div>
          )}
          {mode !== "forgot" && (
            <div className="field">
              <div className="label-row">
                <label htmlFor="password">
                  {mode === "reset" ? "New password" : "Password"}
                </label>
                {mode === "login" && (
                  <Link href="/forgot-password">Forgot password?</Link>
                )}
              </div>
              <div className="password-input">
                <input
                  id="password"
                  type={show ? "text" : "password"}
                  autoComplete={
                    mode === "login" ? "current-password" : "new-password"
                  }
                  placeholder={
                    mode === "login"
                      ? "Your password"
                      : "At least 12 characters"
                  }
                  {...register("password")}
                  aria-invalid={Boolean(errors.password)}
                  aria-describedby={
                    errors.password ? "password-error" : undefined
                  }
                />
                <button
                  type="button"
                  className="icon-button"
                  aria-label={show ? "Hide password" : "Show password"}
                  onClick={() => setShow((value) => !value)}
                >
                  {show ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
              {errors.password && (
                <p id="password-error" className="field-error">
                  {errors.password.message}
                </p>
              )}
            </div>
          )}
          {(mode === "signup" || mode === "reset") && (
            <div className="field">
              <label htmlFor="confirm">Confirm password</label>
              <input
                id="confirm"
                type="password"
                autoComplete="new-password"
                {...register("confirm")}
                aria-invalid={Boolean(errors.confirm)}
                aria-describedby={errors.confirm ? "confirm-error" : undefined}
              />
              {errors.confirm && (
                <p id="confirm-error" className="field-error">
                  {errors.confirm.message}
                </p>
              )}
            </div>
          )}
          <Button
            type="submit"
            className="full-width"
            loading={isSubmitting}
            disabled={!config}
          >
            {detail.action}
            <ArrowRight size={17} />
          </Button>
        </fieldset>
      </form>
      <noscript>
        JavaScript is required to use this secure account form.
      </noscript>
      <div className="auth-alternate">
        {mode === "login" ? (
          <>
            New to ResumeIQ? <Link href="/signup">Create an account</Link>
          </>
        ) : mode === "signup" ? (
          <>
            Already have an account? <Link href="/login">Sign in</Link>
          </>
        ) : (
          <Link href={notice && mode === "reset" ? "/dashboard" : "/login"}>
            {notice && mode === "reset"
              ? "Return to workspace"
              : "Back to sign in"}
          </Link>
        )}
      </div>
      <p className="auth-security">
        <ShieldCheck size={14} /> Private files. Secure sessions. Your
        experience.
      </p>
    </div>
  );
}
function BadgeAuth() {
  return (
    <div className="auth-lock">
      <LockKeyhole size={20} />
    </div>
  );
}
