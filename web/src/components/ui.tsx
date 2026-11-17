"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import {
  ArrowUpRight,
  CheckCircle2,
  Info,
  LoaderCircle,
  X,
} from "lucide-react";
export function Button({
  children,
  variant = "primary",
  loading,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
}) {
  return (
    <button
      type="button"
      {...props}
      disabled={props.disabled || loading}
      className={`button ${variant} ${className}`}
      aria-busy={loading || undefined}
    >
      {loading && (
        <LoaderCircle size={16} className="spin" aria-hidden="true" />
      )}
      {children}
    </button>
  );
}
export function Badge({
  children,
  tone = "muted",
}: {
  children: ReactNode;
  tone?: "mint" | "violet" | "muted";
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action && <div className="heading-action">{action}</div>}
    </header>
  );
}
export function Panel({
  children,
  className = "",
  ...props
}: React.HTMLAttributes<HTMLElement>) {
  return (
    <section className={`panel ${className}`} {...props}>
      {children}
    </section>
  );
}
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon" aria-hidden="true">
        {icon ?? <Info size={24} />}
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <div
      role={error ? "alert" : "status"}
      className={`notice ${error ? "error" : ""}`}
    >
      <Info size={17} aria-hidden="true" />
      <div>{children}</div>
    </div>
  );
}
export function IntegrationNotice({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="integration-notice">
      <Badge tone="violet">Next integration</Badge>
      <h3>{title}</h3>
      <p>{children}</p>
      <span className="muted text-sm">
        No result has been generated. Your draft stays in this browser tab.
      </span>
    </div>
  );
}
export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div
      className="skeleton-group"
      role="status"
      aria-label="Loading workspace"
    >
      <span className="sr-only">Loading…</span>
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="skeleton" />
      ))}
    </div>
  );
}
export function TextLink({
  href,
  children,
}: {
  href: string;
  children: ReactNode;
}) {
  return (
    <Link className="text-link" href={href}>
      {children}
      <ArrowUpRight size={15} aria-hidden="true" />
    </Link>
  );
}
export function Modal({
  open,
  title,
  children,
  onClose,
  busy = false,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  const id = useId();
  const content = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    content.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onClose();
      if (event.key === "Tab") {
        const items = content.current?.querySelectorAll<HTMLElement>(
          'a[href],button:not([disabled]),input:not([disabled]),textarea:not([disabled]),select:not([disabled]),[tabindex="0"]',
        );
        if (!items?.length) {
          event.preventDefault();
          return;
        }
        const first = items[0],
          last = items[items.length - 1];
        if (
          event.shiftKey &&
          (document.activeElement === first ||
            document.activeElement === content.current)
        ) {
          event.preventDefault();
          last.focus();
        } else if (
          !event.shiftKey &&
          (document.activeElement === last ||
            document.activeElement === content.current)
        ) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", keydown);
      previous?.focus();
    };
  }, [open, onClose, busy]);
  if (!open) return null;
  return createPortal(
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div
        ref={content}
        tabIndex={-1}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={id}
      >
        <div className="section-heading">
          <h2 id={id}>{title}</h2>
          <button
            type="button"
            className="icon-button"
            aria-label="Close dialog"
            disabled={busy}
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>,
    document.body,
  );
}
type Toast = { id: number; text: string; error: boolean };
const ToastContext = createContext<(text: string, error?: boolean) => void>(
  () => {},
);
function ToastItem({
  item,
  dismiss,
}: {
  item: Toast;
  dismiss: (id: number) => void;
}) {
  useEffect(() => {
    const timer = setTimeout(() => dismiss(item.id), 6000);
    return () => clearTimeout(timer);
  }, [item.id, dismiss]);
  return (
    <div
      className={`toast ${item.error ? "error" : ""}`}
      role={item.error ? "alert" : "status"}
    >
      <CheckCircle2 size={19} aria-hidden="true" />
      <span>{item.text}</span>
      <button
        className="icon-button"
        aria-label="Dismiss notification"
        onClick={() => dismiss(item.id)}
      >
        <X size={16} />
      </button>
    </div>
  );
}
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const sequence = useRef(0);
  const dismiss = useCallback(
    (id: number) => setItems((items) => items.filter((item) => item.id !== id)),
    [],
  );
  const add = useCallback(
    (text: string, error = false) =>
      setItems((items) => [
        ...items.slice(-2),
        { id: ++sequence.current, text, error },
      ]),
    [],
  );
  return (
    <ToastContext.Provider value={add}>
      {children}
      <div className="toast-stack" aria-live="polite">
        {items.map((item) => (
          <ToastItem key={item.id} item={item} dismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
export function useToast() {
  return useContext(ToastContext);
}
