"use client";
import { useEffect, useState, type ReactNode, type MouseEvent } from "react";
import { Check, ChevronDown, ArrowUpRight, Minus, X } from "lucide-react";
import type { AnalysisRecord } from "@/lib/features";
import type { StoredResume } from "@/lib/api";
import { date } from "@/lib/format";
import { TextLink } from "../ui";
import { MatchView } from "../match-result";

type Report = AnalysisRecord["report"];
type Category = Report["ats"]["categories"][string];
export const reportSections = [
  ["overview", "Resume overview"],
  ["parseability", "ATS parseability"],
  ["impact", "Quantified impact"],
  ["repetition", "Repeated words"],
  ["grammar", "Spelling & grammar"],
  ["sections", "Essential sections"],
  ["contact", "Contact information"],
  ["formatting", "ATS formatting"],
  ["match", "Job description match"],
  ["skills", "Skill-gap analysis"],
  ["templates", "Templates"],
  ["recommendations", "Recommendations"],
] as const;

export function ReportLoading({ creating = false }: { creating?: boolean }) {
  return (
    <div className="ar-loading" role="status" aria-live="polite">
      <div>
        <span className="ar-loading-dot" aria-hidden="true" />
        <strong>
          {creating ? "Analyzing your resume" : "Loading your report"}
        </strong>
        <p>
          {creating
            ? "Your report will appear when the analysis is complete."
            : "Retrieving your saved analysis."}
        </p>
      </div>
      <div className="ar-loading-lines" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>
    </div>
  );
}

export function ScoreSummary({ score }: { score: number }) {
  const circumference = 2 * Math.PI * 47;
  return (
    <div
      className="ar-score"
      role="meter"
      aria-label="Estimated ATS score"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={score}
      aria-valuetext={`${score.toFixed(1)} out of 100; a heuristic estimate, not certification`}
    >
      <svg viewBox="0 0 112 112" aria-hidden="true">
        <circle className="ar-score-track" cx="56" cy="56" r="47" />
        <circle
          className="ar-score-value"
          cx="56"
          cy="56"
          r="47"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - score / 100)}
        />
      </svg>
      <div aria-hidden="true">
        <strong>{score.toFixed(1)}</strong>
        <span>out of 100</span>
      </div>
    </div>
  );
}

function Section({
  id,
  title,
  description,
  summary,
  defaultExpanded = false,
  compact = false,
  children,
}: {
  id: string;
  title: string;
  description: string;
  summary?: string;
  defaultExpanded?: boolean;
  compact?: boolean;
  children: ReactNode;
}) {
  const index = reportSections.findIndex(([key]) => key === id) + 1;
  return (
    <details
      className={`ar-section${compact ? " ar-section-compact" : ""}`}
      id={`report-${id}`}
      open={defaultExpanded}
    >
      <summary>
        <span className="ar-section-number" aria-hidden="true">
          {String(index).padStart(2, "0")}
        </span>
        <span className="ar-section-label">
          <h2>{title}</h2>
          {summary && <span>{summary}</span>}
        </span>
        <ChevronDown size={18} aria-hidden="true" />
      </summary>
      <div className="ar-section-body">
        <p className="ar-section-description">{description}</p>
        {children}
      </div>
    </details>
  );
}

function EmptyFinding({ children }: { children: ReactNode }) {
  return (
    <p className="ar-empty-finding">
      <Check size={17} aria-hidden="true" />
      {children}
    </p>
  );
}

function CheckRows({ category }: { category: Category | undefined }) {
  if (!category)
    return (
      <p className="ar-note">
        No category details are included in this report.
      </p>
    );
  return category.checks.length ? (
    <ul className="ar-checks">
      {category.checks.map((item, index) => (
        <li key={index}>
          <span className={`ar-check-state ${item.status}`}>
            {item.status === "pass" ? (
              <Check size={14} aria-hidden="true" />
            ) : item.status === "fail" ? (
              <X size={14} aria-hidden="true" />
            ) : (
              <Minus size={14} aria-hidden="true" />
            )}
            {item.status === "pass"
              ? "Pass"
              : item.status === "warn"
                ? "Review"
                : "Needs attention"}
          </span>
          <div>
            <strong>{item.label}</strong>
            {item.detail && <p>{item.detail}</p>}
          </div>
        </li>
      ))}
    </ul>
  ) : (
    <p className="ar-note">
      No individual checks are included for this category.
    </p>
  );
}

