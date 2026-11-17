# Phase 3 — Next.js frontend

The `web/` application is built on Phase 2 commit `fea7d61`. It leaves the Python
`frontend/`, Streamlit app, FastAPI contracts, migrations and database code intact.
It is a real authenticated client for the available cloud endpoints, not a static
demo. Phase 2 final live integration verification remains pending. No deployment,
merge, live infrastructure modification or payment processing is included.

## Install and run (Windows CMD)

Install Node.js **24 LTS** (tested with 24.22.1) and use the existing Python 3.12
backend environment. Frontend dependencies are pinned in `web/package.json` and
`web/package-lock.json`; use `npm ci` for reproducible installs.

From your repository root:

```bat
cd web
copy .env.example .env.local
npm ci
```

Privately edit `web/.env.local` with these **browser-public** settings only:

| Variable | Meaning |
| --- | --- |
| NEXT_PUBLIC_SUPABASE_URL | Exact HTTPS project origin, no trailing slash or path |
| NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY | Modern `sb_publishable_` key, never a secret/service-role key |
| NEXT_PUBLIC_API_URL | Exact FastAPI origin; HTTPS remotely or HTTP loopback locally |

A build-time environment guard rejects mistakenly provided backend secrets before
Next.js can inline them. It also rejects embedded credentials in public URLs and
non-publishable Supabase keys without echoing values. Missing configuration is
allowed to build only so the safe setup notice can render. The browser
configuration additionally rejects missing/malformed settings, embedded URL
credentials, remote plain HTTP, paths, and `sb_secret_`/legacy JWT keys. An
unconfigured installation shows a setup notice and disables auth submission;
protected routes redirect to login. No fake session or mock user is substituted.
`NEXT_PUBLIC_*` values are embedded at build time: rebuild after changing them.

In the private backend environment, configure the existing restricted runtime,
cloud Auth/Storage settings and explicit CORS origin. For this localhost setup:

```dotenv
CLOUD_ENABLED=true
API_ALLOWED_ORIGINS=http://127.0.0.1:3000
API_PUBLIC_MODE=true
API_LEGACY_UPLOAD_ENABLED=false
```

Use the existing Phase 2 setup guide for the remaining backend variables and
migrations. Do not put CLOUD_DATABASE_URL, CLOUD_MIGRATION_DATABASE_URL,
SUPABASE_SECRET_KEY, service-role keys, OpenAI keys or passwords in the Next.js
application or any NEXT_PUBLIC variable. Those backend settings are not needed
in `web/.env.local`. No migration is required for the frontend itself.

Start FastAPI from the repository root in its Python virtual environment:

```bat
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

In another CMD window:

```bat
cd web
npm run dev
```

Open `http://127.0.0.1:3000`. Do not mix `localhost` and `127.0.0.1`: browser cookie
origins, backend CORS and Supabase Auth redirect URLs must match the origin you
actually use. Hosting-level rate/concurrency/body limits and quotas remain
operator responsibilities; disabling the legacy route is not abuse protection.

## Supabase Auth configuration (operator action only)

Use the same Supabase project as the backend's trusted issuer/JWKS. Configure
email/password authentication, SMTP and email confirmation as appropriate. Keep
ES256 signing and the backend's signature/issuer/audience validation in place.

For the local origin, set Auth Site URL to `http://127.0.0.1:3000`. Allow the actual
callback URLs used by the client, including their next destinations:

```text
http://127.0.0.1:3000/auth/callback
http://127.0.0.1:3000/auth/callback?next=%2Fdashboard
http://127.0.0.1:3000/auth/callback?next=%2Freset-password
```

Use exact approved production URLs later; do not add production-wide wildcard
redirects or change infrastructure automatically. The application supports PKCE
code callbacks (`code`) and hashed email OTP callbacks (`token_hash`, type signup
or recovery). For cross-device email links where the original PKCE verifier
cookie is absent, operator-configured email templates can target:

