"use client";
import { useEffect, useState } from "react";
import { useAuth, useWorkspace } from "./providers";
import { Badge, Button, Notice, PageHeading, Panel, TextLink } from "./ui";
import { FileUpload } from "./documents";
import { MatchView } from "./match-result";
import type { AnalysisRecord, LinkedAnalysis } from "@/lib/features";
import { date } from "@/lib/format";
const sections = [
  ["overview", "Overview"],
  ["parseability", "Parseability"],
  ["impact", "Impact"],
  ["repetition", "Repeated words"],
  ["grammar", "Grammar"],
  ["sections", "Essential sections"],
  ["contact", "Contact"],
  ["formatting", "Formatting"],
  ["match", "Job match"],
  ["skills", "Skill gaps"],
  ["templates", "Templates"],
  ["recommendations", "Recommendations"],
];
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
  const report = record && record.resume_id === resumeId ? record.report : null;
  function category(key: string) {
    const value = report?.ats.categories[key];
    return value ? (
      <>
        <h3>
          {value.name}: {value.score.toFixed(1)}/100
        </h3>
        <ul className="feature-list">
          {value.checks.map((check, index) => (
            <li key={index}>
              <Badge>{check.status}</Badge> <strong>{check.label}</strong> —{" "}
              {check.detail}
            </li>
          ))}
        </ul>
      </>
    ) : null;
  }
  const waiting = (
    <p className="muted">
      Run analysis to compute this section from your stored document.
    </p>
  );
  return (
    <>
      <PageHeading
        eyebrow="RESUME WORKSPACE"
        title="Look closer. Move forward."
        description="Detailed analysis from your actual document. Scores are documented heuristics, not ATS certification."
      />
      <div className="analyzer-intro-grid">
        <Panel>
          <h2>Add a resume</h2>
          <FileUpload onSuccess={(item) => setSelectedId(item.id)} />
        </Panel>
        <Panel>
          <h2>Analyze your document</h2>
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
            <label htmlFor="analysis-jd">Optional job description</label>
            <textarea
              id="analysis-jd"
              rows={3}
              maxLength={20000}
              disabled={busy}
              value={jd}
              onChange={(event) => setJD(event.target.value)}
            />
            <small>
              Leave empty for general analysis, or supply 30–20,000 characters.
            </small>
          </div>
          <Button
            disabled={
              !resumeId ||
              busy ||
              reading ||
              (!!jd.trim() && jd.trim().length < 30)
            }
            onClick={() => void analyze()}
          >
            {busy ? "Analyzing…" : "Run analysis"}
          </Button>
          {(busy || reading) && (
            <p role="status">
              {busy
                ? "Reading the private document and computing report sections…"
                : "Loading saved analysis…"}
            </p>
          )}
        </Panel>
      </div>
      {resumes.error && <Notice error>{resumes.error}</Notice>}
      {loadedFor === resumeId && error && <Notice error>{error}</Notice>}
      {!selected ? (
        <Notice>Add a resume to begin.</Notice>
      ) : (
        <>
          <div className="field">
            <label htmlFor="analysis-history">Saved analysis history</label>
            <select
              id="analysis-history"
              value={record?.id ?? ""}
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
          <nav className="report-nav" aria-label="Report sections">
            {sections.map(([id, label]) => (
              <a key={id} href={`#report-${id}`}>
                {label}
              </a>
            ))}
          </nav>
          <div className="report-content">
            <Panel id="report-overview" className="report-section">
              <h2>Resume overview</h2>
              <div className="metadata-grid">
                {[
                  ["Format", selected.metadata.file_type.toUpperCase()],
                  ["Word count", selected.metadata.word_count],
                  ["Pages detected", selected.metadata.pages],
                  ["Bullet points", selected.metadata.bullet_count],
                ].map(([label, value]) => (
                  <div key={label}>
                    <span>{label}</span>
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>
              {report ? (
                <>
                  <h3>
                    Estimated ATS score: {report.ats.overall.toFixed(1)}/100
                  </h3>
                  <p>{report.disclaimer}</p>
                  <h4>Strengths</h4>
                  <ul>
                    {report.ats.strengths.map((value, index) => (
                      <li key={index}>{value}</li>
                    ))}
                  </ul>
                  <h4>Areas to review</h4>
                  <ul>
                    {report.ats.weaknesses.map((value, index) => (
                      <li key={index}>{value}</li>
                    ))}
                  </ul>
                </>
              ) : (
                waiting
              )}
            </Panel>
            <Panel id="report-parseability" className="report-section">
              <h2>Estimated ATS parseability</h2>
              {report ? (
                <>
                  {Object.entries(report.ats.categories).map(([key, value]) => (
                    <p key={key}>
                      {value.name} · {value.score.toFixed(1)}/100 · weight{" "}
                      {(value.weight * 100).toFixed(0)}%
                    </p>
                  ))}
                  {category("readability")}
                  {category("structure")}
                </>
              ) : (
                waiting
              )}
            </Panel>
            <Panel id="report-impact" className="report-section">
              <h2>Quantified impact</h2>
              {report ? (
                <p>
                  {report.impact.count} of {report.impact.bullets} detected
                  bullets contain quantified evidence. Review whether each
                  number demonstrates an outcome; number detection alone does
                  not establish impact.
                </p>
              ) : (
                waiting
              )}
            </Panel>
            <Panel id="report-repetition" className="report-section">
              <h2>Repeated words</h2>
              {report ? (
                <>
                  <div className="chips">
                    {report.ats.writing.repeated_words.map(([word, total]) => (
                      <Badge key={word}>
                        {word} · {total}
                      </Badge>
                    ))}
                  </div>
                  {!report.ats.writing.repeated_words.length && (
                    <p>No repeated words flagged by the heuristic.</p>
                  )}
                </>
              ) : (
                waiting
              )}
            </Panel>
            <Panel id="report-grammar" className="report-section">
              <h2>Spelling and grammar</h2>
              {report ? (
                <>
                  {(["spelling", "grammar", "weak_phrasings"] as const).map(
                    (key) => (
                      <div key={key}>
                        <h3>{key.replaceAll("_", " ")}</h3>
                        {report.ats.writing[key].length ? (
                          report.ats.writing[key].map((issue, index) => (
                            <div className="suggestion-card" key={index}>
                              <strong>{issue.message}</strong>
                              <p>{issue.context}</p>
                              <p>{issue.suggestion}</p>
                            </div>
                          ))
                        ) : (
                          <p>No issues flagged by these limited checks.</p>
                        )}
                      </div>
                    ),
                  )}
                  <p>
                    {report.ats.writing.passive_count} possible passive
                    constructions. {report.ats.writing.long_sentences.length}{" "}
                    long sentences flagged.
                  </p>
                  {report.ats.writing.long_sentences.map((text, index) => (
                    <p key={index}>{text}</p>
                  ))}
                  <p>
                    Buzzwords:{" "}
                    {report.ats.writing.buzzwords.join(", ") || "None flagged"}
                  </p>
                  <TextLink href="/improve">
                    Review writing suggestions
                  </TextLink>
                </>
              ) : (
                waiting
              )}
            </Panel>
            <Panel id="report-sections" className="report-section">
              <h2>Essential sections</h2>
              {report ? (
                <>
                  <div className="chips">
                    {report.sections.map((value, index) => (
                      <Badge key={`${value}-${index}`}>{value}</Badge>
                    ))}
                  </div>
                  {category("completeness")}
                </>
              ) : (
                waiting
              )}
            </Panel>
            <Panel id="report-contact" className="report-section">
              <h2>Contact information</h2>
              {report ? (
                <>
                  <p>Presence checks only; contact values are excluded.</p>
                  {Object.entries(report.contact).map(([key, value]) => (
                    <p key={key}>
                      {key.replaceAll("_", " ")}:{" "}
                      {value ? "Detected" : "Not detected"}
                    </p>
                  ))}
                  {category("contact")}
                </>
              ) : (
                waiting
              )}
            </Panel>
            <Panel id="report-formatting" className="report-section">
              <h2>ATS formatting</h2>
              {report ? category("formatting") : waiting}
              <p>
                {selected.metadata.tables_detected} tables ·{" "}
                {selected.metadata.images_detected} images detected.
              </p>
            </Panel>
            <Panel id="report-match" className="report-section">
              <h2>Job description match</h2>
              {report?.job_match ? (
                <MatchView result={report.job_match} />
              ) : (
                <p>
                  Supply a job description when running analysis for a
                  role-specific comparison.{" "}
                  <TextLink href="/job-match">Open Job Match</TextLink>
                </p>
              )}
            </Panel>
            <Panel id="report-skills" className="report-section">
              <h2>Skill gaps</h2>
              {report ? (
                <>
                  {category("keywords")}
                  <p>
                    Detected resume keywords:{" "}
                    {report.keywords.join(", ") || "None detected"}
                  </p>
                  {report.job_match ? (
                    <p>
                      Missing from resume:{" "}
                      {report.job_match.missing.join(", ") || "None detected"}.
                      Only add skills you genuinely have.
                    </p>
                  ) : (
                    <p>
                      A job description is required to identify role-specific
                      gaps.
                    </p>
                  )}
                </>
              ) : (
                waiting
              )}
            </Panel>
            <Panel id="report-templates" className="report-section">
              <h2>Templates</h2>
              {report ? (
                <>
                  <p>
                    Supported single-column export choices:{" "}
                    {report.template_ids.join(", ")}. The builder shows the
                    actual server mapping.
                  </p>
                  <TextLink href="/builder">Open resume builder</TextLink>
                </>
              ) : (
                waiting
              )}
            </Panel>
            <Panel id="report-recommendations" className="report-section">
              <h2>Recommendations</h2>
              {report ? (
                <>
                  <ul className="feature-list">
                    {report.ats.recommendations.map((value, index) => (
                      <li key={index}>{value}</li>
                    ))}
                  </ul>
                  <p>{report.disclaimer}</p>
                </>
              ) : (
                waiting
              )}
            </Panel>
          </div>
        </>
      )}
    </>
  );
}
