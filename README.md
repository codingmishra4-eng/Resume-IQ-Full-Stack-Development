# ResumeIQ v1.0.0

**AI-powered resume analyzer, ATS checker & resume builder — local-first.**

ResumeIQ parses a PDF or DOCX resume entirely on your machine, computes a
transparent *estimated ATS compatibility* score across six categories, compares
it against a job description, and rewrites weak wording with honest
before → after suggestions (never fabricated metrics). It also includes a full
resume builder with 15 prebuilt templates that export to ATS-safe PDF and DOCX.

> **What ResumeIQ does *not* do:** it never claims to be an official ATS
> vendor tool. Every score is labeled an **"estimated ATS score"** — a
> heuristic computed from your actual document. Any metric you should insert
> (impact numbers, years, percentages) is shown as a placeholder like
> `[X%]` instead of being invented.

---

## ✨ Features

| Area | What you get |
|---|---|
| 🧪 **Analyze** | Upload PDF/DOCX → 6-category score (readability, structure, completeness, keywords, formatting, contact), strengths, weaknesses, prioritized recommendations, full PDF report |
| 🎯 **Job Match** | Paste a JD → side-by-side skill comparison: matched / partial / missing skills, match %, experience & education cues, honest guidance ("do NOT list skills you don't know") |
| ✨ **AI Improve** | Before/after rewrites: summary, weak bullets, stronger verbs, JD keyword weaving — with Accept / Reject / Edit per suggestion |
| 🗂 **Resume Builder** | 15 templates across General / ATS / Engineering / Student / Corporate / Data / Design / Academic, live HTML preview, PDF + single-column ATS-safe DOCX export, SQLite save/load |
| 🕘 **History** | Every analysis stored in SQLite; reopen full reports, compare any two analyses, delete records |
| 🔒 **Privacy** | Local-first: parsing, scoring and storage all happen on your device. No resume text leaves your machine (unless *you* configure an OpenAI key) |

## 🚀 Quick start

```bash
# 1 — install dependencies (Python 3.11+ recommended; 3.10 works)
pip install -r requirements.txt

# 2 — optional NLP extras for best-quality parsing/skill detection
python -m nltk.download punkt stopwords wordnet
python -m spacy download en_core_web_sm

# 3 — run the app
streamlit run app.py
```

Open http://localhost:8501. Without an OpenAI key the app runs in
**rule-based mode** — every screen shows a clear notice, and all scores and
suggestions remain fully functional and honest.

### Optional: enable AI narration

```bash
copy .env.example .env      # Windows
# cp .env.example .env      # macOS/Linux
```

Set `OPENAI_API_KEY=sk-...` in `.env`. AI features activate automatically;
any API failure silently falls back to the deterministic rule engine and the
UI labels which source produced each suggestion (`🤖 OpenAI` vs `⚙️ Rule-based`).

## 🧪 Tests & smoke check

```bash
python -m pytest          # 45 tests across 6 test files
python smoke_test.py      # end-to-end pipeline check → prints "SMOKE OK"
```

## 🏗 Project structure

```
app.py                     Streamlit entry point & top-nav router
config.py                  Paths, score weights, AI settings, logging setup
backend/
  resume_parser.py         PDF (PyMuPDF) / DOCX (python-docx) → ParsedResume
  ats_analyzer.py          6-category rubric scoring engine
  keyword_analyzer.py      Skill taxonomy detection (90+ skills, 10 domains)
  job_matcher.py           Resume ↔ JD comparison (70% skills / 30% keywords)
  grammar_checker.py       Misspellings, weak phrases, buzzwords, voice issues
  ai_assistant.py          OpenAI-backed suggestions + rule-based fallback
  scoring_engine.py        Orchestrator: parse → analyze → persist → report
resume_builder/
  template_manager.py      15 template definitions (single & sidebar layouts)
  resume_data.py           Type-safe resume model (dataclasses)
  pdf_generator.py         ReportLab PDF renderer (per-template styling)
  docx_generator.py        python-docx renderer (always single-column ATS-safe)
  builder.py               High-level build/save/load API
  report_pdf.py            Multi-page analysis report (ReportLab)
database/
  models.py                SQLAlchemy ORM: AnalysisRecord, SavedResume, KeywordHistory
  database.py              Engine, session factory, persistence helpers
frontend/
  styles.py                Premium dark theme (global CSS)
  components.py            Reusable UI pieces (cards, chips, tables, badges)
  pages/
    dashboard.py  analyze.py  job_match.py  improve.py  builder.py  history.py
tests/                     pytest suite (parser, analyzer, matcher, builder, DB, AI)
data/                      SQLite DB + upload cache (created on first run)
generated_resumes/         PDF/DOCX output (created on demand)
logs/                      Rotating log file
.streamlit/config.toml     Theme & server configuration
```

## 🧠 How the score works

Each category is scored 0–100 by deterministic checks (findings carry an
`ok / warn / fail` status plus human-readable detail):

| Category | Weight | Example checks |
|---|---|---|
| Readability | 20% | text-extraction quality, word count, average sentence length |
| Structure | 20% | recognized section headings & hierarchy |
| Completeness | 15% | summary / experience / education / skills present |
| Keywords | 20% | skill-taxonomy coverage, action-verb density, weak phrases |
| Formatting | 15% | bullets, dates, ATS-risky symbols/columns |
| Contact | 10% | parseable email, phone, location |

`overall = Σ category × weight` (weights are `config.ScoreWeights`, freely
editable and defensively re-normalized). The number is always presented as an
**estimate** — different ATS products parse documents differently and no test
can guarantee a vendor's proprietary parser.

## 🧾 Templates

15 templates share one definition (`ResumeTemplate`) across three renderers
(live HTML preview, ReportLab PDF, python-docx DOCX) so outputs stay
consistent. Two layout families:

- **single** — full-width, top contact header → the ATS-safest layout
- **sidebar** — decorative two-column layout → clearly flagged in the gallery
  with a compatibility notice

DOCX export is **always single-column** regardless of the template's HTML/PDF
look — Word files face harsher parser limits, so ResumeIQ keeps them safe.

## 🔒 Honesty guarantees

1. Scores derive only from your document's actual text — no random
   generation, no fabricated percentages anywhere in results or reports.
2. Missing impact numbers appear as `[X%]` / `[N hours]` placeholders you
   fill in with real values.
3. Job Match never lists a JD skill as *yours*; "partial" matches are labeled
   partial with an explanation.
4. Every suggestion is labeled with its origin (OpenAI or rule engine).
5. The disclaimer is rendered wherever a score appears: *"heuristic estimate —
   not certified by any ATS vendor."*

## 📜 License / privacy

Local-first design; resume content never leaves your device except when you
explicitly configure an OpenAI key (then job description + snippets go to the
API). The SQLite database stays in `data/`.
