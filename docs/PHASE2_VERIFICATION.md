# Phase 2 final verification

This document separates automated **local evidence** from pending **live project
verification**. Manual checks reported by the operator (startup, JWT login,
restricted runtime, RLS/user isolation, endpoints and private bucket connectivity)
are useful but do not prove the complete file lifecycle or public deployment
security. This change does not deploy, migrate live data, provision accounts,
rotate credentials, merge PR #2 or start Phase 3.

## Targeted security changes

- The API now checks each newly checked-out database connection before using it:
  current_user must be `resumeiq_runtime` and must not have superuser, BYPASSRLS,
  CREATEROLE, CREATEDB or REPLICATION attributes. Checks are read-only and their
  transaction is rolled back. Admin connections fail with a sanitized error.
  This is checked at first database use, not by the liveness health endpoint.
  Migration/operator connections remain separate and are not constrained by the
  API-only guard. The live verifier independently checks its supplied runtime
  connection; a persisted synthetic upload proves that database matches the API.
- `API_PUBLIC_MODE=true` fails configuration unless
  `API_LEGACY_UPLOAD_ENABLED=false`. The latter disables the legacy upload path
  before any body parsing, including trailing-slash and reverse-proxy root_path
  variants. Both flags are
  strictly boolean. Default local Phase 1 behavior remains unchanged. The new
  authenticated endpoints still require verified JWTs.
- Public mode is an explicit operator setting, not automatic deployment detection.
  Verify the actual public ingress with the integration tool. Continue applying
  hosting body/time/concurrency/rate limits and per-user quotas. Authentication
  and disabling the legacy route are not resource-exhaustion protection.

## Safe local checks (no live credentials or writes)

From the repository root with the Python 3.12 virtual environment active:

```bat
python -m pip check
python -m pytest -ra
python smoke_test.py
python -m scripts.audit_phase2_secrets
python -m scripts.verify_phase2
```

The last command prints PENDING and exits **2** without loading `.env`, prompting,
connecting, or writing. Exit 2 is deliberately distinct from success (0) and
failure (1). The opt-in PostgreSQL tests are skipped unless TEST_POSTGRES_URL is
explicitly set. They are **destructive disposable-database tests**: never set
TEST_POSTGRES_URL to Supabase, your persistent runtime DB or any valuable database.
They run DDL/downgrades and create synthetic NOLOGIN roles only in local fixtures.

The secret audit scans tracked working-tree files and reachable local Git patch
history using heuristics. It emits only counts/status, not matching values or raw
patches. A zero count cannot rule out secrets in deleted/unfetched Git history,
external screenshots, chat, hosting logs, secret stores or ignored files. If a
candidate is confirmed real or a real credential was previously exposed outside
Git, rotate that credential with its provider and review access logs. Rotation
is an operator action; the audit never rotates or rewrites history automatically.
No real keys/passwords/URLs should be pasted into bug reports. Do not share raw
exception traces or test environment files.

## Live verifier prerequisites

The verifier is **not automatically run by pytest**. Run it only with explicit
permission for writes to a staging project and **two existing dedicated,
nonanonymous test accounts**, never personal/production users. Do not run other
workflows with these accounts while verification or recovery runs. It creates
Auth sessions, synthetic file uploads and test history; it deletes only confirmed
run-created resources/history and logs out only the sessions it opened (local
logout scope). It never creates/deletes users or runs migrations.

Required environment variables (all values stay private):

| Variable | Meaning |
| --- | --- |
| PHASE2_API_URL | Exact FastAPI origin: HTTPS, or HTTP loopback for local API |
| SUPABASE_URL | Exact HTTPS project origin |
| SUPABASE_PUBLISHABLE_KEY | Modern publishable key for dedicated-user login/client-denial probes |
| SUPABASE_SECRET_KEY | Backend-only modern key for bucket/read-only object/list checks |
| CLOUD_DATABASE_URL | Restricted runtime connection to the same database used by API |
| SUPABASE_STORAGE_BUCKET | Existing private resume bucket |
| PHASE2_TEST_USER_A_EMAIL / PHASE2_TEST_USER_B_EMAIL | Two distinct dedicated test accounts |

Passwords are requested through a secure terminal prompt. If echo cannot be
disabled, the verifier aborts; it never falls back to echoed input. For secure CI,
inject PHASE2_TEST_USER_A_PASSWORD and PHASE2_TEST_USER_B_PASSWORD from a secrets
manager into the process environment. Do not put actual passwords in commands,
repository files or shell history. Noninteractive runs without injected passwords
fail without prompting. Environment values take precedence over explicitly
loaded environment files. No admin/migration URL is used by this tool.

Configure the API to use restricted runtime credentials and disable legacy
upload **before** starting/restarting it. In your private backend `.env` use:

```dotenv
CLOUD_ENABLED=true
API_PUBLIC_MODE=true
API_LEGACY_UPLOAD_ENABLED=false
```

These are configuration flags, not deployment commands. Keep migration/admin
credentials out of the API environment. Start the existing FastAPI app locally
if needed, then run the verifier in a separate terminal. Fill the required test
settings privately via environment injection or an ignored environment file.
Do not use or commit real personal resumes: the verifier generates synthetic
DOCX and PDF in memory, including a unique random run marker.

Exact Windows CMD commands, from the repository root:

```bat
.venv\Scripts\activate.bat
python -m scripts.verify_phase2 --env-file .env --allow-live-writes
```

