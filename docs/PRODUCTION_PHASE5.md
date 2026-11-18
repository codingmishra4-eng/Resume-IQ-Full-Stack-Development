# Phase 5 — production preparation and launch runbook

Base: Phase 4 `d6b3d261ed4ff2632a281fbb28b12510044e26d7`.
Branch: `codex/phase-5-production-readiness`, stacked draft against Phase 4.
**No deployment, live migration, infrastructure changes, real user provisioning,
credential rotation or merge is authorized by these files.** Importing a Blueprint
or approving a Vercel build is a manual infrastructure action, not a local test.

## Audit and deployment topology

The unchanged Streamlit entry point is `app.py`. Vercel must use Root Directory
**web**, framework Next.js, Node 24, `npm ci`, `npm run build`. `web/vercel.json`
is intentionally inside that root. Do not deploy the Python repository as a Vercel
Next.js app, and do not ship backend environment variables to Vercel.

Render runs the existing FastAPI entry point `backend.api:app` through
`python -m scripts.start_api`, using pinned `requirements-api.txt` and Python 3.12.
The wrapper uses Uvicorn with one worker, no reload, no access log, no proxy-header
trust, 24 concurrent connections/tasks, backlog 64, keepalive 5 seconds and a
100-second graceful drain. Render's prepared maximum shutdown delay is 120 seconds.
`render.yaml` is preparation only, with auto-deploy off and a Standard resource
plan. Operator must review current provider pricing/schema/availability before
creating anything. No Render or Vercel remote validation/deployment was performed.

Supabase remains the Auth, private Storage and PostgreSQL provider. Browser calls
FastAPI using verified user Bearer tokens. Storage calls remain backend-only with
modern `sb_secret_` apikey authentication. Browser Supabase configuration uses
only a modern publishable key. No browser Data API/private Storage table access
or administrator DB connection is introduced.

| Gap found | Local change / launch condition |
|---|---|
| Default SQLAlchemy pool/indefinite waits | Bounded 3+1 connections/process, 5s pool/connect waits, 300s recycle; transaction-local 10s statement / 3s lock timeout |
| Admission-only heavy work controls | Public API adds verified-user fixed-window 120 requests/minute and 12 writes/minute, bounded 4096 identities, Retry-After 60; existing two-heavy/one-per-user limit remains |
| No production launch guard | Wrapper requires cloud/public mode, legacy upload disabled, explicit DB TLS; rejects migration/admin variable |
| Liveness confused with cloud readiness | `/api/health` remains liveness; `/api/ready` checks restricted runtime and Phase 4 schema columns, static 503 on failure |
| Access/exception logging risk | No access logging; event-only Uvicorn formatter discards message/traceback; HTTP diagnostics disabled |
| No repeatable deployment checks | CI for Python/PostgreSQL, frontend, production build and public browser flows; separate explicit opt-in staging suite |
| Live verifier did not cover features | `scripts.verify_phase5` adds revision check, analysis/match/improvement/draft/export isolation and cleanup |

Readiness is deliberately **not** a claim of working Auth, JWKS, Storage policies,
AI, actual exports, or exact migration version. It checks columns and runtime
attributes without granting runtime access to the migration table. The operator
verifier checks exact `0002_feature_links` using a separate READ ONLY audit
connection, then checks the ownership FK on its runtime database. All hosted
components must also pass synthetic integration checks before launch.

No schema migration is added in Phase 5. Apply the existing Phase 4 migration
before this backend queries the new columns; an old schema fails readiness.
The API rejects migration credentials in public mode. PostgreSQL timeouts are
SET LOCAL inside ORM transactions, not unsupported pooler startup parameters.
Use the Supabase session pooler or a compatible direct endpoint. Transaction
pooler compatibility requires a separate staging test; never remove RLS to
resolve a pooler failure.

## Environment ownership

