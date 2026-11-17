"use client";
import { useEffect, useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useHydrated } from "@/lib/hydration";
import { Check, Download, FileJson, Printer } from "lucide-react";
import { Badge, Button, Notice, PageHeading, Panel, useToast } from "./ui";
import {
  builderDraftSchema,
  type BuilderDraft,
  type DraftSummary,
  type Template,
} from "@/lib/features";
import { useAuth, useWorkspace } from "./providers";
import { Modal } from "./ui";
import { date } from "@/lib/format";
export const draftSchema = builderDraftSchema;
export type Draft = BuilderDraft;
const empty: Draft = {
  name: "",
  title: "",
  email: "",
  phone: "",
  location: "",
  summary: "",
  experience: "",
  education: "",
  skills: "",
};
const templates = [
  {
    id: "essential",
    name: "Essential",
    text: "Clear. Focused. Single column.",
  },
  {
    id: "editorial",
    name: "Editorial",
    text: "Classic typography. Quiet confidence.",
  },
  {
    id: "compact",
    name: "Compact",
    text: "A little more room for your story.",
  },
];
export function Builder() {
  const hydrated = useHydrated();
  const [template, setTemplate] = useState<
    "essential" | "editorial" | "compact"
  >("essential");
  const { api } = useAuth();
  const { refresh } = useWorkspace();
  const [draftId, setDraftId] = useState(""),
    [choice, setChoice] = useState("");
  const [saved, setSaved] = useState<DraftSummary[]>([]),
    [supported, setSupported] = useState<Template[]>([]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [confirm, setConfirm] = useState<"load" | "delete" | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      api.drafts(controller.signal),
      api.templates(controller.signal),
    ])
      .then(([drafts, catalog]) => {
        if (!controller.signal.aborted) {
          setSaved(drafts);
          setSupported(catalog);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted)
          setError(
            e instanceof Error ? e.message : "Saved drafts unavailable.",
          );
      });
    return () => controller.abort();
  }, [api]);
  const toast = useToast();
  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<Draft>({
    defaultValues: empty,
    resolver: zodResolver(draftSchema),
  });
  const values = useWatch({ control }) as Draft;
  async function reload() {
    setSaved(await api.drafts());
    await refresh();
  }
  async function save(draft: Draft, format?: "pdf" | "docx", asNew = false) {
    setBusy(true);
    setError("");
    try {
      const value = await api.saveDraft(
        { template, draft },
        asNew ? undefined : draftId || undefined,
      );
      setDraftId(value.id);
      setChoice(value.id);
      reset(value.draft);
      toast("Draft saved privately.");
      await reload();
      if (format) {
        const blob = await api.exportDraft(value.id, format);
        downloadBlob(blob, `resume.${format}`);
        toast("Export generated. Review before sharing.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save or export unavailable.");
    } finally {
      setBusy(false);
    }
  }
  async function load() {
    setConfirm(null);
    setBusy(true);
    setError("");
    try {
      const value = await api.draft(choice);
      reset(value.draft);
      setTemplate(value.template);
      setDraftId(value.id);
      toast("Saved draft loaded.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Draft unavailable.");
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    setConfirm(null);
    setBusy(true);
    setError("");
    try {
      await api.deleteDraft(draftId);
      setDraftId("");
      setChoice("");
      reset(empty);
      await reload();
      toast("Saved draft deleted.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete unavailable.");
    } finally {
      setBusy(false);
    }
  }
  function downloadBlob(blob: Blob, name: string) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function download(draft: Draft) {
    const blob = new Blob(
      [JSON.stringify({ version: 1, template, draft }, null, 2)],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "resumeiq-draft.json";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("Draft downloaded. It has not been saved to the cloud.");
  }
  return (
    <>
      <PageHeading
        eyebrow="DESIGN YOUR NEXT CHAPTER"
        title="A story worth presenting well."
        description="Build a clean draft with a live preview. Save privately or generate a PDF or DOCX when ready."
      />
      <Notice>
        Unsaved edits stay in this browser tab. Save or export explicitly to
        store a private draft. Loading another draft replaces local edits;
        leaving this page clears unsaved changes.
      </Notice>
      {error && <Notice error>{error}</Notice>}
      <Panel>
        <h2>Private saved drafts</h2>
        <div className="field">
          <label htmlFor="saved-builder-draft">Choose a saved draft</label>
          <select
            id="saved-builder-draft"
            disabled={busy}
            value={choice}
            onChange={(event) => setChoice(event.target.value)}
          >
            <option value="">Select a saved draft</option>
            {saved.map((item) => (
              <option key={item.id} value={item.id}>
                {item.template} · {date(item.updated_at)} ·{" "}
                {item.id.slice(0, 6)}
              </option>
            ))}
          </select>
        </div>
        {!saved.length && <p>No saved drafts yet.</p>}
        <div className="editor-actions">
          <Button
            disabled={busy || !choice}
            variant="secondary"
            onClick={() => setConfirm("load")}
          >
            Load selected draft
          </Button>
          <Button
            disabled={busy || !draftId}
            variant="secondary"
            onClick={() => setConfirm("delete")}
          >
            Delete current saved draft
          </Button>
        </div>
        <p className="muted">
          {draftId
            ? `Editing saved draft ${draftId.slice(0, 8)}`
            : "New browser-tab draft"}
        </p>
        {busy && (
          <p role="status">Saving, loading or generating your document…</p>
        )}
      </Panel>
      <Modal
        open={confirm !== null}
        title={
          confirm === "delete"
            ? "Delete saved draft?"
            : "Replace unsaved edits?"
        }
        onClose={() => setConfirm(null)}
      >
        <p>
          {confirm === "delete"
            ? "This deletes the current private draft and clears this editor."
            : "Loading replaces your current local edits with the selected saved draft."}
        </p>
        <Button variant="secondary" onClick={() => setConfirm(null)}>
          Cancel
        </Button>
        <Button onClick={() => void (confirm === "delete" ? remove() : load())}>
          Confirm
        </Button>
      </Modal>
      <div className="template-grid" aria-label="Resume templates">
        {templates.map((item) => (
          <button
            type="button"
            key={item.id}
            className={`template-card ${template === item.id ? "selected" : ""}`}
            aria-pressed={template === item.id}
            disabled={busy}
            onClick={() => setTemplate(item.id as typeof template)}
          >
            <span className={`template-mini ${item.id}`} aria-hidden="true">
              <i />
              <i />
              <hr />
              <i />
              <i />
              <i />
            </span>
            <span>
              <strong>{item.name}</strong>
              <small>{item.text}</small>
            </span>
            {template === item.id && <Check size={17} />}
          </button>
        ))}
      </div>
      <div className="builder-workspace">
        <Panel className="builder-editor">
          <div className="section-heading">
            <h2>Your content</h2>
            <Badge>Draft</Badge>
          </div>
          <form method="post" onSubmit={handleSubmit(download)} noValidate>
            <fieldset className="form-fields" disabled={!hydrated || busy}>
              <div className="field-pair">
                {[
                  ["name", "Full name"],
                  ["title", "Professional title"],
                  ["email", "Email"],
                  ["phone", "Phone"],
                  ["location", "Location"],
                ].map(([key, label]) => (
                  <div className="field" key={key}>
                    <label htmlFor={`builder-${key}`}>{label}</label>
                    <input
                      id={`builder-${key}`}
                      type={key === "email" ? "email" : "text"}
                      {...register(key as keyof Draft)}
                      aria-invalid={Boolean(errors[key as keyof Draft])}
                      aria-describedby={
                        errors[key as keyof Draft]
                          ? `builder-error-${key}`
                          : undefined
                      }
                    />
                    {errors[key as keyof Draft] && (
                      <span className="field-error" id={`builder-error-${key}`}>
                        {errors[key as keyof Draft]?.message}
                      </span>
                    )}
                  </div>
                ))}
              </div>
              {[
                ["summary", "Professional summary", 4],
                ["experience", "Experience", 7],
                ["education", "Education", 3],
                ["skills", "Skills", 3],
              ].map(([key, label, rows]) => (
                <div className="field" key={String(key)}>
                  <label htmlFor={`builder-${key}`}>{label}</label>
                  <textarea
                    id={`builder-${key}`}
                    rows={Number(rows)}
                    {...register(key as keyof Draft)}
                  />
                  {errors[key as keyof Draft] && (
                    <span className="field-error">
                      {errors[key as keyof Draft]?.message}
                    </span>
                  )}
                </div>
              ))}
              <Button type="submit">
                <FileJson size={16} /> Download draft JSON
              </Button>
              <div className="editor-actions">
                <Button
                  disabled={busy || !supported.length}
                  onClick={() => void handleSubmit((draft) => save(draft))()}
                >
                  {draftId ? "Update saved draft" : "Save private draft"}
                </Button>
                <Button
                  variant="secondary"
                  disabled={busy || !supported.length}
                  onClick={() =>
                    void handleSubmit((draft) => save(draft, undefined, true))()
                  }
                >
                  Save as new draft
                </Button>
              </div>
              <div className="editor-actions">
                <Button
                  disabled={busy || !supported.length}
                  onClick={() =>
                    void handleSubmit((draft) => save(draft, "pdf"))()
                  }
                >
                  Save and download PDF
                </Button>
                <Button
                  disabled={busy || !supported.length}
                  onClick={() =>
                    void handleSubmit((draft) => save(draft, "docx"))()
                  }
                >
                  Save and download DOCX
                </Button>
              </div>
              <p className="muted text-sm mt-3">
                This is editable draft data, not a generated resume PDF.
              </p>
            </fieldset>
          </form>
          <noscript>
            JavaScript is required to edit and download a local draft.
          </noscript>
        </Panel>
        <div className="preview-column">
          <div className="preview-toolbar">
            <div>
              <span className="eyebrow">LIVE PREVIEW</span>
              <span>
                {templates.find((item) => item.id === template)?.name}
              </span>
            </div>
            <Button variant="ghost" onClick={() => window.print()}>
              <Printer size={16} /> Print draft
            </Button>
          </div>
          <article
            className={`resume-preview ${template}`}
            aria-label="Live resume draft preview"
          >
            <header>
              <h2>{values.name || "Your name"}</h2>
              <p className="resume-job-title">
                {values.title || "Your professional title"}
              </p>
              <p className="resume-contact">
                {[values.email, values.phone, values.location]
                  .filter(Boolean)
                  .join(" · ") || "Your contact details"}
              </p>
            </header>
            {[
              ["summary", "Profile"],
              ["experience", "Experience"],
              ["education", "Education"],
              ["skills", "Skills"],
            ].map(([key, label]) => (
              <section key={key}>
                <h3>{label}</h3>
                <p
                  className={
                    !values[key as keyof Draft] ? "preview-placeholder" : ""
                  }
                >
                  {values[key as keyof Draft] ||
                    `Your ${label.toLowerCase()} will appear here.`}
                </p>
              </section>
            ))}
          </article>
          <div className="export-note">
            <Download size={17} />
            <p>
              Browser print preserves this preview. Server exports use the
              mapped ATS-friendly single-column template, with different
              typography and pagination:{" "}
              {supported.find((item) => item.id === template)?.backend_id ??
                "loading server template catalog"}
              . PDF/DOCX exports save the current draft first.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
