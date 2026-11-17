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
