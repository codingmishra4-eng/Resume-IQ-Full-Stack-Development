"use client";
import { useState } from "react";
import {
  ArrowRight,
  Check,
  Clipboard,
  ListChecks,
  Sparkles,
  Target,
} from "lucide-react";
import { useWorkspace } from "./providers";
import {
  Badge,
  Button,
  IntegrationNotice,
  Notice,
  PageHeading,
  Panel,
  TextLink,
  useToast,
} from "./ui";
import { date } from "@/lib/format";
export function JobMatch() {
  const { resumes } = useWorkspace();
  const [selected, setSelected] = useState("");
  const [description, setDescription] = useState("");
  const toast = useToast();
  return (
    <>
      <PageHeading
        eyebrow="ROLE ALIGNMENT"
        title="Find the connection."
        description="Bring your resume and target role into the same conversation."
      />
      <div className="workflow-grid">
        <Panel>
          <div className="section-heading">
            <div>
              <h2>Your target role</h2>
              <p>Prepare the context for a focused comparison.</p>
            </div>
            <span className="feature-icon small">
              <Target size={20} />
            </span>
          </div>
          <div className="field">
            <label htmlFor="match-resume">Choose your resume</label>
            <select
              id="match-resume"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
            >
              <option value="">Select a stored resume</option>
              {resumes.data?.map((item) => (
                <option value={item.id} key={item.id}>
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
          <div className="field">
            <div className="label-row">
              <label htmlFor="job-description">Job description</label>
              <span>{description.length.toLocaleString()} characters</span>
            </div>
            <textarea
              id="job-description"
              rows={12}
              maxLength={30000}
              placeholder="Paste the role description, responsibilities and required skills…"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
          <div className="editor-actions">
            <Button
              variant="secondary"
              disabled={!description}
              onClick={() => {
                void navigator.clipboard
                  .writeText(description)
                  .then(() => toast("Job description copied."))
                  .catch(() =>
                    toast("Copy is unavailable in this browser.", true),
                  );
              }}
            >
              <Clipboard size={16} /> Copy draft
            </Button>
            <Button disabled>
              Compare resumes <ArrowRight size={16} />
            </Button>
          </div>
        </Panel>
        <div className="workflow-right">
          <Panel className="result-placeholder">
            <div className="section-heading">
              <h2>Match overview</h2>
              <Badge tone="violet">Not generated</Badge>
            </div>
            <div className="empty-match">
              <Target size={38} strokeWidth={1} />
              <h3>A meaningful match needs real evidence.</h3>
              <p>
                We’ll compare the actual skills in your resume with the role. No
                percentage or skill-gap result has been generated.
              </p>
            </div>
            <div className="result-slot">
              <Check size={16} />
              <span>Matching skills</span>
              <span>Awaiting comparison</span>
            </div>
            <div className="result-slot">
              <ListChecks size={16} />
              <span>Missing skills</span>
              <span>Awaiting comparison</span>
            </div>
          </Panel>
          <IntegrationNotice title="Cloud matching is the next connection.">
            Resume selection and this job-description draft are ready. The
            comparison engine is available in the local app, but its cloud
            integration has not been added.
          </IntegrationNotice>
        </div>
      </div>
    </>
  );
}
export function Improve() {
  const [mode, setMode] = useState<"summary" | "bullets">("summary");
  const [drafts, setDrafts] = useState({ summary: "", bullets: "" });
  const toast = useToast();
  const draft = drafts[mode];
  return (
    <>
      <PageHeading
        eyebrow="WORDS WITH PURPOSE"
        title="Make your work speak clearly."
        description="Prepare the experience you want to articulate. Keep every claim grounded in what you actually did."
      />
      <div className="pill-tabs mb-6" aria-label="Writing mode">
        <Button
          variant="ghost"
          aria-pressed={mode === "summary"}
          onClick={() => setMode("summary")}
        >
          Professional summary
        </Button>
        <Button
          variant="ghost"
          aria-pressed={mode === "bullets"}
          onClick={() => setMode("bullets")}
        >
          Experience bullets
        </Button>
      </div>
      <div className="writing-grid">
        <Panel>
          <div className="section-heading">
            <div>
              <span className="eyebrow">YOUR WORDS</span>
              <h2>
                {mode === "summary"
                  ? "Professional summary"
                  : "Experience bullet points"}
              </h2>
            </div>
            <Badge>Original draft</Badge>
          </div>
          <label className="sr-only" htmlFor="original-draft">
            Original {mode === "summary" ? "summary" : "bullet points"}
          </label>
          <textarea
            id="original-draft"
            className="writing-editor"
            rows={14}
            maxLength={15000}
            placeholder={
              mode === "summary"
                ? "Start with who you are, the work you do, and the strengths you can support with experience…"
                : "Paste the bullet points you’d like to improve. Include only genuine responsibilities and results…"
            }
            value={draft}
            onChange={(event) =>
              setDrafts((value) => ({ ...value, [mode]: event.target.value }))
            }
          />
          <div className="editor-actions">
            <span className="muted text-sm">
              {draft.length.toLocaleString()} characters · Browser-tab draft
            </span>
            <Button
              variant="ghost"
              disabled={!draft}
              onClick={() => setDrafts((value) => ({ ...value, [mode]: "" }))}
            >
              Clear
            </Button>
          </div>
        </Panel>
        <Panel className="improvement-result">
          <div className="section-heading">
            <div>
              <span className="eyebrow">A CLEARER VERSION</span>
              <h2>Thoughtful improvements</h2>
            </div>
            <Sparkles size={20} />
          </div>
          <IntegrationNotice title="No rewrite has been generated.">
            Cloud writing assistance is not connected yet. This space will show
            an actual before-and-after rewrite with its source and rationale,
            rather than a fabricated suggestion.
          </IntegrationNotice>
          <div className="writing-principles">
            <p>
              <Check size={15} /> No invented employers, skills or metrics
            </p>
            <p>
              <Check size={15} /> Suggestions you can review and edit
            </p>
            <p>
              <Check size={15} /> Clear labeling of AI and rule-based output
            </p>
          </div>
          <Button
            variant="secondary"
            disabled={!draft}
            onClick={() => {
              void navigator.clipboard
                .writeText(draft)
                .then(() => toast("Original draft copied."))
                .catch(() =>
                  toast("Copy is unavailable in this browser.", true),
                );
            }}
          >
            <Clipboard size={16} /> Copy original draft
          </Button>
        </Panel>
      </div>
    </>
  );
}
