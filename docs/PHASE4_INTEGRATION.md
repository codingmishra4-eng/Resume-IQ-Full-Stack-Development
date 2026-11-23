# Phase 4 feature integration

Base: Phase 3 d0c20d0. Branch: codex/phase-4-feature-integration.
No live project changes, deployment or merge are part of implementation.

## Feature-to-API matrix

| Feature | Existing capability | Phase 4 reuse/integration |
|---|---|---|
| Auth/private documents/history | Phase 2 FastAPI + Supabase/RLS | Preserve contracts and user-scoped sessions |
| ATS report | ATSAnalyzer, ResumeParser, GrammarChecker, KeywordAnalyzer | Load owned private original; compute detailed report without local SQLite |
| Impact/format/contact/sections | ATSAnalyzer categories and quantified-bullet checks | Return actual counts/check evidence, not certified scores or invented metrics |
| Job matching | JobMatcher | Owner-scoped comparison, explicit skill/keyword rubric, persist results without JD text |
| AI improvement | AIAssistant and grammar rules | Explicit provider consent, bounded source text, conservative fact-preserving output guard/fallback |
| Builder | ResumeData, TemplateManager, PDF/DOCX generators | Owned draft CRUD and authenticated temporary exports |
| Preview layouts | Essential/Editorial/Compact | Preserve local previews; explicitly map exports to existing ats-minimal/executive/engineering templates |
| Frontend | Typed Phase 3 client/components | Add schemas/actions/results/history, no mock success responses |

## API contracts

All routes below require the existing verified Supabase user JWT. Path identifiers
are UUIDs; owner lookup precedes private Storage reads and document generation.
The unchanged `/api/v1/analyses` list remains the small Phase 2 score envelope.
Match records do not count as ATS analyses.

| Method | Route | Result |
|---|---|---|
| POST | `/api/v1/resumes/{id}/analyses` | Compute/persist detailed report; optional `job_description` |
| GET | `/api/v1/resumes/{id}/analyses?offset=0` | Owned report history, up to 100 summaries/page |
| GET | `/api/v1/analysis-reports/{id}` | Owned detailed report |
| POST | `/api/v1/resumes/{id}/matches` | Compute/persist match; required `job_description` |
| GET | `/api/v1/job-matches/{id}` | Owned persisted match |
| POST | `/api/v1/resumes/{id}/improvements` | Transient summary/bullets/verbs/keywords suggestions |
| GET | `/api/v1/builder/templates` | Server template catalog and actual export mapping |
| GET, POST | `/api/v1/builder/drafts` | List metadata / save owned draft |
| GET, PUT, DELETE | `/api/v1/builder/drafts/{id}` | Retrieve / replace / delete owned draft |
| POST | `/api/v1/builder/drafts/{id}/exports/{pdf\|docx}` | Authenticated binary attachment, no-store |

`PUT` replaces a validated complete `{template,draft}` payload. The client saves
current form values before exporting. Local JSON download and browser printing
remain local operations. Loading/deleting a saved draft requires confirmation.
Exports have constant filenames and do not create public objects or permanent
server files. Server typography/pagination differ from the browser preview;
Essential → `ats-minimal`, Editorial → `executive`, Compact → `engineering`.
All three exports are single-column, but ATS compatibility is not guaranteed.

## Scoring, privacy and resource boundaries

- Detailed ATS scoring reuses `ATSAnalyzer`'s six weighted heuristic categories.
  Each report returns the actual category weights, checks, strengths, weaknesses,
  recommendations and certification disclaimer. All twelve Analyzer sections
  display computed data; JD-dependent sections explicitly ask for a JD when absent.
- Matching reuses `JobMatcher`: exact taxonomy matches receive 1 credit and
  related-category partial matches 0.5. When repeated non-taxonomy JD keywords
  exist, skills contribute 70% and keyword coverage 30%; otherwise skills alone.
  Keywords use the original engine's substring heuristic. Partial credit is
  related vocabulary evidence, not proof the candidate possesses a missing skill.
- No cloud analysis uses `ScoringEngine` or writes to Streamlit's SQLite database.
- Existing private Storage originals remain unchanged. Analysis JSON persists
  scores, derived skill/keyword evidence and bounded writing excerpts necessary
  for review (40 findings/type, 400 characters/context, ten long sentences).
  These excerpts can contain personal information and are owner-protected; treat
  reports as sensitive. No full extracted resume, original filename, raw JD,
  AI prompt or improvement response is added to the database. Contact output is
  presence booleans only. Job-specific derived vocabulary is retained.
- Builder drafts necessarily store the user-entered resume content as private
  JSON. List endpoints expose identifiers, timestamps and templates only. Deleting
  a draft removes its content; event history keeps only its identifier and event.
  Deleting an original resume cascades linked analysis/match results.
