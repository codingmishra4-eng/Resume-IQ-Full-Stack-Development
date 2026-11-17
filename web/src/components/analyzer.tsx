"use client";
import { useState } from "react";
import { Check, FileText, ScanText } from "lucide-react";
import { useWorkspace } from "./providers";
import {
  Badge,
  EmptyState,
  IntegrationNotice,
  Notice,
  PageHeading,
  Panel,
  Skeleton,
  TextLink,
} from "./ui";
import { FileUpload } from "./documents";
import { count, date } from "@/lib/format";
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
  const { resumes, loading } = useWorkspace();
  const [selectedId, setSelectedId] = useState("");
  const selected =
    resumes.data?.find((item) => item.id === selectedId) ?? resumes.data?.[0];
  const [active, setActive] = useState("overview");
  const gap = (title: string, description: string) => (
    <IntegrationNotice title={title}>{description}</IntegrationNotice>
  );
  return (
    <>
      <PageHeading
        eyebrow="RESUME WORKSPACE"
        title="Look closer. Move forward."
        description="Start with your document. Build a clearer picture of the story it tells."
      />
      <div className="analyzer-intro-grid">
        <Panel>
          <div className="section-heading">
            <div>
              <h2>Add a resume</h2>
              <p>A new version, a new perspective.</p>
            </div>
            <Badge tone="mint">Private upload</Badge>
          </div>
          <FileUpload onSuccess={(item) => setSelectedId(item.id)} />
        </Panel>
        <Panel className="analyzer-guide">
          <span className="feature-icon">
            <ScanText size={28} />
          </span>
          <h2>Clarity before complexity.</h2>
          <p>
            Review extracted document metadata now. Detailed scoring, writing
            feedback and role comparisons will connect in the next phase.
          </p>
          <ul className="check-list">
            <li>
              <Check size={15} /> Real documents, securely stored
            </li>
            <li>
              <Check size={15} /> Metadata from your actual file
            </li>
            <li>
              <Check size={15} /> No invented scores or recommendations
            </li>
          </ul>
          <TextLink href="/documents">Manage your documents</TextLink>
        </Panel>
      </div>
      <div className="report-heading">
        <div>
          <span className="eyebrow">DOCUMENT REVIEW</span>
          <h2>Your resume, at a glance</h2>
        </div>
        <label className="resume-select">
          <span className="sr-only">Resume to review</span>
          <select
            value={selected?.id ?? ""}
            onChange={(event) => setSelectedId(event.target.value)}
            disabled={!resumes.data?.length}
          >
            <option value="" disabled>
              Select a resume
            </option>
            {resumes.data?.map((item) => (
              <option value={item.id} key={item.id}>
                {item.metadata.file_name} · {date(item.created_at)} ·{" "}
                {item.id.slice(0, 6)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {resumes.error ? (
        <Notice error>{resumes.error}</Notice>
      ) : loading && !resumes.data ? (
        <Skeleton rows={4} />
      ) : !selected ? (
        <Panel>
          <EmptyState
            icon={<FileText size={25} />}
            title="Add a resume to begin."
          >
            Your document overview will appear here after uploading. Detailed
            cloud analysis is not connected yet.
          </EmptyState>
        </Panel>
      ) : (
        <>
          <nav className="report-nav" aria-label="Report sections">
            {sections.map(([id, label]) => (
              <a
                href={`#report-${id}`}
                key={id}
                onClick={() => setActive(id)}
                aria-current={active === id ? "location" : undefined}
              >
                {label}
              </a>
            ))}
          </nav>
          <div className="report-layout">
            <div className="report-content">
              <Panel id="report-overview" className="report-section">
                <div className="section-heading">
                  <div>
                    <span className="section-number">01 / DOCUMENT</span>
                    <h2>Resume overview</h2>
                  </div>
                  <Badge tone="mint">From your document</Badge>
                </div>
                <div className="metadata-grid">
                  <div>
                    <span>Format</span>
                    <strong>{selected.metadata.file_type.toUpperCase()}</strong>
                  </div>
                  <div>
                    <span>Word count</span>
                    <strong>{count(selected.metadata.word_count)}</strong>
                  </div>
                  <div>
                    <span>Pages detected</span>
                    <strong>{selected.metadata.pages}</strong>
                  </div>
                  <div>
                    <span>Bullet points</span>
                    <strong>{selected.metadata.bullet_count}</strong>
                  </div>
                </div>
                <p className="muted text-sm">
                  Uploaded {date(selected.created_at)}. The display name is
                  generated to protect your original filename.
                </p>
              </Panel>
              <Panel id="report-parseability" className="report-section">
                <span className="section-number">02 / ESTIMATED SCORE</span>
                <h2>Estimated ATS parseability</h2>
                {gap(
                  "A score needs a complete analysis.",
                  "Document upload does not generate an ATS score. Cloud analysis is not connected yet, so no estimate is shown for this resume.",
                )}
              </Panel>
              <Panel id="report-impact" className="report-section">
                <span className="section-number">03 / IMPACT</span>
                <h2>Quantified impact</h2>
                {gap(
                  "Make your contribution concrete.",
                  "Impact checks will look for measurable outcomes in your actual experience. No resume text or fabricated metrics are displayed here.",
                )}
              </Panel>
              <Panel id="report-repetition" className="report-section">
                <span className="section-number">04 / LANGUAGE</span>
                <h2>Repeated words</h2>
                {gap(
                  "Every word can earn its place.",
                  "Word-frequency feedback requires the detailed cloud report. Your upload metadata does not include this analysis.",
                )}
              </Panel>
              <Panel id="report-grammar" className="report-section">
                <span className="section-number">05 / WRITING</span>
                <h2>Spelling and grammar</h2>
                {gap(
                  "Polish the details.",
                  "Writing feedback will appear when cloud language checks are available. No issues have been inferred from metadata.",
                )}
              </Panel>
              <Panel id="report-sections" className="report-section">
                <span className="section-number">06 / STRUCTURE</span>
                <h2>Essential sections</h2>
                <p className="muted">
                  Section labels recognized by the parser. Recognition is
                  heuristic and is not a completeness score.
                </p>
                {selected.metadata.section_order.length ? (
                  <div className="chips">
                    {selected.metadata.section_order.map((name, index) => (
                      <Badge key={`${name}-${index}`}>
                        {name.replaceAll("_", " ")}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="muted">
                    No canonical section labels were detected.
                  </p>
                )}
              </Panel>
              <Panel id="report-contact" className="report-section">
                <span className="section-number">07 / CONTACT</span>
                <h2>Contact information</h2>
                {gap(
                  "Your details stay private.",
                  "Contact data is intentionally excluded from the document metadata. Detailed validation needs a separate secure report integration.",
                )}
              </Panel>
              <Panel id="report-formatting" className="report-section">
                <span className="section-number">08 / FORMAT</span>
                <h2>ATS formatting</h2>
                <div className="metadata-grid">
                  <div>
                    <span>Tables detected</span>
                    <strong>{selected.metadata.tables_detected}</strong>
                  </div>
                  <div>
                    <span>Images detected</span>
                    <strong>{selected.metadata.images_detected}</strong>
                  </div>
                  <div>
                    <span>Capitalized headings</span>
                    <strong>
                      {selected.metadata.headings_look_caps
                        ? "Detected"
                        : "Not flagged"}
                    </strong>
                  </div>
                </div>
                <p className="muted text-sm">
                  These are extraction facts, not a formatting score or a
                  guarantee of ATS compatibility.
                </p>
              </Panel>
              <Panel id="report-match" className="report-section">
                <span className="section-number">09 / RELEVANCE</span>
                <h2>Job description match</h2>
                {gap(
                  "Connect your story to a role.",
                  "Prepare a target description in Job Match. Cloud comparisons will be connected in the next phase.",
                )}
                <TextLink href="/job-match">Open Job Match</TextLink>
              </Panel>
              <Panel id="report-skills" className="report-section">
                <span className="section-number">10 / SKILLS</span>
                <h2>Skill-gap analysis</h2>
                {gap(
                  "Focus on genuine skill alignment.",
                  "Matched and missing skills need a real resume-to-role comparison. No skill list has been invented.",
                )}
              </Panel>
              <Panel id="report-templates" className="report-section">
                <span className="section-number">11 / PRESENTATION</span>
                <h2>Templates</h2>
                <p className="muted">
                  Try the local draft builder to explore clean layouts. PDF and
                  DOCX generation require the next backend integration.
                </p>
                <TextLink href="/builder">Explore the builder</TextLink>
              </Panel>
              <Panel id="report-recommendations" className="report-section">
                <span className="section-number">12 / NEXT STEPS</span>
                <h2>Final recommendations</h2>
                {gap(
                  "Recommendations should come from evidence.",
                  "Detailed recommendations are not generated by document upload. This section will use the actual analysis report when available.",
                )}
              </Panel>
            </div>
            <aside className="report-summary panel">
              <span className="file-icon">
                <FileText size={23} />
              </span>
              <h3>{selected.metadata.file_name}</h3>
              <p>
                {selected.metadata.file_type.toUpperCase()} ·{" "}
                {count(selected.metadata.word_count)} words
              </p>
              <Badge tone="mint">Private document</Badge>
              <hr />
              <span className="eyebrow">REVIEW STATUS</span>
              <strong>Metadata available</strong>
              <p>Detailed cloud report not connected.</p>
              <TextLink href={`/documents/${selected.id}`}>
                Document details
              </TextLink>
            </aside>
          </div>
        </>
      )}
    </>
  );
}