function WritingFindings({ writing }: { writing: Report["ats"]["writing"] }) {
  const groups = [
    ["spelling", "Spelling"],
    ["grammar", "Grammar"],
    ["weak_phrasings", "Weak phrasing"],
  ] as const;
  return (
    <>
      {groups.map(([key, label]) => (
        <div
          className={`ar-writing-group${writing[key].length ? "" : " ar-writing-group-empty"}`}
          key={key}
        >
          <div className="ar-subheading">
            <h3>{label}</h3>
            <span>
              {writing[key].length}{" "}
              {writing[key].length === 1 ? "finding" : "findings"}
            </span>
          </div>
          {writing[key].length ? (
            <div>
              {writing[key].map((issue, index) => (
                <article className="ar-writing-finding" key={index}>
                  <h4>{issue.message}</h4>
                  {issue.context && (
                    <>
                      <span className="ar-field-caption">Original excerpt</span>
                      <blockquote>{issue.context}</blockquote>
                    </>
                  )}
                  {issue.suggestion && (
                    <>
                      <span className="ar-field-caption">Suggested edit</span>
                      <p className="ar-edit">{issue.suggestion}</p>
                    </>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <EmptyFinding>
              No {label.toLowerCase()} issues flagged by these checks.
            </EmptyFinding>
          )}
        </div>
      ))}
      <div className="ar-writing-notes">
        <p>
          <strong>{writing.passive_count}</strong> possible passive
          constructions · <strong>{writing.long_sentences.length}</strong> long
          sentences flagged
        </p>
        {writing.long_sentences.length > 0 && (
          <details>
            <summary>Review long sentences</summary>
            <ul>
              {writing.long_sentences.map((value, index) => (
                <li key={index}>{value}</li>
              ))}
            </ul>
          </details>
        )}
        {writing.buzzwords.length > 0 && (
          <p>Flagged buzzwords: {writing.buzzwords.join(", ")}</p>
        )}
      </div>
      <p className="ar-note">
        Automated checks are limited. Review each suggestion in context before
        editing.
      </p>
      <TextLink href="/improve">Review writing suggestions</TextLink>
    </>
  );
}

export function AnalysisReport({
  record,
  resume,
}: {
  record: AnalysisRecord;
  resume: StoredResume;
}) {
  const report = record.report;
  const [active, setActive] = useState("overview");
  const [destination, setDestination] = useState("overview");
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id.replace("report-", ""));
      },
      { rootMargin: "-150px 0px -55% 0px", threshold: 0 },
    );
    reportSections.forEach(([id]) => {
      const target = document.getElementById(`report-${id}`);
      if (target) observer.observe(target);
    });
    return () => observer.disconnect();
  }, [record.id]);
  function navigate(event: MouseEvent<HTMLAnchorElement>, id: string) {
    if (
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      event.button !== 0
    )
      return;
    event.preventDefault();
    showSection(id);
  }
  function showSection(id: string) {
    const target = document.getElementById(`report-${id}`);
    if (target instanceof HTMLDetailsElement) {
      target.open = true;
      target.querySelector("summary")?.focus({ preventScroll: true });
    } else {
      target?.querySelector<HTMLElement>("h2")?.focus({ preventScroll: true });
    }
    setActive(id);
    target?.scrollIntoView?.({
      block: "start",
      behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
    window.history.replaceState(window.history.state, "", `#report-${id}`);
  }
  const writing = report.ats.writing;
  const writingCount =
    writing.spelling.length +
    writing.grammar.length +
    writing.weak_phrasings.length;
  return (
    <div className="ar-report-layout">
      <aside className="ar-sidebar" aria-label="Analysis summary">
        <div className="ar-sidebar-score">
          <p>Estimated ATS score</p>
          <ScoreSummary score={report.ats.overall} />
          <p className="ar-note">
            A heuristic estimate.
            <br /> Not an ATS certification.
          </p>
        </div>
        <form
          className="ar-mobile-nav"
          onSubmit={(event) => {
            event.preventDefault();
            showSection(destination);
          }}
        >
          <label htmlFor="report-section-destination">
            Jump to report section
          </label>
          <div>
            <select
              id="report-section-destination"
              value={destination}
              onChange={(event) => setDestination(event.target.value)}
            >
              {reportSections.map(([id, label], index) => (
                <option key={id} value={id}>
                  {String(index + 1).padStart(2, "0")} · {label}
                </option>
              ))}
            </select>
            <button
              type="submit"
              className="button secondary"
              aria-label="Go to selected report section"
            >
              Go
            </button>
          </div>
        </form>
        <nav className="ar-section-nav" aria-label="Report sections">
          {reportSections.map(([id, label], index) => (
            <a
              key={id}
              href={`#report-${id}`}
              aria-current={active === id ? "location" : undefined}
              onClick={(event) => navigate(event, id)}
            >
              <span className="ar-nav-index" aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span>{label}</span>
              <span className="ar-nav-marker" aria-hidden="true" />
            </a>
          ))}
        </nav>
        <p className="ar-sidebar-date">
          Saved {date(record.created_at)}
          <br />
          {record.id.slice(0, 8)}
        </p>
      </aside>
      <div className="ar-report-content">
        <section
          id="report-overview"
          className="ar-overview"
          aria-labelledby="report-overview-title"
        >
          <div className="ar-report-title">
            <div>
              <span className="ar-field-caption">Your analysis</span>
              <h2 id="report-overview-title" tabIndex={-1}>
                Resume overview
              </h2>
            </div>
            <span className="ar-report-date">{date(record.created_at)}</span>
          </div>
          <h3 className="sr-only">
            Estimated ATS score: {report.ats.overall.toFixed(1)}/100
          </h3>
          <p className="ar-overview-intro">
            A closer look at your document’s structure, language and relevance.
            Use these findings to guide your next edit.
          </p>
          <dl className="ar-document-facts">
            {[
              ["Format", resume.metadata.file_type.toUpperCase()],
              ["Words", resume.metadata.word_count],
              ["Pages", resume.metadata.pages],
              ["Bullets", resume.metadata.bullet_count],
            ].map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          <div className="ar-overview-findings">
            <div>
              <h3>
                <span className="ar-status-dot good" />
                Strengths
              </h3>
              {report.ats.strengths.length ? (
                <ul>
                  {report.ats.strengths.map((value, index) => (
                    <li key={index}>{value}</li>
                  ))}
                </ul>
              ) : (
                <p className="ar-note">No specific strengths were returned.</p>
              )}
            </div>
            <div>
              <h3>
                <span className="ar-status-dot review" />
                Areas to review
              </h3>
              {report.ats.weaknesses.length ? (
                <ul>
                  {report.ats.weaknesses.map((value, index) => (
                    <li key={index}>{value}</li>
                  ))}
                </ul>
              ) : (
                <EmptyFinding>
                  No improvement areas flagged in this report.
                </EmptyFinding>
              )}
            </div>
          </div>
          <p className="ar-disclaimer">{report.disclaimer}</p>
        </section>
        <Section
          id="parseability"
          defaultExpanded
          title="Estimated ATS parseability"
          description="The score combines weighted checks of your document. Category scores are estimates, not a measurement of what an employer’s ATS has read."
          summary={`${Object.keys(report.ats.categories).length} weighted categories`}
        >
          <div className="ar-categories">
            {Object.entries(report.ats.categories).map(([key, value]) => (
              <details className="ar-category" key={key}>
                <summary>
                  <span>
                    <strong>{value.name}</strong>
                    <small>{(value.weight * 100).toFixed(0)}% weight</small>
                  </span>
                  <span className="ar-category-score">
                    {value.score.toFixed(1)}
                    <small>/100</small>
                  </span>
                  <ChevronDown size={15} aria-hidden="true" />
                </summary>
                <div className="ar-category-bar" aria-hidden="true">
                  <span style={{ width: `${value.score}%` }} />
                </div>
                <div className="ar-category-checks">
                  <CheckRows category={value} />
                </div>
              </details>
            ))}
          </div>
        </Section>
        <Section
          id="impact"
          compact={report.impact.bullets === 0}
          title="Quantified impact"
          description="Numbers can make a contribution more concrete. This check detects quantified evidence; it does not establish whether a number demonstrates an achievement."
          summary={`${report.impact.count} of ${report.impact.bullets} bullets contain numbers`}
        >
          <div className="ar-impact-counts">
            <div>
              <strong>{report.impact.count}</strong>
              <span>With quantified evidence</span>
            </div>
            <span className="ar-impact-divider" aria-hidden="true">
              /
            </span>
            <div>
              <strong>{report.impact.bullets}</strong>
              <span>Bullets detected</span>
            </div>
          </div>
          {report.impact.bullets > 0 ? (
            <div
              className="ar-impact-bar"
              role="meter"
              aria-label="Bullets containing quantified evidence"
              aria-valuemin={0}
              aria-valuemax={report.impact.bullets}
              aria-valuenow={Math.min(
                report.impact.count,
                report.impact.bullets,
              )}
            >
              <span
                style={{
                  width: `${Math.min(100, (report.impact.count / report.impact.bullets) * 100)}%`,
                }}
              />
            </div>
          ) : (
            <p className="ar-note">
              No bullet points were detected for this check.
            </p>
          )}
          <p className="ar-note">
            This report provides aggregate counts, not a bullet-by-bullet
            review. Check your original document for the context behind each
            number.
          </p>
        </Section>
        <Section
          id="repetition"
          compact={!writing.repeated_words.length}
          title="Repeated words and vocabulary"
          description="Notice recurring language before changing it. Repeating a relevant skill can be useful; repeated general wording may deserve another look."
          summary={`${writing.repeated_words.length} repeated terms`}
        >
          {writing.repeated_words.length ? (
            <>
              <table className="ar-word-table">
                <caption className="sr-only">
                  Repeated words and their observed frequencies
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Word</th>
                    <th scope="col">Occurrences</th>
                  </tr>
                </thead>
                <tbody>
                  {writing.repeated_words.map(([word, total]) => (
                    <tr key={word}>
                      <th scope="row">{word}</th>
                      <td>
                        <span>{total}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="ar-note">
                Counts only. Contextual replacement suggestions are not included
                in this report.
              </p>
            </>
          ) : (
            <EmptyFinding>
              No repeated terms were flagged by the word-frequency check.
            </EmptyFinding>
          )}
        </Section>
        <Section
          id="grammar"
          defaultExpanded={writingCount > 0}
          compact={
            writingCount === 0 &&
            !writing.long_sentences.length &&
            !writing.passive_count &&
            !writing.buzzwords.length
          }
          title="Spelling and grammar"
          description="Review the original context alongside each available correction. Keep any edit faithful to your experience."
          summary={`${writingCount} writing ${writingCount === 1 ? "finding" : "findings"}`}
        >
          <WritingFindings writing={writing} />
        </Section>
        <Section
          id="sections"
          title="Essential sections"
          description="Section headings help a reader find the parts of your story. These labels are recognized heuristically, not verified completeness."
          summary={`${report.sections.length} section labels detected`}
        >
          {report.sections.length ? (
            <ul className="ar-tags" aria-label="Detected section labels">
              {report.sections.map((value, index) => (
                <li key={index}>{value.replaceAll("_", " ")}</li>
              ))}
            </ul>
          ) : (
            <p className="ar-note">
              No canonical section headings were recognized.
            </p>
          )}
          <CheckRows category={report.ats.categories.completeness} />
        </Section>
        <Section
          id="contact"
          title="Contact information"
          description="Presence checks help you spot missing contact details. Your actual contact values are kept out of this view."
        >
          <dl className="ar-contact-list">
            {Object.entries(report.contact).map(([key, value]) => (
              <div key={key}>
                <dt>{key.replaceAll("_", " ")}</dt>
                <dd className={value ? "present" : "absent"}>
                  {value ? (
                    <Check size={15} aria-hidden="true" />
                  ) : (
                    <Minus size={15} aria-hidden="true" />
                  )}
                  {value ? "Detected" : "Not detected"}
                </dd>
              </div>
            ))}
          </dl>
          <CheckRows category={report.ats.categories.contact} />
        </Section>
        <Section
          id="formatting"
          title="ATS formatting"
          description="Review the document features that can affect extraction. These are useful checks, not a guarantee of compatibility."
        >
          <div className="ar-format-facts">
            <span>
              <strong>{resume.metadata.tables_detected}</strong> tables detected
            </span>
            <span>
              <strong>{resume.metadata.images_detected}</strong> images detected
            </span>
            <span>
              Capitalized headings:{" "}
              <strong>
                {resume.metadata.headings_look_caps
                  ? "detected"
                  : "not flagged"}
              </strong>
            </span>
          </div>
          <CheckRows category={report.ats.categories.formatting} />
        </Section>
        <Section
          id="match"
          compact={!report.job_match}
          title="Job description match"
          description="Compare the document with the role description supplied for this analysis. Alignment uses skill and keyword heuristics."
        >
          {report.job_match ? (
            <MatchView result={report.job_match} />
          ) : (
            <div className="ar-context-empty">
              <h3>Add the role for a focused comparison</h3>
              <p>
                Include a job description the next time you run analysis, or
                compare your resume in Job Match.
              </p>
              <TextLink href="/job-match">Open Job Match</TextLink>
            </div>
          )}
        </Section>
        <Section
          id="skills"
          title="Skill-gap analysis"
          description="A missing term is a prompt to review your fit, not a suggestion to claim a skill you do not have."
        >
          <CheckRows category={report.ats.categories.keywords} />
          <h3>Detected resume keywords</h3>
          {report.keywords.length ? (
            <ul className="ar-tags">
              {report.keywords.map((value, index) => (
                <li key={index}>{value}</li>
              ))}
            </ul>
          ) : (
            <p className="ar-note">No resume keywords were detected.</p>
          )}
          {report.job_match ? (
            <div className="ar-skill-gaps">
              <h3>Job skills not detected</h3>
              {report.job_match.missing.length ? (
                <ul className="ar-tags gaps">
                  {report.job_match.missing.map((value, index) => (
                    <li key={index}>{value}</li>
                  ))}
                </ul>
              ) : (
                <EmptyFinding>
                  No missing skills flagged by this comparison.
                </EmptyFinding>
              )}
              {report.job_match.partial.length > 0 && (
                <p>
                  Related, rather than exact matches:{" "}
                  {report.job_match.partial.join(", ")}.
                </p>
              )}
            </div>
          ) : (
            <p className="ar-note">
              A role description is needed to identify job-specific gaps.
            </p>
          )}
        </Section>
        <Section
          id="templates"
          compact={!report.template_ids.length}
          title="Templates"
          description="Explore the report’s supported single-column export choices. Browser previews and generated documents may differ in typography and pagination."
        >
          {report.template_ids.length ? (
            <div className="ar-template-list">
              {report.template_ids.map((id) => (
                <a href="/builder" key={id}>
                  <span>{id.replaceAll("_", " ")}</span>
                  <ArrowUpRight size={17} aria-hidden="true" />
                  <small>View in resume builder</small>
                </a>
              ))}
            </div>
          ) : (
            <p className="ar-note">No template choices were included.</p>
          )}
        </Section>
        <Section
          id="recommendations"
          defaultExpanded={report.ats.recommendations.length > 0}
          compact={!report.ats.recommendations.length}
          title="Final recommendations"
          description="Use these report recommendations to plan your next edit. They are shown in report order; no priority ranking was supplied."
          summary={`${report.ats.recommendations.length} recommendations`}
        >
          {report.ats.recommendations.length ? (
            <ol className="ar-recommendations">
              {report.ats.recommendations.map((value, index) => (
                <li key={index}>
                  <span aria-hidden="true">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <p>{value}</p>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyFinding>
              No additional recommendations were returned by this analysis.
            </EmptyFinding>
          )}
          <p className="ar-disclaimer">{report.disclaimer}</p>
        </Section>
        <p className="ar-report-end">
          End of report <span aria-hidden="true">·</span> Saved{" "}
          {date(record.created_at)}
        </p>
      </div>
    </div>
  );
}
