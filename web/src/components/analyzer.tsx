"use client";
import { useEffect, useState } from "react";
import { useAuth, useWorkspace } from "./providers";
import { Button, Notice, TextLink } from "./ui";
import { FileText, ChevronDown, ArrowUpRight } from "lucide-react";
import { AnalysisReport, ReportLoading } from "./analysis/report";
import "./analysis/analyzer.css";
import { FileUpload } from "./documents";
import type { AnalysisRecord, LinkedAnalysis } from "@/lib/features";
import { date } from "@/lib/format";
export function Analyzer() {
  const { api } = useAuth();
  const { resumes, refresh } = useWorkspace();
  const [selectedId, setSelectedId] = useState(""),
    [jd, setJD] = useState(""),
    [busy, setBusy] = useState(false),
    [readingState, setReading] = useState(false),
    [error, setError] = useState("");
  const [records, setRecords] = useState<LinkedAnalysis[]>([]),
    [record, setRecord] = useState<AnalysisRecord | null>(null);
  const selected =
    resumes.data?.find((item) => item.id === selectedId) ?? resumes.data?.[0];
  const resumeId = selected?.id;
  const [loadedFor, setLoadedFor] = useState<string | undefined>();
  const reading = readingState || loadedFor !== resumeId;
  useEffect(() => {
    const controller = new AbortController();
    if (!resumeId) return;
    void api
      .resumeAnalyses(resumeId, controller.signal)
      .then(async (rows) => {
        if (controller.signal.aborted) return;
        setRecords(rows);
        setRecord(null);
        setError("");
        if (rows[0]) {
          const value = await api.report(rows[0].id, controller.signal);
          if (!controller.signal.aborted) setRecord(value);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted)
          setError(e instanceof Error ? e.message : "History unavailable.");
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setReading(false);
          setLoadedFor(resumeId);
        }
      });
    return () => controller.abort();
  }, [api, resumeId]);
  async function analyze() {
    if (!resumeId) return;
    setBusy(true);
    setError("");
    try {
      const value = await api.createAnalysis(resumeId, jd);
      setRecord(value);
      setRecords((rows) => [
        {
          id: value.id,
          resume_id: value.resume_id,
          created_at: value.created_at,
          ats_score: value.report.ats.overall,
        },
        ...rows,
      ]);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis unavailable.");
    } finally {
      setBusy(false);
    }
  }
  async function load(id: string) {
    setReading(true);
    setError("");
    try {
      setRecord(await api.report(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Report unavailable.");
    } finally {
      setReading(false);
    }
  }
  const currentRecord = record && record.resume_id === resumeId ? record : null;
  return (
    <div className="analyzer-workspace">
      <header className="ar-page-header">
        <div>
          <span className="ar-page-context">
            Resume workspace <span aria-hidden="true">/</span> Analyzer
          </span>
          <h1>Understand your resume.</h1>
          <p>A clearer view of your document, and what to refine next.</p>
        </div>
        <TextLink href="/documents">Your documents</TextLink>
      </header>
      {!selected && (
        <section className="ar-upload-start">
          <span className="ar-file-symbol">
            <FileText size={25} aria-hidden="true" />
          </span>
          <h2>Start with your document</h2>
          <p>Upload a PDF or DOCX to get a private, document-based analysis.</p>
          <FileUpload onSuccess={(item) => setSelectedId(item.id)} />
        </section>
      )}
      {selected && (
        <section
          className="ar-controls"
          aria-busy={busy || reading}
          aria-labelledby="analysis-controls-title"
        >
          <div className="ar-selected-document">
            <div className="ar-document-name">
              <span className="ar-file-symbol">
                <FileText size={20} aria-hidden="true" />
              </span>
              <div>
                <h2 id="analysis-controls-title">
                  {selected.metadata.file_name}
                </h2>
                <p>
                  {selected.metadata.file_type.toUpperCase()}{" "}
                  <span aria-hidden="true">·</span>{" "}
                  {selected.metadata.word_count.toLocaleString()} words{" "}
                  <span aria-hidden="true">·</span> {selected.metadata.pages}{" "}
                  {selected.metadata.pages === 1 ? "page" : "pages"}
                </p>
              </div>
            </div>
            <details className="ar-upload-another">
              <summary>
                Upload another resume{" "}
                <ChevronDown size={15} aria-hidden="true" />
              </summary>
              <fieldset disabled={busy || reading}>
                <FileUpload onSuccess={(item) => setSelectedId(item.id)} />
              </fieldset>
            </details>
          </div>
          <div className="ar-control-fields">
            <div className="field">
              <label htmlFor="analysis-resume">Resume to review</label>
              <select
                id="analysis-resume"
                value={resumeId ?? ""}
                disabled={busy || reading || !resumes.data?.length}
                onChange={(event) => setSelectedId(event.target.value)}
              >
                <option value="" disabled>
                  Select a resume
                </option>
                {resumes.data?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.metadata.file_name} · {date(item.created_at)} ·{" "}
                    {item.id.slice(0, 6)}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="analysis-history">Saved analysis history</label>
              <select
                id="analysis-history"
                value={record && record.resume_id === resumeId ? record.id : ""}
                disabled={busy || reading || !records.length}
                onChange={(event) => void load(event.target.value)}
              >
                <option value="" disabled>
                  {records.length
                    ? "Select a saved report"
                    : "No saved analysis yet"}
                </option>
                {records
                  .filter((item) => item.resume_id === resumeId)
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {date(item.created_at)} ·{" "}
                      {item.ats_score?.toFixed(1) ?? "No score"} ·{" "}
                      {item.id.slice(0, 6)}
                    </option>
                  ))}
              </select>
            </div>
            <Button
              className="ar-run-button"
              disabled={
                !resumeId ||
                busy ||
                reading ||
                (!!jd.trim() && jd.trim().length < 30)
              }
              onClick={() => void analyze()}
            >
              {busy ? "Analyzing…" : "Run analysis"}
              {!busy && <ArrowUpRight size={16} aria-hidden="true" />}
            </Button>
          </div>
          <details className="ar-job-context">
            <summary>
              Add a job description <span>(optional)</span>
              <ChevronDown size={15} aria-hidden="true" />
            </summary>
            <div className="field">
              <label htmlFor="analysis-jd">Optional job description</label>
              <textarea
                id="analysis-jd"
                rows={4}
                maxLength={20000}
                disabled={busy}
                value={jd}
                onChange={(event) => setJD(event.target.value)}
                placeholder="Paste a target role to include job matching and skill-gap findings."
              />
              <small>
                30–20,000 characters, or leave empty for general analysis.
              </small>
            </div>
          </details>
        </section>
      )}
      {resumes.error && <Notice error>{resumes.error}</Notice>}
      {loadedFor === resumeId && error && <Notice error>{error}</Notice>}
      {(busy || reading) && selected && <ReportLoading creating={busy} />}
      {selected && currentRecord ? (
        <AnalysisReport
          key={currentRecord.id}
          record={currentRecord}
          resume={selected}
        />
      ) : selected && !reading && !busy ? (
        <section className="ar-report-empty">
          <span className="ar-field-caption">Your next step</span>
          <h2>Ready for a closer look?</h2>
          <p>
            Run an analysis to see your estimated ATS score, writing findings
            and recommendations here.
          </p>
          <p className="ar-note">
            Only results calculated from your document will appear. Your
            original file stays unchanged.
          </p>
        </section>
      ) : null}
      {!selected && resumes.data === null && <ReportLoading />}
    </div>
  );
}
