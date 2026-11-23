# Windows CMD — Phase 5 local verification

Commands are CMD syntax, not PowerShell or Bash. Execution here was Linux only;
no Windows pass is claimed. Use Python 3.12 and Node 24 LTS. Never paste secrets
into commands; edit ignored private files or inject them through a secret manager.
Do not run live writes without explicit separate approval.

```bat
cd C:\path\to\Resume-IQ-Full-Stack-Development
git fetch origin
git switch codex/phase-5-production-readiness
git status --short --branch
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements-api.txt
python -m pip check
python -m pytest -o addopts="" -q --tb=short
python smoke_test.py
```

If the branch is not local, use
`git switch --track origin/codex/phase-5-production-readiness` once. Do not reset
an existing working tree. The default pytest invocation skips disposable-only
PostgreSQL tests; never set `TEST_POSTGRES_URL` to Supabase/persistent databases.
An optional fresh local Docker cluster can run that subset; see the Phase 4 guide.

Copy `.env.example` to `.env` only if no private `.env` already exists. Privately
fill local settings; use `CLOUD_ENABLED=false` for no-cloud liveness tests.
For local cloud integration use the restricted runtime, exact
`API_ALLOWED_ORIGINS=http://localhost:3000`, `API_PUBLIC_MODE=false` and
`API_LEGACY_UPLOAD_ENABLED=false`. HTTP origins are intentionally local-only.
If using 127.0.0.1 instead, configure that exact frontend origin consistently.

Terminal 1, from repo root with the virtual environment active:

```bat
python -m uvicorn backend.api:app --env-file .env --host 127.0.0.1 --port 8000 --no-access-log
```

Terminal 2:

```bat
cd C:\path\to\Resume-IQ-Full-Stack-Development\web
npm ci
npm run typecheck
npm run lint -- --max-warnings=0
npm test
npm run build
```

Privately configure `web\.env.local` using only the three public variables from
`web\.env.example`. No runtime/admin DB URL, secret API key or password belongs
there. Next.js public values are fixed at build time; rebuild after changing them.
Use `npm run dev` for local development, or use the production build for browser QA:

```bat
npm run start
```

