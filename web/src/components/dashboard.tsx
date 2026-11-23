"use client";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  ChartNoAxesCombined,
  Clock3,
  FileChartColumn,
  Files,
  ScanText,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";
import { useAuth, useWorkspace } from "./providers";
import {
  Badge,
  Button,
  EmptyState,
  Notice,
  PageHeading,
  Panel,
  Skeleton,
  TextLink,
} from "./ui";
import { HistoryList, ResumeTable, UploadButton } from "./documents";
import { ScoreChart } from "./chart";
import { count } from "@/lib/format";
export function Dashboard() {
  const { account } = useAuth();
  const { resumes, analyses, history, loading, refresh } = useWorkspace();
  const scored = analyses.data?.filter((item) => item.ats_score !== null) ?? [];
  const average = scored.length
    ? scored.reduce((sum, item) => sum + (item.ats_score ?? 0), 0) /
      scored.length
    : null;
  return (
    <>
      <PageHeading
        eyebrow="YOUR NEXT CHAPTER"
        title="Your experience. Clearly told."
        description={`Welcome back${account.email ? `, ${account.email.split("@")[0]}` : ""}. Let’s make your next application more intentional.`}
        action={<UploadButton />}
      />
      <section className="welcome-banner">
        <div>
          <Badge tone="mint">
            <span className="status-dot" /> Your personal workspace
          </Badge>
          <h2>
            Good opportunities start
            <br />
            with a strong first impression.
          </h2>
          <p>
            Keep your resume versions organized, your next role in focus,
            <br className="desktop-break" /> and your professional story ready
            for what’s next.
          </p>
          <Link className="text-link" href="/analyzer">
            Open your resume workspace <ArrowRight size={17} />
          </Link>
        </div>
        <div className="hero-document" aria-hidden="true">
          <div className="hero-doc-top">
            <span className="mini-avatar" />
            <span>
              <i />
              <i />
            </span>
            <ShieldCheck size={22} />
          </div>
          <div className="doc-rule" />
          <i className="document-line" />
          <i className="document-line long" />
          <i className="document-line short" />
          <div className="doc-rule" />
          <i className="document-line long" />
          <i className="document-line" />
          <div className="doc-bottom">
            <ShieldCheck size={13} /> YOUR STORY, PROTECTED
          </div>
        </div>
      </section>
      <div className="stat-grid">
        {[
          {
            label: "Uploaded resumes",
            value: resumes.data ? count(resumes.data.length) : "—",
            detail: "PDF & DOCX documents",
            icon: <Files size={19} />,
            tone: "mint",
          },
          {
            label: "Saved analyses",
            value: analyses.data ? count(analyses.data.length) : "—",
            detail: "Available summary records",
            icon: <FileChartColumn size={19} />,
            tone: "violet",
          },
          {
            label: "Average estimated score",
            value: average === null ? "—" : average.toFixed(1),
            detail: "From scored analyses only",
            icon: <ChartNoAxesCombined size={19} />,
            tone: "blue",
          },
          {
            label: "Workspace activity",
            value: history.data ? count(history.data.length) : "—",
            detail: "Your recorded document events",
            icon: <Clock3 size={19} />,
            tone: "amber",
          },
        ].map((item) => (
          <Panel className="stat-card" key={item.label}>
            <div className="stat-label">
              {item.label}
              <span className={`stat-icon ${item.tone}`}>{item.icon}</span>
            </div>
            <strong>{item.value}</strong>
            <small>{item.detail}</small>
          </Panel>
        ))}
      </div>
      {(resumes.error || analyses.error || history.error) && (
        <div className="mb-6">
          <Notice error>
            Some workspace data could not be loaded.{" "}
            <button className="inline-button" onClick={refresh}>
              Try again
            </button>
          </Notice>
        </div>
      )}
      <div className="dashboard-columns">
        <Panel>
          <div className="section-heading">
            <div>
              <h2>Your progress, in perspective</h2>
              <p>Saved estimated ATS scores over time.</p>
            </div>
            <Badge>Analysis history</Badge>
          </div>
          {analyses.error ? (
            <Notice error>{analyses.error}</Notice>
          ) : loading && !analyses.data ? (
            <Skeleton />
          ) : scored.length ? (
            <ScoreChart analyses={analyses.data ?? []} />
          ) : (
            <EmptyState
              icon={<ChartNoAxesCombined size={27} />}
              title="A little perspective goes a long way."
            >
              Run an analysis in the Resume workspace to save your first
              estimated score.
            </EmptyState>
          )}
        </Panel>
        <Panel>
          <div className="section-heading">
            <div>
              <h2>Recent activity</h2>
              <p>The latest in your workspace.</p>
            </div>
            <TextLink href="/documents">View all</TextLink>
          </div>
          {loading && !history.data ? (
            <Skeleton />
          ) : history.error ? (
            <Notice error>{history.error}</Notice>
          ) : (
            <HistoryList items={history.data ?? []} limit={4} />
          )}
        </Panel>
      </div>
      <div className="section-heading quick-heading">
        <div>
          <h2>Make your next move</h2>
          <p>A focused toolkit for a more confident application.</p>
        </div>
        <span className="eyebrow muted">ONE STEP AT A TIME</span>
      </div>
      <div className="quick-grid">
        {[
          {
            href: "/analyzer",
            icon: <ScanText size={21} />,
            title: "Understand your resume",
            text: "Upload a version and compute a detailed report.",
            status: "Resume workspace",
          },
          {
            href: "/job-match",
            icon: <Target size={21} />,
            title: "Focus on the right role",
            text: "Compare real skills and keywords with a target role.",
            status: "Connected workspace",
          },
          {
            href: "/improve",
            icon: <Sparkles size={21} />,
            title: "Refine your story",
            text: "Review grounded writing suggestions.",
            status: "Connected workspace",
          },
        ].map((item) => (
          <Link href={item.href} key={item.href} className="quick-card">
            <div className="quick-card-top">
              <span className="quick-icon">{item.icon}</span>
              <ArrowUpRight size={17} />
            </div>
            <h3>{item.title}</h3>
            <p>{item.text}</p>
            <span className="quick-label">{item.status}</span>
          </Link>
        ))}
      </div>
      <Panel className="recent-documents">
        <div className="section-heading">
          <div>
            <h2>Recent documents</h2>
            <p>The latest versions of your professional story.</p>
          </div>
          <TextLink href="/documents">All documents</TextLink>
        </div>
        {loading && !resumes.data ? (
          <Skeleton />
        ) : resumes.error ? (
          <Notice error>{resumes.error}</Notice>
        ) : resumes.data?.length ? (
          <ResumeTable resumes={resumes.data.slice(0, 4)} compact />
        ) : (
          <EmptyState
            icon={<Files size={25} />}
            title="Room for your first resume."
            action={<UploadButton />}
          >
            Add a PDF or DOCX. We’ll keep it private and easy to find.
          </EmptyState>
        )}
      </Panel>
      <div className="privacy-strip">
        <ShieldCheck size={18} />
        <span>
          <strong>Private by design.</strong> Your original files stay in
          private storage. Download access is short-lived and created only when
          you ask.
        </span>
        <Button variant="ghost" onClick={refresh} loading={loading}>
          Refresh workspace
        </Button>
      </div>
    </>
  );
}
