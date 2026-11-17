"use client";
import { useState } from "react";
import { Clipboard, Sparkles } from "lucide-react";
import { useAuth, useWorkspace } from "./providers";
import {
  Badge,
  Button,
  Notice,
  PageHeading,
  Panel,
  TextLink,
  useToast,
} from "./ui";
import { MatchView } from "./match-result";
import type { Improvements, MatchRecord } from "@/lib/features";
import { date } from "@/lib/format";
function ResumePicker({
  value,
  onChange,
  disabled = false,
}: {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const { resumes } = useWorkspace();
  return (
    <div className="field">
      <label htmlFor="workflow-resume">Choose your resume</label>
      <select
        id="workflow-resume"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">Select a stored resume</option>
        {resumes.data?.map((item) => (
          <option key={item.id} value={item.id}>
            {item.metadata.file_name} · {date(item.created_at)} ·{" "}
            {item.id.slice(0, 6)}
          </option>
        ))}
      </select>
      {resumes.error && <Notice error>{resumes.error}</Notice>}
      {resumes.data?.length === 0 && (
        <TextLink href="/analyzer">Upload a resume first</TextLink>
      )}
    </div>
  );
}
export function JobMatch() {
  const { api } = useAuth();
  const { refresh } = useWorkspace();
  const [selected, setSelected] = useState(""),
    [description, setDescription] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [record, setRecord] = useState<MatchRecord | null>(null);
  const toast = useToast();
  async function compare() {
    setBusy(true);
    setError("");
    setRecord(null);
    try {
      setRecord(await api.match(selected, description));
      await refresh();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Comparison could not be completed.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageHeading
        eyebrow="ROLE ALIGNMENT"
        title="Find the connection."
        description="Compare your actual resume with the skills and keywords in a target role."
      />
      <div className="workflow-grid">
        <Panel>
          <h2>Your target role</h2>
          <ResumePicker
            value={selected}
            disabled={busy}
            onChange={(value) => {
              setSelected(value);
              setRecord(null);
            }}
          />
          <div className="field">
            <label htmlFor="job-description">Job description</label>
            <textarea
              id="job-description"
              rows={12}
              maxLength={20000}
              disabled={busy}
              value={description}
              onChange={(event) => {
                setDescription(event.target.value);
                setRecord(null);
              }}
            />
            <small>
              30–20,000 characters. The raw description is not saved.
            </small>
          </div>
          <div className="editor-actions">
            <Button
              variant="secondary"
              disabled={!description}
              onClick={() => {
                void navigator.clipboard
                  .writeText(description)
                  .then(() => toast("Job description copied."))
                  .catch(() => toast("Copy is unavailable.", true));
              }}
            >
              <Clipboard size={16} /> Copy draft
            </Button>
            <Button
              disabled={busy || !selected || description.trim().length < 30}
              onClick={() => void compare()}
            >
              {busy ? "Comparing…" : "Compare resumes"}
            </Button>
          </div>
          {busy && (
            <p role="status">
              Reading your stored document and calculating alignment…
            </p>
          )}
          {error && <Notice error>{error}</Notice>}
        </Panel>
        <Panel>
          <div className="section-heading">
            <h2>Match overview</h2>
            <Badge>
              {record ? "Computed from your document" : "Not generated"}
            </Badge>
          </div>
          {record ? (
            <>
              <MatchView result={record.result} />
              <p className="muted">
                Saved {date(record.created_at)} · {record.id.slice(0, 8)}
              </p>
            </>
          ) : (
            <p>
              Select your resume and submit a role description to calculate a
              real comparison.
            </p>
          )}
        </Panel>
      </div>
    </>
  );
}
const modes = ["summary", "bullets", "verbs", "keywords"] as const;
type Mode = (typeof modes)[number];
const labels = {
  summary: "Professional summary",
  bullets: "Experience bullets",
  verbs: "Action verbs",
  keywords: "Keyword guidance",
};
export function Improve() {
  const { api } = useAuth();
  const toast = useToast();
  const [selected, setSelected] = useState(""),
    [mode, setMode] = useState<Mode>("summary");
  const [drafts, setDrafts] = useState<Record<Mode, string>>({
    summary: "",
    bullets: "",
    verbs: "",
    keywords: "",
  });
  const [jd, setJD] = useState(""),
    [consent, setConsent] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [result, setResult] = useState<Improvements | null>(null),
    [edits, setEdits] = useState<string[]>([]);
  const draft = drafts[mode];
  async function improve() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const value = await api.improve(selected, {
        kind: mode,
        text: draft,
        job_description: jd.trim() || undefined,
        use_ai: consent,
      });
      setResult(value);
      setEdits(value.items.map((item) => item.improved));
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Writing assistance unavailable.",
      );
    } finally {
      setBusy(false);
    }
  }
  function copy(text: string) {
    void navigator.clipboard
      .writeText(text)
      .then(() => toast("Text copied. Review before using."))
      .catch(() => toast("Copy is unavailable.", true));
  }
  return (
    <>
      <PageHeading
        eyebrow="WORDS WITH PURPOSE"
        title="Make your work speak clearly."
        description="Review source-grounded suggestions. No suggestion overwrites your original document."
      />
      <div className="pill-tabs mb-6" aria-label="Writing mode">
        {modes.map((value) => (
          <Button
            key={value}
            variant="ghost"
            disabled={busy}
            aria-pressed={mode === value}
            onClick={() => {
              setMode(value);
              setResult(null);
            }}
          >
            {labels[value]}
          </Button>
        ))}
      </div>
      <div className="writing-grid">
        <Panel>
          <h2>{labels[mode]}</h2>
          <ResumePicker
            value={selected}
            disabled={busy}
            onChange={(value) => {
              setSelected(value);
              setResult(null);
            }}
          />
          <label htmlFor="original-draft">
            Original{" "}
            {mode === "summary"
              ? "summary"
              : mode === "bullets"
                ? "bullet points"
                : "resume excerpt"}
          </label>
          <textarea
            id="original-draft"
            className="writing-editor"
            rows={10}
            maxLength={6000}
            disabled={busy}
            value={draft}
            onChange={(event) => {
              setDrafts((value) => ({ ...value, [mode]: event.target.value }));
              setResult(null);
            }}
            placeholder="Copy an exact excerpt from the selected resume, or leave empty to use its detected summary or bullets."
          />
          <div className="field">
            <label htmlFor="improve-jd">
              Job description{" "}
              {mode === "keywords" ? "(required)" : "(optional)"}
            </label>
            <textarea
              id="improve-jd"
              rows={4}
              maxLength={20000}
              disabled={busy}
              value={jd}
              onChange={(event) => {
                setJD(event.target.value);
                setResult(null);
              }}
            />
          </div>
          <label className="consent-row">
            <input
              type="checkbox"
              checked={consent}
              disabled={busy}
              onChange={(event) => setConsent(event.target.checked)}
            />{" "}
            Allow the server’s AI provider to process this excerpt. Optional;
            requires server opt-in. Rules remain available.
          </label>
          <div className="editor-actions">
            <Button
              variant="secondary"
              disabled={!draft}
              onClick={() => copy(draft)}
            >
              <Clipboard size={16} /> Copy original draft
            </Button>
            <Button
              disabled={
                busy ||
                !selected ||
                (mode === "keywords" && jd.trim().length < 30) ||
                (!!jd.trim() && jd.trim().length < 30)
              }
              onClick={() => void improve()}
            >
              {busy ? "Reviewing…" : "Suggest improvements"}
            </Button>
          </div>
          {busy && (
            <p role="status">Checking source text and preparing suggestions…</p>
          )}
          {error && <Notice error>{error}</Notice>}
        </Panel>
        <Panel>
          <div className="section-heading">
            <h2>Thoughtful improvements</h2>
            <Sparkles size={20} />
          </div>
          {!result ? (
            <Notice>No rewrite has been generated.</Notice>
          ) : (
            <>
              <Notice>{result.notice}</Notice>
              {result.items.length === 0 && (
                <p>
                  No safe edits were identified for this source. Try a different
                  exact excerpt.
                </p>
              )}
              {result.items.map((item, index) => (
                <div className="suggestion-card" key={index}>
                  <Badge>
                    {item.source === "openai" ? "AI-generated" : "Rule-based"}
                  </Badge>
                  <h3>Original</h3>
                  <p className="preserve-lines">{item.original}</p>
                  <p>{item.rationale}</p>
                  <label htmlFor={`suggestion-${index}`}>
                    Review and edit suggestion {index + 1}
                  </label>
                  <textarea
                    id={`suggestion-${index}`}
                    rows={5}
                    maxLength={8000}
                    value={edits[index] ?? ""}
                    onChange={(event) =>
                      setEdits((values) =>
                        values.map((value, i) =>
                          i === index ? event.target.value : value,
                        ),
                      )
                    }
                  />
                  <Button
                    variant="secondary"
                    onClick={() => copy(edits[index])}
                  >
                    Copy reviewed suggestion
                  </Button>
                </div>
              ))}
            </>
          )}
        </Panel>
      </div>
    </>
  );
}
