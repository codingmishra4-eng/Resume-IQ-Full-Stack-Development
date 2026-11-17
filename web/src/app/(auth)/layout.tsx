import Link from "next/link";
import {
  ArrowUpRight,
  FileCheck2,
  Layers3,
  LockKeyhole,
  Sparkles,
} from "lucide-react";
export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <main className="auth-layout">
      <section className="auth-story">
        <Link href="/login" className="brand">
          <span className="brand-mark">
            <FileCheck2 size={21} />
          </span>
          Resume<span className="brand-iq">IQ</span>
        </Link>
        <div className="story-body">
          <span className="eyebrow">BUILT FOR YOUR NEXT CHAPTER</span>
          <h2>
            Great experience.
            <br />
            <span>A clearer story.</span>
          </h2>
          <p>
            A thoughtful workspace to organize your resumes and make every
            application more intentional.
          </p>
          <div className="story-visual" aria-hidden="true">
            <div className="story-document">
              <div className="mini-avatar" />
              <div className="mini-line long" />
              <div className="mini-line short" />
              <hr />
              <div className="mini-line" />
              <div className="mini-line long" />
              <div className="mini-line" />
              <div className="mini-line short" />
              <hr />
              <div className="mini-line long" />
              <div className="mini-line" />
            </div>
            <span className="floating-label label-top">
              <LockKeyhole size={15} /> Yours. And only yours.
            </span>
            <span className="floating-label label-bottom">
              <Layers3 size={15} /> One workspace, every version.
            </span>
          </div>
          <div className="story-points">
            <span>
              <LockKeyhole size={15} /> Private document storage
            </span>
            <span>
              <Sparkles size={15} /> Designed for focus
            </span>
          </div>
        </div>
        <div className="story-footer">
          <span>Make your experience count.</span>
          <ArrowUpRight size={17} />
        </div>
      </section>
      <section className="auth-form-side">
        {children}
        <p className="auth-footnote">
          Thoughtful tools for the next step in your career.
        </p>
      </section>
    </main>
  );
}