```text
{{ .SiteURL }}/auth/callback?token_hash={{ .TokenHash }}&type=signup
{{ .SiteURL }}/auth/callback?token_hash={{ .TokenHash }}&type=recovery
```

Treat email links/callback queries as sensitive one-time capabilities; do not log
or share them. Framework request logging is disabled, and all pages set a
no-referrer policy. Configure external hosting/proxy/APM logging accordingly.
Live confirmation and password recovery depend on project email templates,
redirect allowlists and SMTP; these have not been changed or verified here.

## Authentication and data flow

1. Public login/signup/reset pages call Supabase Auth with the publishable key.
   Passwords are never sent to FastAPI or logged. Signup either receives a real
   session or shows a confirmation message. Recovery requires a valid signed-in
   user before updating the password.
2. `@supabase/ssr` maintains browser/server cookie state using the PKCE flow.
   Cookies are Secure in production (HTTPS required), SameSite=Lax and scoped
   to the application path. Use the development server for local HTTP.
   `src/proxy.ts` refreshes cookies. Protected App Router layout independently
   calls `getUser()` on the server and fails closed before rendering content;
   it never authorizes from an unverified client session alone.
3. Only safe account ID/email/creation-time props cross into the client layout.
   The Supabase SDK obtains access tokens for the FastAPI Authorization header.
   Browser fetches omit cookie credentials, disallow redirects and use no-store.
   FastAPI remains the final JWT and ownership authority.
4. HTTP 401 permits one token-refresh attempt. A second failure clears protected
   UI and redirects to login. Network/server failures do not silently become
   successful requests. Errors are mapped to sanitized text; provider bodies,
   codes, tokens, passwords and signed URLs are never logged by application code.
5. Document/history/analysis state is scoped to the current account. Account
   switching remounts the workspace and aborts stale loads. Logout uses Supabase
   **local** scope and clears protected UI, not every session on every device.
6. Uploads use multipart XHR for actual byte progress. The UI stops at 99% until
   validation/persistence succeeds, supports stopping a request, and refreshes
   Documents on uncertain outcomes. No POST retry occurs for timeout/network
   errors; only a rejected 401 is retried once after refresh. Stopping a request
   does not guarantee the backend stopped processing it.
7. Fetch requests have a 30-second deadline and uploads a 90-second deadline.
   List endpoints paginate in batches of 100 up to a safety ceiling of 10,000
   records; crossing it is an explicit error, not a misleading partial count.
8. Downloads are requested only after an explicit click. Strict validation
   accepts only the configured Supabase origin and Storage signing path, with
   positive TTL <=60s. A temporary “Save file” link uses no-referrer/noopener,
   is not prefetched or persisted, and disappears on expiry. Deletion requires
   an accessible confirmation dialog and refreshes the library after the result.

No direct Supabase table or Storage SDK operations are used by this frontend.
Backend secrets and owner IDs supplied by a caller are never used to authorize
requests. The SDK's browser-readable session cookies require normal XSS defenses:
user text is rendered as React text, never arbitrary HTML; do not introduce
third-party scripts or shared caching of authenticated pages. A production CSP
should be tested with Next.js scripts before rollout. Frontend route protection
complements, and never replaces, FastAPI JWT/ownership checks.

## Contracts used

`src/lib/api.ts` has strict runtime Zod schemas and inferred TypeScript interfaces.
No raw resume text/contact fields or arbitrary analysis JSON are assumed.

| Endpoint | Frontend use |
| --- | --- |
| GET /api/me | Profile identity verification |
| GET /api/v1/me | Versioned identity comparison |
| POST /api/v1/resumes | Single PDF/DOCX upload; 201 typed stored metadata |
| GET /api/v1/resumes?offset=N | Dashboard, library and selectors |
| GET /api/v1/resumes/{id} | Owned document details |
| POST /api/v1/resumes/{id}/download | Explicit short-lived download preparation |
| DELETE /api/v1/resumes/{id} | Confirmed owner deletion; empty 204 |
| GET /api/v1/analyses?offset=N | Saved analysis count and actual score trend |
| GET /api/v1/analyses/{id} | Typed client method ready for future summary detail UI |
| GET /api/v1/history?offset=N | Owned activity in dashboard/library |