Terminal 3 (from web, server running at http://127.0.0.1:3000):

```bat
npx playwright install chromium
npm run test:e2e
```

If using localhost or another local port, set the runner URL explicitly:

```bat
set "PHASE3_BROWSER_BASE_URL=http://localhost:3000"
npm run test:e2e
```

Open the local site in a browser for keyboard/viewport checks. Never use test
recordings/screenshots containing passwords. Live authenticated browser tests are
separate and require the dedicated accounts and explicit staging-write approval
in [the production guide](PRODUCTION_PHASE5.md). Do not infer approval from the
presence of an env file.

Read-only migration status inspection in a private operator terminal, repo root:

```bat
python -c "from dotenv import load_dotenv; from alembic.config import Config; from alembic import command; load_dotenv(); command.current(Config('alembic.ini'))"
```

This uses the operator-only `CLOUD_MIGRATION_DATABASE_URL`. Expect
`0002_feature_links (head)`. Do not put this variable in the API process or
Render/Vercel. Run the command in its separate terminal. No upgrade is implied.
Only after backup, review and explicit migration approval:

```bat
python -c "from dotenv import load_dotenv; from alembic.config import Config; from alembic import command; load_dotenv(); command.upgrade(Config('alembic.ini'), 'head')"
```

Health and rejection checks (do not add tokens to curl commands):

```bat
curl.exe --fail http://127.0.0.1:8000/api/health
curl.exe -i http://127.0.0.1:8000/api/ready
curl.exe -i http://127.0.0.1:8000/api/me
curl.exe -i -X POST http://127.0.0.1:8000/api/resume/upload
```

Liveness is 200; readiness is 503 without restricted cloud schema, otherwise 200.
No JWT =>401; disabled legacy upload =>404. Readiness alone does not test Storage
or Auth. Use the safe synthetic verifier only after explicit approval:

```bat
python -m scripts.verify_phase5
```

The no-flag command must print PENDING and exit 2 without connections. After the
operator has supplied dedicated settings and approved staging writes:

```bat
python -m scripts.verify_phase5 --allow-live-writes --expected-project-ref YOUR_STAGING_PROJECT_REF --expected-api-origin https://YOUR-STAGING-API.onrender.com
```

The private staging file also needs the separate
`PHASE5_MIGRATION_AUDIT_DATABASE_URL` for a READ ONLY version check. Read cleanup
journal instructions first. No migration runs automatically.


## Automatic pytest isolation (Phase 5 PR #5 fix)

Use the existing API environment; no manual clearing of cloud variables and no
shell-wide `PYTHON_DOTENV_DISABLED` setting is required:

```bat
cd C:\path\to\Resume-IQ-Full-Stack-Development
.venv-api\Scripts\activate
python -m pytest -o addopts="" -q --tb=short
```

Expected without an explicitly opted-in disposable database after the staging-mode
regressions: **254 passed,
0 failed, 17 skipped, 0 errors**. The 17 skips are PostgreSQL migration/RLS tests,
not suppressed unit failures. Root `.env` may remain in place unchanged.

For one command that runs pytest, dependency checks and the existing synthetic
smoke test with private dotenv/cloud/provider configuration excluded:

```bat
python -m scripts.verify_local
```

This reports PASS/FAIL counts and PENDING for disposable PostgreSQL and live/
platform verification. It does not provision a database, migrate live services,
modify `.env`, or use real API credentials. Failed subprocess output is suppressed
to prevent accidental credential diagnostics; rerun isolated pytest for details.
Temporary test reports are removed. A nonzero exit indicates a required check failed.

Isolation happens at the top of `tests/conftest.py`, before application imports.
Only the pytest process and its children are affected: inherited cloud, migration,
provider and libpq settings are stripped, dotenv auto-loading is disabled, and
safe cloud-off defaults are installed. Real HTTP transports/urllib are blocked
while MockTransport/ASGI remain usable. Database checkouts permit SQLite and only
the explicitly acknowledged disposable URL. The HTTP guard deliberately leaves
Windows asyncio's loopback self-pipe/socket-pair implementation intact.

The offline migration test alone removes the dotenv-disable variable in its child
environment, then explicitly loads a temporary synthetic file and emits `--sql`.
That exception neither loads the developer `.env` nor connects to PostgreSQL.
Production configuration loading and all production security guards are unchanged.

### Explicit disposable PostgreSQL only

Create a **brand-new local disposable** cluster first, never an existing database.
Both settings below are required in CMD. No URL is read from `.env`; remote
hosts, query-based host overrides and missing acknowledgement are rejected before
any test connection. The acknowledgement is not proof of disposability: confirm
the named container is fresh and contains no valuable data.

```bat
docker run --detach --rm --name resumeiq-isolation-test -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=resumeiq_test -p 127.0.0.1:55450:5432 postgres:17-alpine
docker exec resumeiq-isolation-test pg_isready -U postgres
set "RESUMEIQ_TEST_POSTGRES_DISPOSABLE=true"
set "TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55450/resumeiq_test"
python -m pytest -o addopts="" -q --tb=short
docker stop resumeiq-isolation-test
set "TEST_POSTGRES_URL="
set "RESUMEIQ_TEST_POSTGRES_DISPOSABLE="
```

Wait until pg_isready succeeds. Use a fresh container on every run because tests
create/drop roles, tables and grants. The previous isolation checkpoint ran **244 passed,
0 failed, 0 skipped, 0 errors**. The new staging-mode tests add 27 cases; that
expanded destructive PostgreSQL run was not executed under the local-only staging
automation approval. No live Supabase database was used to obtain these
counts. Windows execution remains pending unless the Windows CI/local run completes;
Linux success is not a Windows pass. A Windows CI job now runs standard pytest
with synthetic inherited migration settings.


## Staging verification from your existing private file

**Implementation is local only. No staging access is authorized yet.** The next
command below is for review; run it only after separately approving staging
read-only connections. It is not part of pytest or `scripts.verify_local`.

The verifier uses your existing file in place:
`%USERPROFILE%\ResumeIQ-Private\staging.env`. Do not move/copy it into the repo,
print it with `type`, put credentials on the command line, or pass the whole file
to the application server. It can contain operator-only audit credentials which
are forbidden in the deployed API environment. The tool never modifies that file.

1. Open CMD in the repository and activate the existing API environment:

```bat
.venv-api\Scripts\activate
```

2. Independently find the **staging project's Project Reference/Project ID** in
   Supabase project settings. This is a public identifier, not an API key, JWT,
   database password or original-project reference. Replace
   `YOUR_STAGING_PROJECT_REF` in the command. The independent pin is required even
   if the file contains `STAGING_PROJECT_REF`; both must match when present.
3. After separate approval of read-only staging access, run one command:

```bat
python -m scripts.verify_phase5 --read-only --expected-project-ref YOUR_STAGING_PROJECT_REF
```

The default path is exactly the private file above, resolved from USERPROFILE.
The equivalent explicit-path command, useful for review, is:

```bat
python -m scripts.verify_phase5 --read-only --env-file "%USERPROFILE%\ResumeIQ-Private\staging.env" --expected-project-ref YOUR_STAGING_PROJECT_REF
```

No test-user email/password, live-write flag, publishable key, secret Storage key,
API server or frontend deployment is required for this database audit. Inherited
shell variables and repository `.env` are not used as configuration fallbacks.
File interpolation is disabled; target URLs must be complete literal values.

Required existing settings (values stay private):

| Setting | Expected staging configuration |
|---|---|
| `SUPABASE_URL` | Exact `https://<staging-project-ref>.supabase.co` |
| `CLOUD_DATABASE_URL` | Restricted runtime URL for the same project, actual role `resumeiq_runtime` |
| `PHASE5_MIGRATION_AUDIT_DATABASE_URL` | Separate operator connection for read-only revision inspection; existing `CLOUD_MIGRATION_DATABASE_URL` is accepted as a fallback |

If both audit and migration variables exist, **every configured connection must
match staging**. Neither may point to the original project. They are never used
as the application's runtime. Runtime and audit database names must be `postgres`.
Direct hosts must be `db.<staging-ref>.supabase.co`; supported Supabase pooler
hosts must have the same project reference in the login username. A session-pooler
runtime username is `resumeiq_runtime.<staging-ref>`; the actual role checked by
PostgreSQL is still `resumeiq_runtime`. Prefer the session pooler for application
compatibility. Other hosts, Unix socket/host query overrides and unexpected URL
options fail before connecting. URLs require explicit TLS (`sslmode=require`,
`verify-ca` or `verify-full`; prefer hostname-verifying TLS with a trusted CA).

The tool checks configured JWT origins/ES256/audience and exact HTTPS CORS values.
Missing deployment/JWT settings are reported PENDING instead of requiring user
passwords. Public mode configured with legacy upload enabled is a FAIL.

Expected report labels:

- **PASS**: independently pinned staging routing/TLS, restricted runtime, denied
  PUBLIC/Data API grants, enabled **and forced** RLS, exact ownership policies,
  minimal CRUD grants and migration `0002_feature_links`.
- **FAIL**: mismatch, unsafe configuration, excessive permissions, missing/wrong
  policies/revision, denied required access, unavailable connection or timeout.
  Driver diagnostics and credentials are suppressed. Do not loosen protections
  to obtain PASS; review the private configuration and approved staging catalog.
- **PENDING**: deployment flags/URLs not configured, Render/Vercel setup, Auth
  redirects/emails, real JWT/Storage behavior, two-user tests and browser QA.

All audit connections begin with `SET TRANSACTION READ ONLY`, bounded statement
and lock timeouts, then run fixed SELECT/catalog queries and roll back. A narrow
adapter also rejects INSERT/UPDATE/DELETE/DDL, multi-statements and attempts to
turn read-only off. No login, migration, cleanup, journal creation, Storage
request, deployment or application-row write is reachable from read-only mode.
The role audit uses a transaction-local empty owner identity to check unscoped
row denial; this is session state only. READ ONLY does not grant new privileges.

### Optional integration tests: separate approval required

Only after explicit staging-write approval, dedicated exclusive test users and a
working staging API are available, review this separate command:

```bat
python -m scripts.verify_phase5 --allow-live-writes --expected-project-ref YOUR_STAGING_PROJECT_REF --expected-api-origin https://YOUR-STAGING-API.onrender.com
```

It uses the same existing private file. `PHASE2_API_URL` in that file must exactly
match the independent staging API origin pin. Local API testing can instead pin
`http://127.0.0.1:8000` if that process is intentionally configured for staging.
The tool does not infer an API target from Render/Vercel or deploy either service.
Missing/mismatched pins fail before login or database connection. Modern opaque
API keys cannot be bound to a project offline: valid key ownership, hosted JWT
verification and Storage policies remain checks of the approved integration run.

The existing two-user auth/isolation, synthetic PDF/DOCX upload, private Storage,
analysis/matching, rule-only improvement and builder/export checks are reused.
User passwords are securely prompted only in this approved write mode when absent
from the file. Cleanup retains the existing baseline/hash/ownership checks and
keeps its credential-free recovery journal on uncertainty. Never apply a migration
or replay a Phase 5 journal automatically. Exit 0 means the selected mode passed;
exit 1 means FAIL; no selected mode exits 2/PENDING without reading settings.

After the read-only report, remaining operator tasks are: review Render settings
and runtime-only secrets; deploy only with separate approval; verify `/api/ready`;
configure Vercel Root Directory `web` with public-only variables; set exact CORS
and Supabase Auth callback/reset URLs; run approved two-user/browser checks; then
review edge abuse protection, resource/load budgets, backups/rollback and launch
approval. Read-only database PASS is not proof of working Auth, Storage or deployment.


Local implementation verification (Linux/Python 3.12): **254 passed, 0 failed,
17 skipped, 0 errors**; pip check and synthetic smoke PASS. The 27 new staging
regressions use only temporary synthetic files and mock connections/transports.
They cover project/DB/JWKS mismatch rejection before connections, routing/TLS
restrictions, password-free read-only mode, inherited-config isolation, exact
private-path resolution with a synthetic USERPROFILE, write/DDL blocking,
rollback/redaction, and the separately pinned live-mode reuse. Native Windows,
staging access, migrations and deployments remain unexecuted.
