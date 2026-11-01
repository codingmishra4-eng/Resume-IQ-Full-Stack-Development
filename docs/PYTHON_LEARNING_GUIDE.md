# ResumeIQ — Python Learning Guide

This guide walks through the entire codebase in ten chapters. Read it
top-to-bottom for a full tour, or jump to the chapter you need. Every chapter
ends with concrete pointers to the exact file/function to open.

---

## Table of contents

1. [Architecture overview](#1-architecture-overview)
2. [File-by-file map](#2-file-by-file-map)
3. [Key classes at a glance](#3-key-classes-at-a-glance)
4. [How resume parsing works](#4-how-resume-parsing-works)
5. [How scoring works](#5-how-scoring-works)
6. [How the AI integration works](#6-how-the-ai-integration-works)
7. [How the database works](#7-how-the-database-works)
8. [How the templates work](#8-how-the-templates-work)
9. [How the tests work](#9-how-the-tests-work)
10. [Extending ResumeIQ](#10-extending-resumeiq)

---

## 1. Architecture overview

ResumeIQ is a three-layer application:

```
┌────────────────────────────────────────────────────────────┐
│  PRESENTATION — Streamlit (frontend/)                      │
│  app.py is the router; pages/* are pure view functions     │
│  that read/write st.session_state and call the service      │
│  layer. No business logic beyond formatting lives here.    │
├────────────────────────────────────────────────────────────┤
│  DOMAIN — pure Python (backend/, resume_builder/)          │
│  Parsers, analyzers, matchers, template renderers.         │
│  Zero Streamlit imports — everything is plain classes      │
│  with typed dataclasses in / out, so it is importable      │
│  from tests, scripts, or a future API server.              │
├────────────────────────────────────────────────────────────┤
│  STATE — SQLAlchemy + SQLite (database/)                   │
│  Small, explicit ORM. Persistence happens only through     │
│  database.Database; nothing else touches SQL.              │
└────────────────────────────────────────────────────────────┘
```

Why this matters:

- **Streamlit reruns the whole script on every interaction.** Domain logic
  that lives outside Streamlit makes each rerun cheap and testable.
- **Pure-data inputs/outputs** (`ParsedResume`, `ATSResult`, `ResumeData`)
  mean every layer can be unit-tested without UI.
- **The same builders serve three outputs** (HTML preview, PDF, DOCX) from
  one data model — one source of truth.

Entry point: `app.py`. On import it injects global CSS
(`frontend/styles.inject_base_css`), initializes `st.session_state`, renders
the top navigation, and dispatches to the selected page's `render()` function.

## 2. File-by-file map

| File | Responsibility | Lines (~) |
|---|---|---|
| `app.py` | Router, nav rendering, global state init | 120 |
| `config.py` | Paths, `ScoreWeights`, `AIConfig`, logging (`get_logger`) | 130 |
| `backend/resume_parser.py` | PDF/DOCX byte extraction → `ParsedResume` | 340 |
| `backend/ats_analyzer.py` | Six `CategoryResult` scorers + recommendations | 500 |
| `backend/keyword_analyzer.py` | Skill taxonomy + frequency report | 150 |
| `backend/job_matcher.py` | Resume ↔ JD gap analysis | 170 |
| `backend/grammar_checker.py` | Spelling, weak phrases, buzzwords, voice issues | 240 |
| `backend/ai_assistant.py` | `AIAssistant`: OpenAI + rule fallback | 290 |
| `backend/scoring_engine.py` | `ScoringEngine.analyze_upload / analyze_text` orchestration | 125 |
| `resume_builder/resume_data.py` | Resume model dataclasses + sample factory | 220 |
| `resume_builder/template_manager.py` | 15 `ResumeTemplate` definitions + HTML renderer | 370 |
| `resume_builder/pdf_generator.py` | ReportLab renderer (per-template fonts/colors) | 400 |
| `resume_builder/docx_generator.py` | python-docx renderer (ATS-safe single column) | 200 |
| `resume_builder/builder.py` | `ResumeBuilder` façade: validate → render → persist | 85 |
| `resume_builder/report_pdf.py` | Multi-page analysis report PDF | 250 |
| `database/models.py` | 3 ORM models (see chapter 7) | 90 |
| `database/database.py` | Engine/session + CRUD helpers | 190 |
| `frontend/styles.py` | Global CSS token (colors, cards, uploader tweaks) | 130 |
| `frontend/components.py` | `page_title`, `skill_chips`, stat cards, tables | 150 |
| `frontend/pages/*.py` | One `render()` per screen | 130–410 |
| `tests/*.py` | pytest suite (chapter 9) | ~470 |

## 3. Key classes at a glance

| Class | File | Purpose |
|---|---|---|
| `ParseError` | backend/resume_parser.py | Raised for empty/corrupt/oversized documents |
| `ParsedResume` | backend/resume_parser.py | text, words, pages, sections dict, contact dict, file meta |
| `ResumeParser` | backend/resume_parser.py | Facade: `parse(bytes, name)` auto-detects PDF vs DOCX |
| `ATSResult` / `CategoryResult` | backend/ats_analyzer.py | Score + findings lists; findings are `ok / warn / fail` |
| `ATSAnalyzer` | backend/ats_analyzer.py | The six rubric scorers |
| `KeywordAnalyzer` / `KeywordReport` | backend/keyword_analyzer.py | Domain-grouped skill detection |
| `JobMatcher` / `JobMatchResult` | backend/job_matcher.py | Matching / partial / missing skills + match % |
| `GrammarChecker` / `WritingReport` | backend/grammar_checker.py | Misspellings, weak phrases, buzzwords, voice |
| `AIAssistant` / `AISuggestion` | backend/ai_assistant.py | Suggestion factory with provenance label |
| `ScoringEngine` / `FullAnalysis` | backend/scoring_engine.py | Orchestrates everything, persists, returns report dict |
| `ScoreWeights` | config.py | Editable category weights (auto-normalized) |
| `ResumeData` (+ item dataclasses) | resume_builder/resume_data.py | Builder form model |
| `ResumeTemplate` | resume_builder/template_manager.py | Frozen style definition consumed by 3 renderers |
| `PDFGenerator` / `DOCXGenerator` | resume_builder/*.py | Per-template renderers |
| `ResumeBuilder` | resume_builder/builder.py | Build/save/load with validation |
| `ReportPDFBuilder` | resume_builder/report_pdf.py | Analysis report PDF |
| `AnalysisRecord` / `SavedResume` / `KeywordHistory` | database/models.py | ORM tables |
| `Database` | database/database.py | Engine factory + typed CRUD |

## 4. How resume parsing works

`ResumeParser.parse(data: bytes, name: str) -> ParsedResume`:

1. **Dispatch** — extension sniffing: PDF → `_extract_pdf` (PyMuPDF,
   `page.get_text("text")` per page, includes page count for sparse-content
   detection), DOCX → `_extract_docx` (python-docx paragraphs; table cell text
   is pulled too because resumes often hide content in tables).
2. **Passport/word count** — word count guards: under `MIN_WORDS_FOR_ANALYSIS`
   (60) `ParseError` is raised *with the friendliest possible message* — real
   users, not stack traces. Too-big files (> `MAX_UPLOAD_MB`) are rejected
   before parsing.
3. **Section detection** (`_detect_sections`) — the text is split into lines;
   each line is case-normalized then matched against a canonical heading map
   ("Work History", "Employment", "Professional Experience" → `experience`).
   From the first heading onward, lines flow into the current section until a
   new heading appears. Sections found: summary / experience / education /
   skills / projects / certifications / achievements / languages / interests.
4. **Contact extraction** (`_extract_contact`) — three regexes:
   - email: standard RFC-ish pattern,
   - phone: tolerant of `+`, spaces, dashes — note the tail is `\d{2,4}` so
     Indian 10-digit and 4-digit-extension formats both match,
   - LinkedIn/URL: domain-aware match.
   Also grabs the *first plausible name candidate*: the Word token before `@`
   of the email, dotted names (e.g. `priya.sharma@[...]`), etc.
5. **Everything is lowercase-normalized afterwards** for downstream scoring,
   but `ParsedResume.text` keeps the original for display.

⚠️ Lesson: PDF extraction is *inherently lossy*; two-column PDFs can scramble
reading order. `ATSAnalyzer._score_readability` explicitly rewards
top-parse-quality documents and flags poor extraction — that is the honest
way to handle "we can't parse your file well".

## 5. How scoring works

`ScoringEngine.analyze_upload(data, name, jd_text=None)`:

1. parses (`ResumeParser`),
2. runs `ATSAnalyzer.analyze(parsed, jd) → ATSResult`,

Each category is its own method returning a `CategoryResult` with
`score / status / findings`:

| Method | What it checks |
|---|---|
| `_score_readability` | word count band, mean sentence length, gibberish ratio, extraction quality |
| `_score_structure` | heading hits per section, section ordering, bullet usage |
| `_score_completeness` | presence of summary/experience/education/skills (+ lengths) |
| `_score_keywords` | taxonomy skill coverage (via `KeywordAnalyzer`), action verbs, weak-phrase penalty, JD vocabulary overlap when a JD is supplied |
| `_score_formatting` | bullet chars, date coverage, ATS-risk glyphs (tables, images, multi-column hints), fonts |
| `_score_contact` | email + phone + location present and parseable |

3. **Weighted blend**: `overall = Σ category × weight` (weights from
   `config.ScoreWeights.normalized()`; edit freely — they auto renormalize).
4. **Strengths / weaknesses** `_derive_strengths_weaknesses` — categories ≥ 70
   become strengths, < 55 weaknesses, with the actual score quoted.
5. **Recommendations** (`_build_recommendations`) — a priority-ordered list.
   Rules fire on the *findings that actually failed*: deduped, most urgent
   first (misspellings → weak phrases → missing sections → formatting risks).
   Nothing here invents numbers.
6. **Persist** (chapter 7) then return `FullAnalysis` (dataclass exposing
   `.overall` `.category_scores` `.report_dict`).

The keyword story: `KeywordAnalyzer` holds a ~90-skill taxonomy across 10
domains (from `python` to `stakeholder management`). It reports per-domain
hits, total matches and frequency counts. That single report powers job
MATCHING (chapter: `JobMatcher.match` = 70% skill coverage + 30% JD keyword
coverage) — and the "Missing skills" guidance.

## 6. How the AI integration works

`backend/ai_assistant.py` — the class every AI feature goes through:

- **Construct**: reads `config.AIConfig` (env: `OPENAI_API_KEY`,
  `OPENAI_MODEL`, `OPENAI_BASE_URL`). A key present → `openai.OpenAI(...)`
  client is created; otherwise `ai_available = False` and the app logs
  "rule-based fallback everywhere."
- **Every public method has two paths**:
  - `rewrite_summary`, `improve_bullets`, `keyword_guidance`: if
    `ai_available`, build a grounded system prompt (never invent employers,
    dates, numbers; use `[X%]` placeholders), call `self._chat(...)` inside a
    try/except that returns `None` on *any* failure — then parse
    `{"items":[...]}` JSON defensively (`_parse_json_items`). If the response
    is absent/malformed → deterministic rule path.
  - rule path (`_rule_summary`, `_rule_fix_bullets`) — no API, no randomness:
    weak-phrase substitution (e.g. "was responsible for" → "led"), title/skill
    detection from the resume text itself, and metric placeholders.
- **Provenance**: every `AISuggestion` carries `source="openai"` or
  `"rule-based"`. The UI renders an accordingly-colored badge, so users know
  which brain produced what.
- `suggest_verbs` is entirely rule-based (it scans for `WEAK_PHRASES` from
  `backend/grammar_checker.py`) because a phrase-swap doesn't need an LLM.

**Design lesson**: never let AI failure break UX. A dead API key, a rate
limit, or malformed JSON all collapse to the same fallback — the user just
sees a differently-labeled suggestion.

## 7. How the database works

Three tables (SQLAlchemy 2.0-style typed ORM in `database/models.py`):

1. **`analysis_records`** — one row per uploaded-resume analysis.
   - Score columns (`ats_score`, per-category floats, `word_count`) are
     denormalized into real columns so Dashboard/History can query and sort
     without deserializing JSON.
   - `report_json` (SQLAlchemy `JSON` → TEXT) stores the *full* report so
     History can reopen a report without re-parsing.
   - `resume_text` optionally stores the extracted text so Improve/Builder can
     reuse the last analyzed resume.
2. **`saved_resumes`** — builder drafts. `data_json` keeps the whole
   `ResumeData` payload; rendering happens on demand at export time.
3. **`keyword_history`** — JD match attempts (title, score, missing skills).

`database/database.py`:

- `get_engine()` — reads `DATABASE_URL` env (default `sqlite:///data/resumeiq.db`),
  ensures the parent directory exists (SQLite won't create folders).
- `Base.metadata.create_all(engine)` — schema-on-boot; migrations are
  unnecessary for a local single-user app.
- Scoped helpers: `save_analysis`, `list_analyses`, `get_analysis`,
  `delete_analysis`, save/list/load/delete for resumes, and a
  `compare_analysis(id_a, id_b)` used by History's side-by-side view.
- `get_session()` is a plain `sessionmaker` context manager; commits happen
  inside the helper — callers stay fact-of-DB-free.

Streams, threads and Streamlit: SQLite in default mode is fine for a
single-user Streamlit app. If you later move to Postgres, only `get_engine()`
needs to change.

## 8. How the templates work

`resume_builder/template_manager.py`:

- `ResumeTemplate` is a **frozen dataclass**: id, name, category,
  `layout` (`single` | `sidebar`), `header` style, accents, fonts, sizes,
  `section_order`, `bullet`, `ats_friendly` flag, and an optional
  compatibility `notice`.
- `TEMPLATES: dict[str, ResumeTemplate]` holds 15 hand-authored definitions.
  Categories: General, ATS, Engineering, Student, Corporate, Data, Design,
  Business, Academic.
- **One definition → three renderers:**
  - `render_html(template, data)` — preview inside Streamlit (`st.markdown`
    with `unsafe_allow_html=True`), exact CSS for sidebar layout, colors,
    typography.
  - `PDFGenerator` (ReportLab) — `FONT_MAP`/`BOLD_MAP` map requested families
    (`helvetica`, `times`) onto the always-available PDF base fonts; the
    template drives headings, accent rules, sidebar boxes, bullet glyphs.
  - `DOCXGenerator` (python-docx) — **always single-column ATS-safe**, even
    for sidebar templates. Word's parser is the least forgiving, so DOCX is
    the "safe twin"; the docx generator emits a top-header + linear layout in
    the template's fonts.
- `attempts compatibility_note()` — human-readable ATS warning when
  `ats_friendly=False` (sidebar/creative), surfaced by the gallery UI.

**Lesson**: when N outputs share one style, define the style as data and fan
it out — never copy-paste styles across renderers, where they inevitably
diverge.

## 9. How the tests work

45 pytest tests across 6 files, all in `tests/`:

| File | Covers |
|---|---|
| `test_resume_parser.py` | DOCX/PDF extraction, section detection, contact regex edge cases (incl. the `\d{2,4}` phone tail), sparsity guard |
| `test_ats_analyzer.py` | Category scoring of a well-formed vs sparse resume, weights normalization, strengths/recommendations generation |
| `test_job_matcher.py` | Skill matching / partials / missing, no false "you know X" claims, 70/30 match math |
| `test_grammar_checker.py` | Misspelling detection, weak phrase & buzzword rules |
| `test_builder.py` | Template inventory completeness (15), PDF and DOCX are produced & non-empty, invalid template rejected |
| `test_database_and_ai.py` | DB round-trips (save/list/get/delete), JSON payload integrity, `AIAssistant` rule fallbacks with no API key |

`conftest.py` creates two realistic `ParsedResume` fixtures (fresh grad + 3-year
professional) so every test works on realistic text without touching disk.

Run:

```bash
python -m pytest            # whole suite
python -m pytest tests/test_ats_analyzer.py -v   # single file
```

**Test-writing habits worth copying from this suite**:

- one *behavioral* assertion per test ("sparse resume scores contact < 50",
  not "score == 42.6") so the rubric can be tuned without breaking tests;
- DB tests use a temp SQLite file, never the production `data/` db;
- AI tests always exercise the *fallback* path — CI has no API keys.

## 10. Extending ResumeIQ

**Add a template** → `resume_builder/template_manager.py`: add one
`ResumeTemplate(...)` to `TEMPLATES`. All three renderers pick it up
automatically; the gallery sorts by category. Keep `ats_friendly=False`
honest — that flag drives the warning chips.

**Add a scoring check** → one `CategoryResult.add_check(...)` inside the
relevant `ATSAnalyzer._score_*` method; findings feed both the UI and the PDF
report. If you weight it separately, add a field to `ScoreWeights` in
`config.py`.

**Add an AI-generated suggestion** → a new `AIAssistant` method returning an
`AISuggestion`, with a rule-based fallback path; render it in
`frontend/pages/improve.py` via `_suggestion_block`.

**Add a table** → new model in `database/models.py` (subclass `Base`), plus
CRUD helpers in `database/database.py`; `create_all` will add it at boot.

**Add a page** → create `frontend/pages/<name>.py` with a `render()`, then
register it in the `PAGES` list in `app.py`. Reuse
`components.page_title`/card CSS so it matches automatically.

**Swap the storage engine** → implement the same functions with Postgres in
a new `database/<engine>.py`; nothing else imports SQL anywhere.

**Swap the parser backend** — e.g. add locked-PDF OCR: implement your
`_extract_pdf_ocr` next to `_extract_pdf` inside `resume_parser.py` and have
`ResumeParser.parse` fall back to it when PyMuPDF returns fewer than
`MIN_WORDS_FOR_ANALYSIS` words.

---

*The single most transferable lesson in this codebase: build the honest
version first, then let AI dress it up when a key exists — never the
reverse.*