`--allow-live-writes` is the explicit authorization gate. Omitting it performs
no network/DB activity. Do not invoke the flagged command until staging test
credentials/accounts and permission for these writes are available.

## Live coverage and assertions

1. Read-only role/catalog audit: restricted runtime, no bypass/admin flags,
   RLS/FORCE RLS on all four tables, no PUBLIC/Data API role access to cloud or
   Alembic tables, and an unscoped runtime query seeing no resume rows. The
   actual Data API is also probed for anonymous, both test users and the backend
   key; none may read these application tables.
2. Bucket privacy using the backend key in **apikey only**, never Bearer.
3. Password login for both test users; UUID identity matches `/api/me`.
4. Missing/malformed JWT rejection on identity, resume and history endpoints.
5. Unsupported, empty, corrupt PDF/DOCX and oversized files rejected. The legacy
   unauthenticated upload must return 403/404 at the tested ingress.
6. Synthetic DOCX for A and PDF for B: real authenticated API upload, runtime
   PostgreSQL metadata lookup, ready state and safe user-scoped object path.
7. Owned list includes the record; other user's list excludes it. Other-user
   metadata read, signed download and deletion return 404.
8. Owner receives a signed URL of at most 60 seconds. It is fetched without
   credential headers, checked against the expected Supabase origin, and its
   bytes must equal the uploaded synthetic bytes. URLs are never printed.
9. Anonymous, owner and other-user raw Storage access/signing/listing cannot
   expose the object; public object URL access must be denied.
10. Owned upload history exists and does not include other user's resource IDs;
    response fields are explicitly checked for privacy.
11. Cleanup deletes through the owning API identity, verifies database absence
    and privileged Storage listing absence, removes only history for the confirmed
    test-created IDs via runtime RLS, then logs out both test sessions.

Output consists of fixed PASS/FAIL labels and check-group counts, not tokens,
passwords, URLs, keys, document text or provider exception bodies. HTTP/SQL
library logging is suppressed for the run. Group counts are not pytest counts.
Redirect following is disabled. Live success requires exit 0; any verification
or cleanup failure is exit 1. A failed preflight aborts the dependent checks.

## Failure cleanup and recovery

A private local recovery journal under ignored `work/phase2-verification-*.json`
contains UUIDs, object-relative paths, pre-run resume IDs and synthetic hashes;
it contains no credentials, signed links, personal filenames or resume text.
File creation requests mode 0600 on Unix; on Windows keep the working directory
under your private user ACL. Do not publish the journal or edit its IDs/hashes.

A `finally` block attempts cleanup after assertion failures, provider errors and
interruptions. It preserves pre-existing IDs. When an upload response was lost,
new candidate rows are adopted only if their stored bytes match this run's unique
synthetic hashes. Unknown, empty pending or mismatched objects are not deleted.
An ambiguous request or incomplete cleanup retains the journal and fails the run.
Outages, SIGKILL, expired credentials and server requests still in flight mean
cleanup cannot be guaranteed; the tool never reports these as a full pass.

After the server's old upload requests have settled, use fresh dedicated-user
sessions to replay the retained journal (replace the filename locally):

```bat
python -m scripts.verify_phase2 --env-file .env --allow-live-writes --cleanup-journal work\phase2-verification-RUN_ID.json
```

Recovery checks the configured role/bucket and account ownership again and
revalidates stored synthetic content before deleting retained records. Unverifiable
pending rows, orphaned files without metadata or persistent outages require an
operator to inspect the private journal and follow the documented interrupted-
operation maintenance procedure. Never use broad user-data deletion or the
Alembic downgrade as cleanup. Test accounts with a pending run must not be reused
for unrelated work until it is resolved. No live integration test is claimed
passed until resources/Storage cleanup is verified and exit status is 0.

## Completion gate

Local mocked/unit tests validate verifier behavior, not a real Supabase gateway.
Disposable PostgreSQL validates actual migrations/ACL/RLS and runtime guards,
not hosted project settings. Keep live password login, JWT/JWKS, actual Storage
upload/download/cleanup, direct access denial and public-ingress checks marked
pending until this tool runs successfully with authorized dedicated users.
Phase 2 is ready for final live verification; it is not declared fully complete
or production-certified solely from local tests or prior partial manual checks.

## Recorded local verification — 2026-11-18

CPython 3.12.14/Linux, with TEST_POSTGRES_URL explicitly pointing to a fresh
localhost-only disposable PostgreSQL 17 container:

- Complete `python -m pytest -ra`: **192 passed, 0 failed, 0 skipped, 0 errors**
  (9.33 seconds), including 13 real PostgreSQL tests.
- `python -m pip check`: no broken requirements.
- `python smoke_test.py`: exit 0, SMOKE OK; existing 15-template PDF/DOCX checks.
- Git diff whitespace check: passed.
- Local tracked-file/reachable-history secret audit: 0 candidates detected.
- Default live verifier invocation: PENDING, exit 2, no network/DB access.

The 192 tests include mocked two-user verifier runs and adverse/recovery cases;
they are **not 192 live Supabase tests**. No live login, project DB connection,
Storage mutation, migration, user provisioning, credential rotation, deployment
or PR merge was performed. Native Windows execution was unavailable; documented
commands are module invocations compatible with CMD and the tests preserve short
Windows-safe pytest IDs. The operator's previously reported manual checks were
not reclassified as a complete live pass. Phase 2 final live sign-off remains
pending the authorized dedicated-account run and verified cleanup.