| Scope | Variables / rules |
|---|---|
| Vercel only | `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `NEXT_PUBLIC_API_URL`; all service origins HTTPS, exact and credential-free |
| Render | `CLOUD_ENABLED=true`, `API_PUBLIC_MODE=true`, `API_LEGACY_UPLOAD_ENABLED=false`, `CLOUD_AI_ENABLED=false`, `API_ALLOWED_ORIGINS` exact HTTPS frontend origins |
| Render Auth/Storage | `SUPABASE_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ALGORITHM=ES256`, `SUPABASE_JWT_AUDIENCE=authenticated`, `SUPABASE_STORAGE_BUCKET`, backend-only `SUPABASE_SECRET_KEY` |
| Render database | `CLOUD_DATABASE_URL` authenticates only `resumeiq_runtime`, NOBYPASSRLS, no admin attributes/role memberships; add explicit `sslmode=require` at minimum; prefer verify-full with the operator-provisioned Supabase CA |
| Render pool | `CLOUD_DB_POOL_SIZE=3` (1–10), `CLOUD_DB_MAX_OVERFLOW=1` (0–5), `CLOUD_DB_POOL_TIMEOUT=5` (1–30 seconds); process count multiplies connections |
| Operator migration environment ONLY | `CLOUD_MIGRATION_DATABASE_URL`; never set it in Render, Vercel or CI deployment secrets |
| Operator staging verifier ONLY | `PHASE5_MIGRATION_AUDIT_DATABASE_URL` for SELECT revision in READ ONLY transaction, plus existing `PHASE2_*`, Supabase keys, restricted runtime URL and dedicated test accounts |
| Browser QA process ONLY | `PHASE5_BROWSER_BASE_URL`, `PHASE5_API_URL`, `PHASE5_ALLOW_LIVE_WRITES=true` after approval, dedicated `PHASE2_TEST_USER_A/B_EMAIL/PASSWORD`, public Supabase URL/key |

Use provider secret settings/private ignored `.env` files. Never place credentials
in a shell command, screenshot, issue, PR, artifact, frontend public environment,
or committed env file. Do not copy the operator env wholesale into a web or API
service. The existing build-time public-secret guard remains active. The bundle
scanner is heuristic, not a guarantee of no credential exposure.

AI remains disabled. Enabling it later requires a reviewed pinned optional SDK,
backend-only provider configuration and explicit per-request user consent. The
API requirements intentionally do not install the optional OpenAI SDK. Retain
existing conservative source-preserving proof-edit acceptance, 12s timeout,
600-token cap, no retries and rule fallback. Do not enable AI to make rule-only
QA pass. No provider API call was executed in Phase 5.

## Manual operator deployment sequence (not executed by Codex)

1. **Review and approve release scope.** Review the stacked PR chain in order.
   Select immutable commit SHAs. Record previous web/API release IDs and database
   backup/PITR restore point. Keep traffic closed and AI off.
2. **Supabase preparation.** Confirm ES256 signing/JWKS/issuer, private bucket,
   no public/anonymous Storage policies, disabled Data API exposure of app tables,
   no PUBLIC/anon/authenticated/service_role app-table grants, FORCE RLS on all
   four tables, restricted runtime role and separate migration ownership. Use
   read-only catalog checks from Phase 2 documentation. Rotate a credential only
   if exposure is confirmed and the operator explicitly authorizes it; no keys
   were rotated here. Review hosted Auth rate limits and email delivery.
3. **Backup and migration.** Verify the backup is restorable. Stop writers if
   needed for the Phase 4 index/constraints and review lock impact. In a private
   operator shell, load `.env`, inspect `alembic current`, then manually approve
   `upgrade head` using the admin connection. Verify the result is exactly
   `0002_feature_links`. Never run pytest's `TEST_POSTGRES_URL` suite against this
   database. No migration command runs in Render build/start or CI deployment.
4. **Prepare Render.** After explicit infrastructure approval, create/import the
   Blueprint on the approved branch/commit. Populate only the listed Render
   variables. DB URL must use TLS. Keep auto-deploy off and one worker. Confirm
   resource allocation has headroom for 24 bounded upload buffers, two CPU-heavy
   tasks, PDF parsing/rendering and up to four DB connections. Standard is a
   starting budget, not a load-tested guarantee; choose plan after staging load
   measurements. API logs must never contain request bodies, auth headers or URLs.
5. **Prepare Vercel.** With approval, create the project with Root Directory `web`,
   Next.js, Node 24 and public-only env variables. Point API origin at the exact
   approved Render HTTPS domain. Review provider build logs/analytics settings;
   disable URL query capture on auth callbacks. Preview deployments need distinct
   test configuration and allowlisted origins; never grant wildcard CORS or
   blanket preview Auth redirects. Do not send production credentials to forks.
6. **Auth URLs.** In Supabase set Site URL to the final frontend HTTPS origin.
   Allow the exact `/auth/callback` flow and password-recovery callback used by
   `callbackUrl` in `web/src/lib/auth.ts` (including `next=/reset-password` as
   needed for the provider's matching rules). Test signup/confirmation/reset
   links in staging. Add localhost callbacks separately for local development;
   remove unneeded preview origins. Do not put tokens in a documentation URL.
7. **Origins and transport.** Set Render CORS to exact frontend HTTPS origin(s),
   without trailing slash/path. Verify OPTIONS permits Authorization and JSON
   Content-Type for GET/POST/PUT/DELETE; no credentialed cookie forwarding is
   needed. HTTP public CORS origins are rejected. Keep platform TLS enabled.
8. **Health/security gates.** Check `/api/health` and `/api/ready` (commands below),
   unauthenticated `/api/me` =>401, legacy `/api/resume/upload` =>404, invalid JWT
   =>401, private object/public link denial and API runtime role attributes.
   Check next frontend security headers, auth redirects and no horizontal overflow.
9. **Synthetic smoke QA.** Only after staging-write approval run the Python
   Phase 5 verifier and browser suite with dedicated, exclusively used users.
   Follow cleanup journal procedures below. Confirm history, resume deletion
   cascades, both export types, cross-user denials and no provider invocation.
   Authenticated browser/live workflows remain a launch blocker until executed.
10. **Traffic approval.** Set a trusted edge/WAF rate/body/time limit for invalid
    authentication/anonymous traffic before opening the service. Application
    quotas cover verified users only and are per process: restarts/replicas reset
    or multiply quotas. They are not distributed billing/abuse protection. Do not
    enable proxy-header trust on arbitrary X-Forwarded-For. Establish metrics,
    alert routing, backup retention, on-call responsibility and operator approval.

## Operational limits, logs and graceful shutdown

10 MiB document cap; JSON cap 128 KiB; PDF/DOCX validation/decompression protections
unchanged. Analysis at most 100 pages/100,000 extracted characters; source excerpt
6,000 characters; JD 20,000; generated document at most 5 MiB. Frontend feature
requests allow 90 seconds. Render request/platform timeout must exceed legitimate
feature runtime; verify the current provider limit before release. Uvicorn's
concurrency limit can return 503 before app middleware; clients must handle this
without replaying uncertain writes. The one-process rate map fails closed when
full and expires windows; verified UUIDs only, not IPs/tokens, are stored.

SIGTERM triggers Uvicorn draining, then FastAPI disposes DB pools in lifespan
shutdown. Heavy worker tasks are not a durable queue; process termination may
interrupt a write. The Phase 2 pending/deleting reconciliation procedure remains
necessary for uncertain Storage workflows. Do not blindly retry POSTs after an
outage. Platform drain behavior, load/soak testing and failure recovery remain
staging tasks. No automated chaos or production failure injection was performed.

App logs retain existing synthetic/count-only cloud events. Uvicorn errors emit
only level/logger/event (including when an exception contains secrets). Tracebacks
are deliberately excluded; debug through local synthetic tests and counters,
not private request capture. Monitor aggregate 401/429/503, readiness failures,
latency, memory, connection use and cleanup failures without user content/IDs.
Review Render/Vercel access-log retention separately: app settings cannot control
provider-owned logging. Signed URLs are bearer credentials until expiry.

## Safe live verifier and recovery

`python -m scripts.verify_phase5` with no selected mode exits 2/PENDING before
reading settings or connecting. See the [staging Windows workflow](WINDOWS_PHASE5.md#staging-verification-from-your-existing-private-file) for independent project
pinning and the existing external private-file path. Read-only inspection needs
separate connection approval and no test passwords. After separately approving
staging writes and pinning a working staging API, use:

```bat
python -m scripts.verify_phase5 --allow-live-writes --expected-project-ref YOUR_STAGING_PROJECT_REF --expected-api-origin https://YOUR-STAGING-API.onrender.com
```

This logs into two dedicated accounts, checks restricted runtime/RLS/ACLs and
private Storage, then reads exact revision `0002_feature_links` using
`PHASE5_MIGRATION_AUDIT_DATABASE_URL` in a READ ONLY transaction. That separate
connection must point to the same staging project; it is not the runtime or a
service deployment variable. Do not grant runtime access to `alembic_version`.
No migration or user/role provisioning is run. Passwords may be securely prompted
if absent from the explicitly selected private file. Inherited settings are not
used by the Phase 5 CLI. Logs contain static labels/counts only.
Feature calls have a 90s timeout. Only a confirmed pre-operation `rate_limited` 429 with Retry-After 1–60s is waited out and retried once, so ownership-denial probes can respect production quotas. Network failures, timeouts, 5xx, busy/generic 429 and uncertain writes are never replayed.

The verifier reuses Phase 2 synthetic uploads, baseline IDs, payload hashes and
atomic credential-free journals. It adds hash-identified owned drafts, linked
reports/matches, rule-only suggestions and both export types, then deletes only
confirmed/new hash-matched resources and related synthetic history. The real
PostgreSQL regression test checks this cleanup under forced RLS. A lost/in-flight
draft response retains the journal even if currently visible candidates are
removed. Failure to verify any cleanup is a failure, not a pass.

On interruption/outage, retain `work/phase2-verification-*.json`; never commit it.
Wait for all requests to settle. **Phase 5 journal recovery is manual review**:
confirm the same project/test users, compare baseline IDs and synthetic hashes,
inspect only listed/new provably synthetic resources, delete through the owner
API, verify private Storage cleanup, cascade reports and synthetic history, and
log out test sessions. Never delete a baseline object or an unproved candidate.
Do not feed a Phase 5 journal to Phase 2 recovery (it explicitly rejects it).
Phase 2-only journals retain the existing Phase 2 recovery procedure.

## Browser QA and data handling

`npm run test:e2e` runs only public cases; no account/settings/network writes.
`npm run test:e2e:live` contains two opt-in full-workspace scenarios (desktop and
mobile). Without `PHASE5_ALLOW_LIVE_WRITES=true`, both are explicitly pending/skipped.
No hosted tests were authorized or executed here.

Generate the synthetic DOCX fixture from the repo root:

```bat
python -m scripts.browser_fixture
```

Then privately inject the two dedicated account credentials/public Supabase
configuration, exact staging browser/API origins and the opt-in flag into the
browser process. Run from `web`:

```bat
npm run test:e2e:live
```

Never run `playwright codegen`, debug traces, headed credential screenshots, HTML
reports or verbose network diagnostics against these accounts. The custom live
reporter emits counts only; trace, screenshots and video are disabled, retries
are zero, and the browser suite is separate from ordinary CI. Its failures are
intentionally sanitized; reproduce with synthetic local mocks for diagnostics.
Browser cleanup deletes confirmed resume/draft IDs and downloads, logs out test
sessions, and retains a credential-free `work/phase5-browser-*.json` on uncertain
writes. API deletion retains minimal event history by design; the Python verifier
removes its own synthetic events. Browser-only events need operator review if
full test-account erasure is required; never mass-delete shared history.

The browser suite covers actual login/logout, upload, saved twelve-section report,
match visualization, rule-only guidance, draft save, PDF/DOCX downloads, document
activity, A/B denial, switching, missing-session redirect and backend error state.
It asserts responsive public layouts; authenticated overflow/layout, keyboard,
assistive technology and long-content pagination still need review with live
accounts. Clearing session cookies tests loss of session; server JWT exp/iat
verification is covered by backend tests, not a claim of waiting for a real JWT
expiry in browser QA. Loading is exercised with a delayed mocked backend outage;
no invented scoring responses are injected.

## Rollback and recovery (manual)

Keep an immutable known-good previous Vercel and Render release. On incident,
close writes/traffic or maintenance-gate the UI, preserve cleanup journals and
aggregate logs, then restore the previously reviewed frontend/backend pair.
Avoid running a Phase 4 backend against an unmigrated DB. Prefer forward fixes;
Phase 4's nullable additive columns allow an older backend to coexist with the
upgraded database, but do not assert automatic compatibility for untested releases.

Do not run `alembic downgrade` on live data as a routine rollback: 0002 downgrade
drops report links/kinds and loses that information. A database restore/PITR is
an explicit separate operator decision with potential post-backup data loss.
Restore into an isolated project first, verify RLS/ACLs/runtime/Storage consistency
and account/session behavior, reconcile incomplete uploads/deletions, and rerun
synthetic isolation/export checks before traffic resumes. Coordinate DB and
Storage recovery; a database backup alone is not an object-store backup.

## Launch gate

- [ ] Review and approve PR chain, provider plans/configuration and immutable SHAs.
- [ ] Backups/restoration validated; migration 0002 reviewed and applied manually.
- [ ] Restricted runtime, forced RLS, Data API denial and private Storage verified live.
- [ ] Exact HTTPS CORS, Auth callbacks/reset emails and public-only web env reviewed.
- [ ] Authenticated two-user live verifier and desktop/mobile browser workflows pass.
- [ ] Clean synthetic resources or all retained journals reviewed and resolved.
- [ ] Edge anonymous/invalid-auth rate protection, resource/load budgets and observability approved.
- [ ] Advisory risk reviewed; runtime audit clean; development build inputs trusted.
- [ ] Rollback rehearsal and operator approval to deploy/open traffic recorded.

**Current dependency review (2026-11-19):** [the detailed audit](DEPENDENCY_AUDIT_PHASE5.md)
records withdrawal of the root advisory and fresh full/runtime counts of zero,
with no dependency changes. Retain the historical checkpoint below for provenance;
it is not the current active-advisory count.

The original npm development report listed 17 high transitive affected packages
via picomatch GHSA-fc5q-39xc-vjpf; latest upstream remains 4.0.7, still affected.
No forced dependency override. Runtime npm audit is clean. Keep build tooling and
untrusted glob/path inputs confined to CI/local development, use `npm ci`, restrict
build secrets/PR permissions, and recheck upstream before release. This mitigation
is not a patch. No production readiness claim follows from local unit tests alone.

## Recorded automated results

Executed locally on Linux, Python 3.12.14, Node 24.22.1/npm 11.9.0. Windows and
hosted services were not used. CI configuration was authored, not remotely run.

| Check | Actual result |
|---|---|
| Complete pytest with a fresh disposable PostgreSQL 17 cluster | 238 passed, 0 failed, 0 skipped, 0 errors |
| PostgreSQL tests included above | 17 passed, including Phase 5 readonly revision audit, readiness and feature cleanup under real forced RLS |
| Frontend Vitest | 77 passed, 0 failed, 0 skipped, 0 errors |
| Public Playwright against local production Next.js / installed Chromium | 4 passed, 0 failed, 0 skipped (desktop and mobile) |
| Authenticated staging Playwright | 2 skipped/PENDING, 0 executed: no live-write permission or test credentials used |
| TypeScript / Next route type generation | Passed |
| ESLint --max-warnings=0 | Passed |
| Production Next.js build | Passed |
| pip check | No broken requirements found |
| Existing synthetic pipeline/15-template smoke | SMOKE OK |
| Local HTTP API + SIGTERM | Liveness 200, readiness 503 without cloud, identity 401, legacy upload 404; application shutdown completed; Uvicorn reraised SIGTERM (exit -15) |
| Public JS bundle heuristic scan | 0 candidate exposures |
| Git tracked-file/local-history heuristic scan | 0 candidate exposures; not proof of no historical exposure |
| Runtime npm audit | 0 advisories |
| Full development npm audit | 17 high transitive advisories, upstream latest picomatch 4.0.7 still affected |
| No-flag Python Phase 5 verifier | PENDING / exit 2, no network or database access |

Backend regressions cover quota bounds/reset/identity keys and correct 429 status,
startup/admin/TLS guards, redacted exception logging, fail-closed readiness,
public HTTPS CORS, retained ambiguous journals, selective rate-limit retry and
real PostgreSQL feature write/cleanup behavior. Existing Phase 1–4 tests remain.

No hosted Auth, private Storage policy, live user isolation, live migration,
provider integration, load/soak, Render/Vercel platform shutdown or Windows
execution is claimed. These and the launch checklist remain owner release gates.

### Windows test-environment isolation follow-up

Normal pytest now isolates inherited application/provider/libpq settings and
implicit dotenv loading before application imports. The offline migration test
explicitly enables dotenv only for its temporary synthetic-file subprocess and
still emits SQL without a database connection. Production loaders, guards, RLS
and authentication are unchanged. See [the Windows verification commands](WINDOWS_PHASE5.md#automatic-pytest-isolation-phase-5-pr-5-fix).

Regression results on Linux/Python 3.12: **227 passed, 0 failed, 17 skipped, 0
errors** both in an isolated checkout without `.env` and in a separate checkout
with a complete synthetic `.env` plus inherited cloud/migration credentials.
The synthetic file's contents were verified unchanged. A fresh local disposable
PostgreSQL 17 run passed **244 tests, 0 failed, 0 skipped, 0 errors**. The isolated
one-command runner also passed pip check and the existing synthetic smoke test.
No private developer env file was opened, modified or copied for these scenarios.
No live service was accessed. Native Windows remains pending; a Windows CI job
now executes standard pytest with synthetic inherited migration settings.

Disposable tests now require both an explicit loopback `TEST_POSTGRES_URL` and
`RESUMEIQ_TEST_POSTGRES_DISPOSABLE=true`. Query-based host overrides and remote
URLs are rejected before connecting; do not acknowledge a persistent local DB.
The existing Linux CI supplies the acknowledgement only for its fresh service
container. Without explicit opt-in, the usual 17 PostgreSQL skips are expected.


### Password-independent read-only staging mode

`--read-only` is a separate CLI branch with no live verifier construction,
credentials prompt, HTTP client, upload, cleanup or migration call. It reuses the
Phase 2 catalog assertions through a SELECT-only adapter, with server-enforced
READ ONLY transactions on runtime and separate revision-audit connections; both
are rolled back and disposed. It additionally checks exact ownership policies,
minimal runtime CRUD permissions and the Phase 4 ownership FK. Missing optional
Auth/deployment configuration and unexecuted hosted checks are PENDING.

The expected project reference must be supplied independently on the command
line before any file is read. Supabase/JWT origins, all configured DB endpoints,
roles, pooler username project suffixes and TLS options are validated before any
connection. The live CLI additionally pins its API origin before entering the
existing two-user workflow. Configuration comes only from the external selected
file via `dotenv_values(interpolate=False)`; no root dotenv discovery or inherited
secret fallback. The existing private staging file is neither moved nor modified.
Read-only checks do not prove that opaque API keys belong to the intended project;
that requires the separately approved live Auth/Storage checks.

Implementation and synthetic local regression tests do not authorize accessing
staging. No private staging file or real credentials were accessed during this
implementation. No migration, destructive PostgreSQL suite, staging connection,
remote operation, push or deployment was executed for this local-only change.

Latest local-only staging-automation verification: **254 passed, 0 failed,
17 skipped, 0 errors**; dependency check and synthetic smoke PASS. The 17
destructive disposable PostgreSQL tests were intentionally not run under this
authorization. These local/mock results do not establish staging or Windows
verification.