Resume metadata includes generated filename, type, pages, word count, recognized
section labels, bullets, table/image counts and uppercase-heading flag. These
are extraction facts, **not ATS scores**. Analysis summaries contain ID, time
and nullable score only, with no resume association. Therefore a score is never
attached to the selected document. Null scores remain absent, not invented zeroes.
Dashboard charts use only real available summaries and have accessible tabular
alternatives. Loaded empty collections, API errors and loading are distinct.

## Pages and components

- `/login`, `/signup`, `/forgot-password`, `/reset-password`, `/auth/callback`:
  real Supabase Auth flows, accessible validation and generic error handling.
- `/dashboard`: real counts, average of non-null recorded scores, historical
  chart, recent documents, activity and navigation actions.
- `/analyzer`: upload and actual document overview, 12 horizontal report sections,
  recognized-section/format metadata and explicitly unconnected report sections.
- `/job-match`, `/improve`: editable browser-tab drafts, actual resume selector
  where relevant, copy controls and clear not-generated results. No fake matching
  or AI request is made. Execution controls remain disabled until backend support.
- `/builder`: three working frontend draft layouts (Essential, Editorial,
  Compact), live editable preview, validated JSON draft download and browser
  printing. These are not a false mapping to Streamlit's 15 server templates.
  Drafts are not cloud-saved; page refresh/navigation clears unsaved edits.
- `/documents`, `/documents/{id}`: real library, metadata, search, upload,
  owner download/delete and activity view. Original filenames remain private.
- `/upgrade`: structure only, no checkout/price claims or unavailable paid plans.
- `/profile`: server-authenticated account, backend identity check, password reset,
  copy-account-ID and local-session logout.

`components/` separates auth, shell, notifications/dialogs, document actions,
upload, dashboard/chart, report/workflow screens and the draft builder. Private
route errors use a sanitized error boundary; asynchronous operations have explicit
loading/error/empty states. Navigation is horizontal with a mobile disclosure.
Dialogs trap focus, close with Escape and restore focus. Styles support 650/900/
1100px responsive breakpoints, visible focus and reduced motion. Fonts are locally
bundled Geist packages; production builds need no Google Fonts network calls.

## Phase 4 integration dependencies

The existing Python engines are preserved, not recreated in the browser. Their
cloud HTTP endpoints do not exist yet. The page structure and API types must be
extended only after backend contracts are approved and ownership tested.

| Feature | Missing backend contract |
| --- | --- |
| Detailed analyzer sections | Owner-scoped analysis creation and detailed report retrieval, tied explicitly to a resume; impact, grammar, repeated words, contact checks, scores and recommendations |
| Job matching | Resume + job description comparison returning actual matched/partial/missing skills, match estimate and evidence |
| AI Improve | Grounded summary/bullet rewrite and keyword guidance endpoints, provenance, limits and explicit user review |
| Builder cloud saving | User-owned draft CRUD and template registry |
| Generated builder exports | Validated owner-scoped PDF/DOCX rendering/download, linked to supported server templates |
| Per-document score/history links | Explicit schema relationship between analyses and resumes; do not guess from timestamps |
| Billing | Out of scope; no payment integration or advertised paid entitlement |

No unofficial endpoint URL is silently called. Pending integrations are visible
in the UI and documented; there are no placeholder success responses or sample
scores mixed into production data. The existing local Streamlit application
continues providing its current analysis/matching/improvement/builder engines.

## Checks

From `web/`:

```bat
npm run typecheck
npm run lint
npm test
npm run build
npm audit --omit=dev
```