- `CLOUD_AI_ENABLED=false` is the backend default. Enabling it is insufficient
  without per-request `use_ai=true` consent. `OPENAI_API_KEY` stays backend-only.
  Only the selected excerpt (or detected summary/bullets when empty) is supplied
  as provider context. JD keyword guidance stays rule-based. Improvements are
  never automatically applied. Provider edits are accepted only when their
  normalized word/number sequence matches the original or the conservative
  spelling/filler/wording edit. Other generations, including new employers or
  metrics, are discarded in favor of labeled rule output. This deliberately
  limits AI to proof edits; it is not unrestricted resume generation.
- Providers use a 12-second timeout, 600-token output cap and no retries; at most
  six bullet requests. JSON bodies are capped at 128 KiB before parsing. JD size
  is 30–20,000 characters; source excerpts 6,000 characters; original reads are
  streamed with a 10 MiB ceiling; analysis accepts at most 100 pages/100,000
  extracted characters. Exports are at most 5 MiB.
- CPU/provider operations run in worker threads without holding a DB transaction.
  At most two heavy operations per process, one per user, run concurrently.
  This is admission control, not distributed quota enforcement. Configure gateway
  rate limits and process/container CPU/memory budgets before public exposure.
- The frontend uses bounded requests, real loading states (no invented progress),
  strict response schemas, fresh bearer user tokens, no cached private data and
  no automatic retry of failed writes. An account change remounts the complete
  workspace, clearing report, JD, writing and builder state.

## Migration and security

`0002_feature_links` is additive on the four existing tables. It adds nullable
`cloud_analyses.resume_id`, `kind` (`analysis` or `match`), an index and a same-owner
composite foreign key with cascade deletion, plus the parent `(id,user_id)` unique
constraint. Existing Phase 2 summary records remain nullable/unlinked and readable
through the existing summary API. No table recreation, user provisioning, grants,
RLS policy change or runtime permission expansion occurs.

Runtime remains `resumeiq_runtime` with NOBYPASSRLS and transaction-local user
identity. Every application lookup also filters owner and takes the existing row
lock where needed. Heavy work rechecks ownership before persisting/exporting.
FORCE RLS and denied PUBLIC/anon/authenticated/service_role table grants remain
unchanged, including the migration table. The composite foreign key additionally
rejects linking a report to another user's resume, even with direct runtime SQL.
The existing ES256 JWT verification, backend `sb_secret_` apikey-only Storage
requests, private-bucket check, safe uploads, short-lived downloads and disabled
public legacy upload are preserved.

No live database migration, cloud request, real role creation, deployment or merge
was executed during this implementation. PostgreSQL tests use explicitly supplied,
fresh disposable local containers and NOLOGIN test roles.

## Owner steps: review, then local/staging verification

1. Review this draft PR against Phase 3. Back up the target database and schedule
   the migration; adding an index/constraints can lock existing tables. The new
   backend requires migration head before it starts serving feature queries.
2. Keep `CLOUD_ENABLED=false` and `CLOUD_AI_ENABLED=false` until configuration is
   reviewed. Keep admin migration credentials separate from the deployed runtime.
   Never paste them into commands or commit `.env`. Do not run downgrade on a
   persistent database: downgrade removes Phase 4 links/types and loses that data.
3. With the project virtual environment active, these exact Windows CMD commands
   load the operator's existing private `.env` without displaying values. Run
   `current` first; apply `head` only after review/backup and explicit operator
   decision. This agent has not run these against Supabase:

```bat
cd C:\path\to\Resume-IQ-Full-Stack-Development
.venv\Scripts\activate
python -c "from dotenv import load_dotenv; from alembic.config import Config; from alembic import command; load_dotenv(); command.current(Config('alembic.ini'))"
python -c "from dotenv import load_dotenv; from alembic.config import Config; from alembic import command; load_dotenv(); command.upgrade(Config('alembic.ini'), 'head')"
```

   Alembic uses only `CLOUD_MIGRATION_DATABASE_URL`; runtime uses only
   `CLOUD_DATABASE_URL`. Neither command prints the connection string. For Linux,
   activate `.venv/bin/activate` and use the same Python commands.
4. Audit runtime attributes/table policies using the Phase 2 read-only verification
   steps in `docs/PHASE2_VERIFICATION.md`. Do not grant BYPASSRLS, owner membership,
   table DDL, or Data API table access to make an error disappear.
5. Configure the backend's exact frontend CORS origin and private Storage bucket.
   For any public test deployment use `API_PUBLIC_MODE=true` and
   `API_LEGACY_UPLOAD_ENABLED=false`. No deployment is included here. Frontend
   `.env.local` contains public configuration only; see `docs/NEXTJS_PHASE3.md`.
6. Start the API locally with environment loading, and run the frontend:

```bat
python -m uvicorn backend.api:app --env-file .env --host 127.0.0.1 --port 8000
```

```bat
cd web
npm ci
npm run dev
```

