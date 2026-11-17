"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Clock3,
  FileText,
  FolderOpen,
  Plus,
  Search,
  ShieldCheck,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { type StoredResume, type HistoryEntry, validateFile } from "@/lib/api";
import { count, date, documentTitle, safeMessage } from "@/lib/format";
import { useAuth, useWorkspace } from "./providers";
import {
  Badge,
  Button,
  EmptyState,
  Modal,
  Notice,
  PageHeading,
  Panel,
  Skeleton,
  useToast,
} from "./ui";
export function FileUpload({
  onSuccess,
}: {
  onSuccess?: (resume: StoredResume) => void;
}) {
  const { api } = useAuth();
  const { refresh } = useWorkspace();
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [percent, setPercent] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => () => controller.current?.abort(), []);
  function select(files: FileList | File[] | null) {
    setError(null);
    setPercent(0);
    if (!files?.length) return;
    if (files.length !== 1) {
      setError("Choose one resume at a time.");
      setFile(null);
      return;
    }
    try {
      validateFile(files[0]);
      setFile(files[0]);
    } catch (error) {
      setFile(null);
      setError(safeMessage(error));
    }
  }
  async function upload() {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    setPercent(0);
    controller.current = new AbortController();
    try {
      const result = await api.upload(
        file,
        setPercent,
        controller.current.signal,
      );
      setFile(null);
      if (input.current) input.current.value = "";
      toast("Resume uploaded to your private workspace.");
      refresh();
      onSuccess?.(result);
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError")
        toast("Request stopped. Refresh Documents to confirm upload status.");
      else setError(safeMessage(error));
      refresh();
    } finally {
      setBusy(false);
      controller.current = null;
    }
  }
  return (
    <div className="file-upload">
      <label
        className={`upload-zone ${dragging ? "is-dragging" : ""} ${busy ? "is-busy" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          if (!busy) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (!busy) select(event.dataTransfer.files);
        }}
      >
        <input
          ref={input}
          className="sr-only"
          type="file"
          accept=".pdf,.docx"
          disabled={busy}
          aria-label="Choose a PDF or DOCX resume"
          onChange={(event) => select(event.currentTarget.files)}
        />
        <span className="upload-icon">
          <UploadCloud size={25} strokeWidth={1.5} />
        </span>
        <strong>{file ? file.name : "Drop your resume here"}</strong>
        <span>
          {file ? (
            `${(file.size / 1024).toFixed(0)} KB · Ready to upload`
          ) : (
            <>
              or <span className="link-color">browse files</span> from your
              device
            </>
          )}
        </span>
        <span className="upload-formats">
          PDF or DOCX <span>·</span> Up to 10 MB
        </span>
      </label>
      {busy && (
        <div className="upload-progress">
          <progress max={100} value={percent} aria-label="Upload progress" />
          <span role="status">
            {percent < 99
              ? `Uploading · ${percent}%`
              : "Validating and storing your resume…"}
          </span>
        </div>
      )}
      {error && <Notice error>{error}</Notice>}
      <div className="upload-actions">
        <span className="privacy-note">
          <ShieldCheck size={14} /> Stored privately. Never public.
        </span>
        {busy ? (
          <Button
            variant="secondary"
            onClick={() => controller.current?.abort()}
          >
            Stop request
          </Button>
        ) : (
          <Button onClick={() => void upload()} disabled={!file}>
            <UploadCloud size={16} /> Upload resume
          </Button>
        )}
      </div>
    </div>
  );
}
export function UploadButton({ label = "Upload resume" }: { label?: string }) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  return (
    <>
      <Button onClick={() => setOpen(true)}>
        <Plus size={17} />
        {label}
      </Button>
      <Modal open={open} title="Add a resume" onClose={close}>
        <p className="muted modal-description">
          Keep another version of your professional story in one private place.
        </p>
        <FileUpload onSuccess={close} />
      </Modal>
    </>
  );
}
export function DownloadButton({ resume }: { resume: StoredResume }) {
  const { api } = useAuth();
  const toast = useToast();
  const [ready, setReady] = useState<{ url: string; expiresIn: number } | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!ready) return;
    const timer = setTimeout(() => setReady(null), ready.expiresIn * 1000);
    return () => clearTimeout(timer);
  }, [ready]);
  async function prepare() {
    setBusy(true);
    try {
      setReady(await api.download(resume.id));
    } catch (error) {
      toast(safeMessage(error), true);
    } finally {
      setBusy(false);
    }
  }
  if (ready) {
    const url = new URL(ready.url);
    url.searchParams.set("download", resume.metadata.file_name);
    return (
      <a
        className="button secondary small"
        href={url.toString()}
        target="_blank"
        rel="noopener noreferrer"
        referrerPolicy="no-referrer"
        aria-label={`Save ${resume.metadata.file_type.toUpperCase()} ${resume.id.slice(0, 6)}`}
      >
        <ArrowDownToLine size={15} /> Save file
      </a>
    );
  }
  return (
    <Button
      variant="ghost"
      className="small"
      loading={busy}
      aria-label={`Download ${resume.metadata.file_type.toUpperCase()} ${resume.id.slice(0, 6)}`}
      onClick={() => void prepare()}
    >
      <ArrowDownToLine size={16} />
      <span className="action-label">Download</span>
    </Button>
  );
}
export function DeleteButton({ resume }: { resume: StoredResume }) {
  const { api } = useAuth();
  const { refresh } = useWorkspace();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  async function remove() {
    setBusy(true);
    try {
      await api.remove(resume.id);
      toast("Resume deleted.");
      close();
    } catch (error) {
      toast(safeMessage(error), true);
    } finally {
      setBusy(false);
      refresh();
    }
  }
  return (
    <>
      <Button
        variant="ghost"
        className="small delete-action"
        aria-label={`Delete ${resume.metadata.file_type.toUpperCase()} ${resume.id.slice(0, 6)}`}
        onClick={() => setOpen(true)}
      >
        <Trash2 size={16} />
      </Button>
      <Modal
        open={open}
        title="Delete this resume?"
        onClose={close}
        busy={busy}
      >
        <div className="delete-preview">
          <FileText size={24} />
          <div>
            <strong>{documentTitle(resume)}</strong>
            <p>{count(resume.metadata.word_count)} words · Private document</p>
          </div>
        </div>
        <p className="muted">
          The uploaded file will be removed from private storage. This cannot be
          undone. Activity history remains.
        </p>
        <div className="modal-actions">
          <Button variant="secondary" disabled={busy} onClick={close}>
            Keep resume
          </Button>
          <Button variant="danger" loading={busy} onClick={() => void remove()}>
            Delete resume
          </Button>
        </div>
      </Modal>
    </>
  );
}
export function ResumeTable({
  resumes,
  compact = false,
}: {
  resumes: StoredResume[];
  compact?: boolean;
}) {
  return (
    <div className="table-scroll">
      <table className="resume-table">
        <caption className="sr-only">Your private resumes</caption>
        <thead>
          <tr>
            <th>Document</th>
            <th className="hide-mobile">Words</th>
            <th className="hide-mobile">Added</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {resumes.map((resume) => (
            <tr key={resume.id}>
              <td>
                <Link
                  className="document-name"
                  href={`/documents/${resume.id}`}
                >
                  <span className={`file-icon ${resume.metadata.file_type}`}>
                    <FileText size={21} strokeWidth={1.5} />
                  </span>
                  <span>
                    <strong>{resume.metadata.file_name}</strong>
                    <small>
                      {resume.metadata.file_type.toUpperCase()} <span>·</span>{" "}
                      {resume.metadata.pages}{" "}
                      {resume.metadata.pages === 1 ? "page" : "pages"}{" "}
                      <span>·</span> {resume.id.slice(0, 6)}
                    </small>
                  </span>
                </Link>
              </td>
              <td className="hide-mobile mono">
                {count(resume.metadata.word_count)}
              </td>
              <td className="hide-mobile muted">{date(resume.created_at)}</td>
              <td>
                <div className="row-actions">
                  {compact ? (
                    <Link
                      className="icon-button"
                      href={`/documents/${resume.id}`}
                      aria-label={`Open resume ${resume.id.slice(0, 6)}`}
                    >
                      <ArrowRight size={17} />
                    </Link>
                  ) : (
                    <>
                      <DownloadButton resume={resume} />
                      <DeleteButton resume={resume} />
                    </>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function DocumentsPage() {
  const { resumes, history, loading, refresh } = useWorkspace();
  const [query, setQuery] = useState("");
  const [tab, setTab] = useState<"documents" | "history">("documents");
  const filtered =
    resumes.data?.filter((item) =>
      `${item.metadata.file_name} ${item.metadata.file_type} ${item.id} ${date(item.created_at)}`
        .toLowerCase()
        .includes(query.toLowerCase()),
    ) ?? [];
  return (
    <>
      <PageHeading
        eyebrow="YOUR LIBRARY"
        title="Every version. One place."
        description="A private home for the documents behind your next opportunity."
        action={<UploadButton />}
      />
      <div className="document-toolbar">
        <div className="pill-tabs" aria-label="Library views">
          {(["documents", "history"] as const).map((item) => (
            <Button
              variant="ghost"
              key={item}
              aria-pressed={tab === item}
              onClick={() => setTab(item)}
            >
              {item === "documents" ? (
                <FolderOpen size={15} />
              ) : (
                <Clock3 size={15} />
              )}
              {item === "documents" ? "Documents" : "Activity"}
            </Button>
          ))}
        </div>
        <Button variant="ghost" loading={loading} onClick={refresh}>
          Refresh
        </Button>
      </div>
      {tab === "documents" ? (
        <Panel>
          <div className="section-heading">
            <div>
              <h2>
                Your resumes{" "}
                {resumes.data && (
                  <span className="count-bubble">{resumes.data.length}</span>
                )}
              </h2>
              <p>Only you can access these files.</p>
            </div>
            <label className="search-input">
              <Search size={16} />
              <span className="sr-only">Search documents</span>
              <input
                placeholder="Search documents…"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
          </div>
          {resumes.error ? (
            <Notice error>{resumes.error}</Notice>
          ) : loading && !resumes.data ? (
            <Skeleton />
          ) : filtered.length ? (
            <ResumeTable resumes={filtered} />
          ) : (
            <EmptyState
              icon={<FolderOpen size={26} />}
              title={
                query ? "No documents match." : "Your next chapter starts here."
              }
              action={!query && <UploadButton label="Add your first resume" />}
            >
              {query
                ? "Try a different type, date or document ID."
                : "Upload a PDF or DOCX resume to start building your private library."}
            </EmptyState>
          )}
        </Panel>
      ) : (
        <Panel>
          <div className="section-heading">
            <div>
              <h2>Workspace activity</h2>
              <p>A record of your uploads and document changes.</p>
            </div>
            <Badge tone="mint">Private</Badge>
          </div>
          {history.error ? (
            <Notice error>{history.error}</Notice>
          ) : !history.data ? (
            <Skeleton />
          ) : (
            <HistoryList items={history.data} />
          )}
        </Panel>
      )}
    </>
  );
}
export function HistoryList({
  items,
  limit,
}: {
  items: HistoryEntry[];
  limit?: number;
}) {
  if (!items.length)
    return (
      <EmptyState icon={<Clock3 size={23} />} title="A clean slate.">
        Your document activity will appear here as you use your workspace.
      </EmptyState>
    );
  return (
    <ul className="activity-list">
      {items.slice(0, limit).map((item) => (
        <li key={item.id}>
          <span
            className={`activity-icon ${item.event === "resume_deleted" ? "deleted" : ""}`}
          >
            {item.event === "resume_deleted" ? (
              <Trash2 size={15} />
            ) : (
              <UploadCloud size={15} />
            )}
          </span>
          <div>
            <strong>
              {(
                {
                  resume_uploaded: "Resume uploaded",
                  resume_deleted: "Resume deleted",
                  analysis_created: "Analysis generated",
                  job_matched: "Job comparison saved",
                  draft_saved: "Builder draft saved",
                  draft_deleted: "Builder draft deleted",
                  export_generated: "Resume export generated",
                } as Record<string, string>
              )[item.event] ?? "Workspace activity"}
            </strong>
            <small>
              Resource {item.resource_id.slice(0, 6)} · {date(item.created_at)}
            </small>
          </div>
        </li>
      ))}
    </ul>
  );
}