Component/API/Auth tests use synthetic fixtures and mocked Supabase/FastAPI calls.
Protected-layout tests validate server rejection and callbacks; session tests
cover local logout and stale in-flight data across account changes. They do not
claim actual email delivery, cookie exchange or live Supabase connectivity.

Browser test definitions are provided in `web/e2e/public.spec.ts`, configured for
desktop Chromium and Pixel-7-sized Chromium. No server/browser is automatically
installed or launched. On your own development machine, start `npm run dev` in
one terminal, then run in another:

```bat
cd web
npx playwright install chromium
set PHASE3_BROWSER_BASE_URL=http://127.0.0.1:3000
npm run test:e2e
```

These public-page tests exercise real route redirects and auth layout overflow at
both widths. Testing signed-in browser flows, uploads and actual confirmation/
recovery needs staging credentials, dedicated users and permission for writes;
follow the Phase 2 live verifier and test those flows without personal resumes.

In this managed session, `cua_repl.js` is unavailable. The Sites workflow requires
skipping browser QA rather than installing/launching a substitute browser/server.
No visual browser, responsive screenshot or Playwright execution is claimed.
The supplied browser tests are ready for operator execution. Local type/lint/
unit/build checks and existing Python regressions are recorded in the PR.

## Known development-tool dependency risk

The runtime-only audit reports **0 vulnerabilities**. The full audit reports
**17 high-severity affected development packages**, all propagated from the
single unpatched picomatch ReDoS advisory
[GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf).
The advisory lists all published versions through 4.0.7 and no patched version.
ESLint/Vitest glob tooling is development-only; application matching/upload code
does not accept or evaluate user-supplied glob patterns. Development servers bind
to loopback and should be used only with trusted source/configuration. Do not run
untrusted build/test configs or expose these tooling processes publicly. This is
an outstanding dependency risk, not a clean full-audit claim. Re-audit and update
the lock when the upstream patch becomes available; no unsafe forced downgrade
or unpublished package patch is applied here. ESLint 9 is pinned for compatibility
with the current Next config's plugin peer ranges; migrating to ESLint 10 awaits
compatible plugin releases.

Auth and builder forms also have POST-only native behavior and disabled
fieldsets in server-rendered HTML, enabled only after hydration. This prevents
pre-hydration/no-JavaScript GET submissions from placing passwords or resume
fields in URLs. Tests cover these server-rendered guards. The browser draft
builder remains local; JavaScript is required to edit/export it.

## Recorded verification — 2026-11-18

- Node 24.22.1 / npm 11.9.0: TypeScript check passed; ESLint passed with zero
  warnings; production Next.js 16.4.6 build passed, including all requested routes.
- Frontend Vitest: **65 passed, 0 failed, 0 skipped** across eight files. These
  are real local unit/component tests with synthetic provider fixtures, not live
  Supabase authentication tests.
- Python 3.12.14: complete existing backend suite against a fresh disposable local
  PostgreSQL 17 database: **192 passed, 0 failed, 0 skipped, 0 errors**. `pip check`
  reported no broken requirements and the existing smoke test returned SMOKE OK.
- Runtime dependency audit: zero vulnerabilities. Full development-tree audit:
  17 high affected packages propagated from the unpatched advisory described above.
- Four public browser test cases are defined (two tests at two viewport projects),
  but browser QA/Playwright was **not run** because managed browser tooling is
  unavailable. Responsive rendering and live cookie/email/upload flows require
  the documented operator checks before merge or deployment.
- No real credentials, live data writes, infrastructure changes, deployments or
  PR merges were performed. Phase 2 remains independently pending live sign-off.

Branch: `codex/phase-3-nextjs-frontend`, based on Phase 2 `fea7d61`. The frontend
PR should target `codex/phase-2-auth-database` while that backend PR is open; after
Phase 2 merges, retarget/rebase for the development branch as a separate reviewed
action. No direct commits to master or the Phase 2 branch are part of this phase.