7. With two dedicated synthetic test accounts, upload a generated test DOCX and
   test all feature actions. A must see only A's report/history/matches/drafts;
   B must receive 404 for A's identifiers, including both export formats. Check
   missing/invalid JWTs, report history after reload, resume deletion cascade,
   saved draft load/update/delete, and direct anonymous Storage denial. Inspect
   generated files locally for truthful content and literal markup handling.
   Never use a personal resume, print tokens, or share signed URLs.
8. AI testing is optional and requires operator opt-in plus checkbox consent.
   Verify disabled-provider behavior first, then accepted proof edits and
   discarded unsupported generation. Provider credentials/consumption and live
   Supabase writes have not been exercised here.
9. Browser/device QA remains required: keyboard/screen reader navigation,
   desktop/mobile overflow, auth redirect/session changes, download dialogs,
   clipboard permission denial and long-content pagination. The managed session
   lacks its native browser testing tool; Playwright cases were collected only.

## Reproducible local checks

```sh
python -m pytest -o addopts='' -q --tb=short
python -m pip check
python smoke_test.py
python -m scripts.audit_phase2_secrets
npm --prefix web test
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run build
npm --prefix web audit --omit=dev
npm --prefix web audit
```

Without `TEST_POSTGRES_URL`, the destructive disposable PostgreSQL tests skip.
For a full run, create a brand-new local disposable container only. Never use a
persistent Supabase URL here; roles/default grants/tables are modified and removed.
Stop the named container after the test. Use a fresh container for each run.

```sh
docker run --detach --rm --name resumeiq-phase4-test-pg \
  -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=resumeiq \
  -p 127.0.0.1:55444:5432 postgres:17-alpine
# Wait until: docker exec resumeiq-phase4-test-pg pg_isready -U postgres
RESUMEIQ_TEST_POSTGRES_DISPOSABLE=true \
TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55444/resumeiq \
  python -m pytest -o addopts='' -q --tb=short
docker stop resumeiq-phase4-test-pg
```

The development advisory still affects 17 transitive packages via picomatch
GHSA-fc5q-39xc-vjpf. The registry's latest version remains 4.0.7 and the advisory
covers that version; no patched upstream release was available. No forced or
breaking override was applied. Runtime dependency audit reports zero advisories.
Recheck upstream before public release; do not treat a build as browser/live QA.

## Recorded implementation verification

Linux, Python 3.12.14, Node 24.22.1 / npm 11.9.0:

| Check | Actual result |
|---|---|
| Complete Python suite with disposable PostgreSQL 17 | **225 passed, 0 failed, 0 skipped, 0 errors** |
| PostgreSQL subset included above | 16 passed, including upgrade/downgrade, retained legacy record, ACLs, forced RLS, NOBYPASS runtime, composite FK/cascade, complete feature workflow |
| Frontend Vitest | **77 passed, 0 failed, 0 skipped, 0 errors**, 10 files |
| ESLint | Passed, zero warnings |
| TypeScript / Next route type generation | Passed |
| Next.js production build | Passed |
| Python pip check | No broken requirements found |
| Existing synthetic smoke test | Exit 0, `SMOKE OK`, all 15 templates plus analysis pipeline |
| Git tracked-file/local-history secret audit | 0 candidate exposures; heuristic only |
| Runtime npm audit | 0 advisories |
| Full npm audit | 17 high transitive development advisories; no patched picomatch upstream |
| Playwright | 4 public cases collected, **not executed** |
| Live Supabase / hosted JWT / private Storage / AI provider | **Pending**, no live credentials or writes used |
| Windows execution | **Not run** in this Linux environment; portable CMD commands supplied |

New Python coverage includes required JWTs on every feature route, computed report
schemas/history, deterministic 66.7% matching fixture, linked-result deletion,
cross-user 404s, draft XML/markup safety and real PDF/DOCX parsing, invalid/oversize
inputs, AI hallucination/provider failure fallback, source-preserving proof edit,
concurrency cleanup, bounded Storage HTTP requests and temporary-file cleanup.
Frontend coverage adds actual request/response schemas, auth-only JSON and binary
transport, report history/all twelve sections, computed matching and stale result
clearing, reviewable suggestions, builder confirmation/save/delete and export
failure recovery/download. Existing Phase 1–3 tests remain in the complete suites.

Changed source groups: `backend/api.py`, `backend/api_v1/{errors,middleware}.py`,
`backend/cloud/{database,models,routes,storage,feature_engine,feature_schemas,features}.py`,
`migrations/versions/0002_feature_links.py`, `.env.example`, Python cloud/feature tests;
`web/src/lib/{api,features}.ts`, Analyzer/Job Match/Improve/Builder/MatchView components,
dashboard/activity/upgrade copy, supplemental CSS and frontend fixtures/tests.
README and the Phase 3 checkpoint link here. This document is the complete route, migration, operational and verification guide.

Implementation is ready for review as a stacked draft against Phase 3. Hosted
readiness remains conditional on migration review/application, safe live tests,
browser/device QA, rate/resource limits and resolving/reviewing the development
advisory. No production readiness or completed live verification is claimed.
