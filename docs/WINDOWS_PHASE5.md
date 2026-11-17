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
python -m scripts.verify_phase5 --env-file .env --allow-live-writes
```

The private verifier environment also needs the separate
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

Expected without an explicitly opted-in disposable database: **227 passed,
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
create/drop roles, tables and grants. Expected full result: **244 passed,
0 failed, 0 skipped, 0 errors**. No live Supabase database was used to obtain these
counts. Windows execution remains pending unless the Windows CI/local run completes;
Linux success is not a Windows pass. A Windows CI job now runs standard pytest
with synthetic inherited migration settings.
