# Phase 2: authenticated cloud persistence

This optional backend layer preserves Streamlit and all Phase 1 contracts. It
adds no frontend, payments, deployment or local-data migration. Set
`CLOUD_ENABLED=false` (default) to use only the original features; protected
endpoints then reject requests with 401. Invalid enabled configuration fails
startup. Run on Python 3.12 with the pinned `requirements-api.txt` environment.

## Architecture and credential flow

```mermaid
sequenceDiagram
  participant C as Client
  participant A as Supabase Auth
  participant F as FastAPI
  participant J as Trusted Supabase JWKS
  participant P as PostgreSQL
  participant S as Private Supabase Storage
  C->>A: Sign in directly
  A-->>C: Access and refresh tokens
  C->>F: Authorization: Bearer access-token
  F->>J: Fetch/cache project public signing keys
  F->>F: Verify signature, issuer, audience, time claims, role and UUID sub
  F->>P: Query using verified user_id and resource ID
  F->>S: Backend credential; generated user/UUID path
  F-->>C: Allowlisted metadata (signed URL only on explicit request)
```

Supabase handles passwords, email verification, sessions and refresh-token
rotation. This backend never receives passwords or refresh tokens, issues tokens,
or stores tokens in SQLite/PostgreSQL. The future client must use Supabase's auth
client, protect its refresh tokens and refresh expired access tokens there. JWTs
are validated locally; logout/revocation does not immediately invalidate an
already-issued access token. Configure short access-token lifetimes. There is no
client implementation in this phase.

`backend/cloud/auth.py` derives `Identity.id` exclusively from verified `sub`.
The configured algorithm is exactly ES256 or RS256; HS256/legacy shared secrets,
unsigned tokens and attacker-selected key URLs are unsupported. `kid` selects a
key only from the configured project JWKS. PyJWT caches the keyset for 300s and
refreshes for unknown key IDs. It requires sub/iss/aud/exp/iat, verifies signature,
issuer, audience, expiration and iat, and validates nbf when supplied. The token
role must be `authenticated`, and sub must parse as UUID. All failures including
JWKS outages return identical 401 errors with `WWW-Authenticate: Bearer`; no
unverified fallback or user-ID override exists. Public account information is
only the UUID. No email/profile metadata is returned.

## Modules

- `settings.py`: explicit opt-in; strict URL/issuer/JWKS/algorithm/bucket validation.
- `auth.py`: injectable verifier and FastAPI current-user dependency.
- `models.py`, `database.py`: cloud-only ORM tables, ownership-scoped CRUD.
- `storage.py`: server-side Supabase REST adapter; no redirects or upsert.
- `routes.py`: typed versioned endpoints, metadata allowlists, storage workflow.
- `cleanup.py`: manual retry of old interrupted operations, with sanitized failure.
- `migrations/`: version-controlled cloud schema and RLS, not `create_all()`.
- `tests/api/test_cloud*.py`: local crypto/API fixtures and opt-in PostgreSQL test.

Paths above are under `backend/cloud/` except migrations and tests. Existing
`database/database.py`, `database/models.py` and their Streamlit consumers are
unchanged. The cloud database is never used implicitly by local business engines.

## Supabase and environment setup

1. Create a Supabase project and enable the desired sign-in methods in Auth.
   Configure an asymmetric signing key (ES256 or RS256) and matching algorithm
   below. Legacy HS256 projects must migrate their signing keys first.
2. Create a private bucket named `resumes` in Storage; leave public access off.
   Restrict allowed MIME types to PDF/DOCX and configure an appropriate size cap.
3. This design proxies every object operation through FastAPI. Do **not** grant
   anon/authenticated Storage access for this bucket. Review **all** existing
   `storage.objects` policies for broad grants (not just bucket-specific policies);
   ensure none permit clients to list/read/upload/update/delete this bucket.
   Default RLS with no granting policies denies direct client access. Do not
   disable Storage RLS. Use a dedicated bucket/project if broad existing policies
   cannot be removed safely. Do not edit Supabase-managed storage tables directly.
4. Keep the modern `sb_secret_` API key and database URL only in backend
   environment/secrets.
   Never prefix them with `NEXT_PUBLIC_`, place them in browser code, or commit
   `.env`. Configure JWT verification and database as below. The secret key grants
   privileged service-role access and bypasses Storage RLS: the backend's JWT and ownership checks are mandatory.
5. Run migrations explicitly, then start the API. Test direct anonymous/user-token
   bucket access denial and real upload/sign/delete against your own project
   before public use. These live Supabase checks have not been run here.

| Variable | Required when enabled / meaning |
| --- | --- |
| `CLOUD_ENABLED` | `true` to enable, otherwise `false`; no other values |
| `SUPABASE_URL` | HTTPS project origin, no path/trailing slash |
| `SUPABASE_JWT_ISSUER` | Exactly `${SUPABASE_URL}/auth/v1` |
| `SUPABASE_JWT_AUDIENCE` | Typically `authenticated`, explicitly required |
| `SUPABASE_JWKS_URL` | Exactly `${SUPABASE_JWT_ISSUER}/.well-known/jwks.json` |
| `SUPABASE_JWT_ALGORITHM` | Exactly `ES256` or `RS256`, matching signing key |
| `CLOUD_DATABASE_URL` | API-only `resumeiq_runtime` PostgreSQL connection; use TLS with `?sslmode=verify-full` and a trusted CA in production |
| `CLOUD_MIGRATION_DATABASE_URL` | Separate operator/admin connection for Alembic and cross-user maintenance; required by migration commands even while CLOUD_ENABLED=false; omit from deployed API secrets |
| `SUPABASE_STORAGE_BUCKET` | Private bucket ID, lowercase alphanumeric, hyphen/underscore |
| `SUPABASE_SECRET_KEY` | Backend-only modern `sb_secret_` Storage API key; required, never a publishable key or JWT |
| `API_ALLOWED_ORIGINS` | Existing comma-separated exact HTTP(S) origins; no wildcard |
| `MAX_UPLOAD_MB` | Existing positive finite upload cap (parser cap also applies) |

### Modern secret key migration

Replace the old `SUPABASE_SERVICE_ROLE_KEY` setting with `SUPABASE_SECRET_KEY`
in backend secrets and restart the API. This adapter requires an opaque modern
`sb_secret_` key; legacy service-role JWTs and `sb_publishable_` keys are rejected.
The old variable is not read and there is no fallback. With cloud mode enabled,
a missing or malformed secret fails startup without echoing its value. Configuration
repr omits the key and database URL. Cloud-disabled Streamlit/local usage still
requires no Supabase credentials. No database migration is needed for this change.

Storage REST requests carry the secret only in the `apikey` header, never in
`Authorization: Bearer`, a URL/query string, or a request body. The hosted
Supabase API gateway handles API-key authentication before Storage; this assumes
hosted Supabase (or a compatible gateway), not a bare self-hosted Storage server
expecting a legacy service JWT. The gateway's privileged access bypasses Storage
RLS, so backend user ownership checks remain essential. Operation headers cannot
override authentication. Private bucket checks, random owner-scoped paths,
non-upsert uploads, `DELETE /object/{bucket}` with `prefixes`, and
`POST /object/sign/{bucket}/{path}` with `expiresIn: 60` are retained.

Browser-to-FastAPI authentication is separate: users still send their Supabase
access JWT in Authorization and the backend still verifies ES256/RS256 signatures
against project JWKS. The server secret is never accepted as user identity or
returned to the client. Never use `NEXT_PUBLIC_` or browser environment variables
for this credential. Rotate secrets in backend settings, not JWT verification
settings; do not share actual credentials when troubleshooting.

References: [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys)
and [Storage REST reference](https://supabase.com/docs/reference/self-hosting-storage/introduction).
Local tests use synthetic keys and mocked HTTP transports. Live modern-key
Storage upload/sign/download/delete and key rotation still require verification
against the configured project; no live keys are required by tests or committed.

`.env.example` contains placeholders only. `config` loads `.env` with real
environment values taking precedence. Separate Streamlit/API environments avoid
optional package conflicts. Cloud failure never silently redirects persistence to
SQLite. Database passwords with special characters must be URL-encoded.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-api.txt
# Export CLOUD_MIGRATION_DATABASE_URL securely for explicit DDL.
python -m alembic upgrade head
# Use the separate runtime CLOUD_DATABASE_URL for API startup.
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

## Database and RLS

Revision `0001_cloud` creates only four new tables:

| Table | Payload / ownership |
| --- | --- |
| `cloud_resumes` | UUID PK, UUID user_id, unique server object path, pending/ready/deleting state, validated metadata JSON |
| `cloud_analyses` | UUID PK, UUID user_id, analysis summary JSON |
| `cloud_saved_resumes` | UUID PK, UUID user_id, builder data JSON |
| `cloud_history` | UUID PK, UUID user_id, event and resource UUID |

Every table has created_at/updated_at timestamps and a user_id index. Object paths
are unique, required fields are non-null, and resume lifecycle state has a CHECK
constraint. User UUIDs refer logically to Supabase identities; there is no FK to
`auth.users` so PostgreSQL can live outside Supabase. Supabase account deletion
therefore requires an explicit application data erasure workflow; it does not
cascade automatically. History resource IDs intentionally survive resume deletion
and have no FK. History contains event/UUID/timestamp only, not resume contents.

`CloudDatabase` enforces owner predicates for read/update/delete/list, accepts
verified ownership on create, uses parameterized ORM queries, and restricts update
fields so IDs/ownership cannot be reassigned. Individual reads lock rows during
transactions to serialize mutations. All lists cap at 100 with nonnegative offset.
Analyses/saved-builder CRUD is available as an internal persistence API; this phase
does not add an analysis-generation or builder HTTP endpoint or import local
history. Analysis list/detail responses explicitly expose only ID/time/ATS score.

Alembic enables and forces RLS on all four cloud tables. Both USING and WITH
CHECK require `current_user = 'resumeiq_runtime'` and an owner matching the
transaction-local `resumeiq.user_id` UUID. Missing identity yields no rows and
rejects writes. Invalid identity fails the query. The role-name predicate makes
the policy deny other roles even if they are accidentally granted DML (except
roles with BYPASSRLS/superuser privileges, which ignore policies).

The migration explicitly revokes **ALL table privileges** from PUBLIC and each
existing `anon`, `authenticated`, `service_role`, including `public.alembic_version`.
It checks effective privileges after revocation and aborts transactionally if
inherited/admin access remains. This is essential for `service_role`, which
bypasses RLS. Absent Supabase roles are skipped, so plain PostgreSQL needs no
Supabase functions or role provisioning. Policies do not require the runtime role
to exist when migrating. Tables and Alembic version tracking are explicitly in
`public`; ORM statements qualify this schema on PostgreSQL to prevent search-path
or temporary-table shadowing. Default privileges and unrelated objects are left
unchanged. Keep Data API exposure disabled as a separate defense.

The runtime has **NOBYPASSRLS**, and application owner predicates are still
required. `CloudDatabase.for_user()` creates an immutable request-local session
factory. Each PostgreSQL transaction sets the verified UUID with parameterized
`set_config(..., true)`, which has SET LOCAL lifetime; commit/rollback clear it.
An unscoped session explicitly clears identity and fails closed. All API database
transactions, including upload finalization, cleanup compensation and delete
history, use the same verified user scope. Independent requests never mutate a
shared identity. Local SQLite and Streamlit sessions do not run this hook.

This setting is not an independent authentication mechanism: a compromised
runtime DB credential or SQL injection could set a different UUID. Only the
trusted backend receives this credential; users cannot submit SQL or identity
settings. JWT verification, parameterized queries and ownership checks remain
mandatory. The Data API roles and PUBLIC must not receive runtime membership,
DML grants or runtime credentials.

Migrations use **CLOUD_MIGRATION_DATABASE_URL only**. No fallback to the API's
CLOUD_DATABASE_URL, no implicit SQLite migration and no startup DDL occur. Use a
separate table-owning/admin role for migrations. The migration creates no roles,
users or passwords and grants no runtime privileges automatically. The reviewed
operator script is [sql/phase2_runtime.sql](sql/phase2_runtime.sql).

Revision `0001_cloud` was hardened before this project's first application. If
an installation already stamped an older copy of `0001_cloud`, `upgrade head`
will not re-run it: prepare a new forward migration for that installation; do
not edit Alembic stamps or downgrade a populated database. `downgrade base`
**destroys cloud tables**, and belongs only in disposable tests or an approved
rollback. Never use the disposable integration tests on a live Supabase project.

### Dedicated runtime role and hosted Supabase

Use `resumeiq_runtime` with LOGIN only when its password has been securely
provisioned; NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOINHERIT, NOREPLICATION and
NOBYPASSRLS. It must not own tables, schemas or databases and must have no parent
role memberships. Required grants are CONNECT to the target database, USAGE on
public, and SELECT/INSERT/UPDATE/DELETE on only the four cloud tables. UUID keys
need no sequence grants. No Alembic table access, schema CREATE, DDL, TRUNCATE,
REFERENCES, TRIGGER, grant option or Auth/Storage-schema grants are needed.

The operator script validates administrative flags, unsafe memberships and
schema CREATE privileges before granting DML. It aborts if public schema CREATE
is inherited through PUBLIC; audit/fix schema ACLs with an operator rather than
revoking global privileges blindly and breaking unrelated Supabase applications.
Audit other existing PUBLIC grants/security-definer functions as well: a role
cannot opt out of privileges granted to PUBLIC. The script limits new grants to
ResumeIQ; it does not claim to isolate arbitrary existing public-schema code.

CREATEROLE and the admin's own BYPASSRLS flag are not sufficient evidence that
hosted Supabase will allow provisioning another bypass role. PostgreSQL 15's
rules require superuser for BYPASSRLS; newer versions permit it for suitably
privileged bypass roles, with additional role-administration requirements for
ALTER ROLE. Hosted restrictions can further limit this. Supabase's `postgres`
is managed, not an unrestricted superuser. **Do not test this by granting bypass
in production, grant `service_role` membership, or fall back to admin credentials
in FastAPI.** The supported secure alternative is the NOBYPASSRLS runtime and
transaction-scoped policy described above; no bypass grant is necessary.

References: [PostgreSQL 15 CREATE ROLE](https://www.postgresql.org/docs/15/sql-createrole.html),
[current CREATE ROLE](https://www.postgresql.org/docs/current/sql-createrole.html),
[Supabase roles](https://supabase.com/docs/guides/database/postgres/roles),
[Supabase inherited privileges](https://supabase.com/kb/troubleshooting/custom-role-inherits-privileges-that-were-not-explicitly-granted-ddaa1c).

### Exact Windows CMD procedure (operator actions, not executed by this PR)

Keep CLOUD_ENABLED=false and Data API automatic exposure disabled throughout
setup. Review backups/target project and the generated migration SQL first. Do
not paste passwords, URLs or keys into chat, shell history or PR comments.

1. In your local, ignored `.env`, privately configure CLOUD_MIGRATION_DATABASE_URL
   for your tested migration/admin connection. Reserve CLOUD_DATABASE_URL for
   the dedicated runtime, not that admin. Keep the migration URL out of the
   deployed API environment. Use the tested direct or session-pooler connection
   and TLS; provider pooler login formats may differ from the PostgreSQL role name.
2. Open **CMD**, from the repository root (adjust the path locally):

```bat
cd /d C:\path\to\Resume-IQ-Full-Stack-Development
.venv\Scripts\activate.bat
python -m pip install -r requirements-api.txt
python -c "from dotenv import load_dotenv; from alembic.config import main; load_dotenv('.env', override=False); main(argv=['history'])"
if not exist work mkdir work
python -c "from dotenv import load_dotenv; from alembic.config import main; load_dotenv('.env', override=False); main(argv=['upgrade','head','--sql'])" > work\phase2-migration.sql
```

Review `work\phase2-migration.sql`. The offline command does not connect to the
database. It contains DDL/privileges but no connection password. Existing process
environment variables take precedence over `.env`; use a fresh CMD window and
remove stale overrides privately before proceeding. The next command **writes
the selected database**; run it yourself only after review:

```bat
python -c "from dotenv import load_dotenv; from alembic.config import main; load_dotenv('.env', override=False); main(argv=['upgrade','head'])"
python -c "from dotenv import load_dotenv; from alembic.config import main; load_dotenv('.env', override=False); main(argv=['current'])"
```

3. As an authorized database operator, provision the runtime role separately.
   Example reviewed DDL (no password, initially NOLOGIN):

```sql
CREATE ROLE resumeiq_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOINHERIT NOREPLICATION NOBYPASSRLS;
```

Do not recreate an existing role; inspect its attributes/memberships first. The
migration and Python code do not run this statement. Run the reviewed contents
of `docs/sql/phase2_runtime.sql` through your admin SQL client to grant only the
required schema/table access. Separately grant CONNECT on the target database
if not already allowed (using its actual name). Provision a strong password
through a trusted tool's secure prompt, e.g. `\password resumeiq_runtime` in an
already securely configured admin `psql` session. Do not put the password in SQL
text or command arguments. Then explicitly `ALTER ROLE resumeiq_runtime LOGIN;`.
Supabase may require the operator's admin role to SET ROLE or adjust membership
administration rights; do not grant runtime membership to Data API roles.
4. Review/run [sql/phase2_verify_permissions.sql](sql/phase2_verify_permissions.sql)
   as admin. Expect no PUBLIC/Data API table grants, runtime DML only, no runtime
   bypass/admin attributes, and RLS/FORCE RLS on all four tables. If an inherited
   grant causes migration to fail, review that membership with the operator;
   do not ignore the error, disable RLS or broadly revoke unrelated app grants.
5. Privately configure CLOUD_DATABASE_URL for runtime, remove admin credentials
   from the API environment, and confirm `current_user = resumeiq_runtime` and
   `rolbypassrls = false` using your trusted DB client. Do not use anon,
   authenticated, service_role or postgres as the runtime login. Test a valid
   token plus two distinct users' upload/list/download/delete against staging
   before enabling CLOUD_ENABLED=true for production. Never run this repository's
   destructive PostgreSQL integration test against Supabase.


## API contracts

All new routes require `Authorization: Bearer <Supabase access token>`.

| Method/path | Success |
| --- | --- |
| GET `/api/me` or `/api/v1/me` | 200 `{ "id": "uuid" }` |
| POST `/api/v1/resumes` | Multipart `file`, 201 `{id,created_at,metadata}` |
| GET `/api/v1/resumes?offset=0` | 200 owned ready resume metadata array |
| GET `/api/v1/resumes/{uuid}` | 200 owned ready resume metadata |
| POST `/api/v1/resumes/{uuid}/download` | 200 `{url,expires_in:60}`, Cache-Control no-store |
| DELETE `/api/v1/resumes/{uuid}` | 204 empty response |
| GET `/api/v1/analyses?offset=0` | 200 owned analysis summaries |
| GET `/api/v1/analyses/{uuid}` | 200 owned summary |
| GET `/api/v1/history?offset=0` | 200 owned event/UUID/timestamp array |

`metadata` is exactly the Phase 1 `ResumeMetadata` allowlist. Responses never
expose raw resume text, uploaded personal filenames, object paths, service keys,
provider errors, contact information or arbitrary ORM JSON. Unknown and other-user
resources both return 404. Authentication errors are 401; file validation retains
Phase 1 400 codes; missing/invalid fields or UUIDs return sanitized 422; storage
workflow failures return 503 `cloud_unavailable`; unexpected failures return safe
500 `internal_error`. Errors use `{detail,code}`. The existing 422 error text is
retained for compatibility; it may refer to the file field for other invalid input.

```bash
# ACCESS_TOKEN is a short-lived access token obtained from Supabase Auth.
curl -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8000/api/me
curl -H "Authorization: Bearer $ACCESS_TOKEN" -F 'file=@resume.pdf' http://localhost:8000/api/v1/resumes
curl -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8000/api/v1/resumes
curl -X POST -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8000/api/v1/resumes/RESUME_UUID/download
curl -X DELETE -H "Authorization: Bearer $ACCESS_TOKEN" http://localhost:8000/api/v1/resumes/RESUME_UUID
```

Avoid shell history/log capture of real tokens. Interactive OpenAPI is at `/docs`;
header examples above show authentication. No credentials are included in source.
CORS now permits GET/POST/DELETE and Authorization/Content-Type for explicit
origins, with credentialed cookies disabled. CORS is not authentication.

## Storage consistency, retention and privacy

Original PDF/DOCX bytes go to Supabase over HTTPS; metadata/history go to
PostgreSQL. The existing Phase 1 bounded-body, size, signature, archive-bomb and
parser validation are reused before upload. Upload filenames become generated
`resume.pdf`/`resume.docx`; object names are random under `<verified-user-uuid>/`.
Original filenames are never paths. The adapter rejects traversal-shaped paths,
checks bucket privacy before upload/sign, disables redirects and overwrites,
and never gives clients the privileged credential.

A durable pending row is committed before Storage upload. On success the row
becomes ready and history is committed. On upload/finalization failure the object
and pending row are removed where possible. If cleanup fails, the intent remains
hidden from normal list/detail/download endpoints for later reconciliation.
Delete first commits a deleting tombstone, then idempotently removes the object,
then deletes metadata and records a history event. Failed deletes retain the
intent and can be retried with the same DELETE. PostgreSQL and object storage do
not share an atomic transaction; a lost response can leave a ready record while
a client retries and creates another upload. No idempotency-key contract is added.

Ready files remain until explicit deletion. No automatic ready-file expiry,
account erasure, backup purge or history expiry is implemented. Provider backups
and previously downloaded copies are outside this deletion operation. Signed URLs
are bearer capabilities valid for 60 seconds: sharing one shares download access,
and prior URLs are not immediately revoked by logout. Avoid logging/caching them.

For failed/crashed operations, **stop API traffic**, then run:

```bash
python -m backend.cloud.cleanup
```

Load operator environment variables first, including CLOUD_MIGRATION_DATABASE_URL
and the Storage settings (the module does not implicitly read `.env`). Cross-user
maintenance requires the separately managed admin/bypass connection, not the
unscoped NOBYPASSRLS runtime; keep it outside the deployed API environment.
It retries cleanup of pending/deleting rows older than 24h with row locks,
retaining intents on errors and printing only counts. Never run against active
uploads; quiescing avoids upload/cleanup races. Monitor pending/deleting counts
and run this maintenance regularly. A network-ambiguous commit may require
operator inspection; no always-on job worker exists in this phase.

Local Streamlit is unchanged: parsing/storage occur on its host in SQLite, with
optional OpenAI snippet transmission. In cloud mode resumes **leave the user's
device**. Cloud routes do not call AI or local logging-intensive scoring/builder
workflows. API failures discard provider exception text; no tokens/raw resume
contents are logged. Configure hosting/proxy/APM logs to redact Authorization,
request/response bodies, `apikey` headers and signed URLs. Original local-app logs have their
existing behavior and are not the cloud audit log.

## Verification and limitations

```bash
python -m pip check
python -m pytest -ra
python smoke_test.py
# Optional real integration: disposable PostgreSQL only (DDL/downgrade test!)
TEST_POSTGRES_URL=postgresql+psycopg://postgres@localhost:55432/resumeiq python -m pytest -ra
```

Local tests use real locally generated ES256/RS256 JWT signatures, mocked JWKS
retrieval and Storage, and SQLite fixtures for fast cloud ORM tests. Opt-in
PostgreSQL testing actually upgrades/downgrades/re-upgrades Alembic, exercises
CRUD ownership, Data API/PUBLIC ACL denial, inherited-grant rejection, and
NOBYPASSRLS request isolation using NOLOGIN disposable roles. Without its environment
variable it is explicitly skipped. No live Supabase credentials/project were
available: real JWKS rotation, login/refresh, bucket access policies, signed
URL downloads and Storage failure semantics still need project integration tests.

The unchanged `POST /api/resume/upload` is **unauthenticated**, metadata-only and
nonpersistent. Root/health are unchanged too. Before a public deployment, block
that legacy path at the ingress or restrict it to a private/trusted network, and
apply rate limits, concurrency/time/body limits, and quotas. This preserves its
Phase 1 contract without silently making it public-ready. Apply abuse protection
to authenticated uploads as well; JWT authentication alone does not stop resource
exhaustion. No deployment is performed by this change.

Further limits: no malware scanner, process sandbox, account cleanup webhook,
per-user storage quota, immediate access-token revocation, integration CI secret
management or production observability. Storage secret keys and the migration/admin credentials
are powerful credentials. Review grants, backups, encryption/TLS, project region,
retention requirements and Supabase integration before production use. Unit tests
and a disposable PostgreSQL test do not certify production security or browser UI.

### Recorded verification (2026-11-14)

On CPython 3.12.14, the full suite with disposable PostgreSQL 17 enabled passed
132 tests, with 0 failures, 0 skips and 0 errors. `python -m pip check` reported
`No broken requirements found.` `python smoke_test.py` exited 0 with `SMOKE OK`
and exercised all 15 PDF/DOCX templates. These checks include existing Phase 1
and local business-logic tests, not a Streamlit browser interaction test. The
PostgreSQL test includes row-lock contention as well as migrations/RLS/CRUD.
Supabase calls remain mocked and do not count as live Supabase verification.


### Modern API key update verification (2026-11-15)

On CPython 3.12.14/Linux: `python -m pytest -ra` passed 147 tests with 0 failures,
1 skip and 0 errors. The existing PostgreSQL integration test was skipped because
`TEST_POSTGRES_URL` was unset; no new skip was added. `python -m pip check` reported
no broken requirements and `python smoke_test.py` exited 0 with `SMOKE OK`.
The modern-key HTTP contract and success/error response/log privacy tests use
HTTPX MockTransport and synthetic credentials, not a live Supabase project.

### Migration/runtime hardening verification (2026-11-15)

On CPython 3.12.14/Linux with explicitly local disposable PostgreSQL 17:
`python -m pytest -ra` completed with **162 passed, 0 failed, 0 skipped, 0 errors**.
`python -m pip check` reported no broken requirements. `python smoke_test.py`
exited 0 with `SMOKE OK`. No Supabase connection, live migration, real login
user creation or deployment was performed. The integration fixture creates only
synthetic NOLOGIN roles in its disposable container.

Coverage includes plain PostgreSQL without Supabase roles; Supabase-like
new-table/default ACLs; transactional rejection of inherited Data API access;
PUBLIC and all three Data API roles denied cloud/Alembic-table privileges,
including the bypass service_role; restricted runtime grants; per-table RLS
read/write/ownership reassignment denial; identity reset and concurrent user
isolation; row locks; schema shadowing; authenticated upload/history/delete
through a NOBYPASSRLS connection; offline dotenv-loaded migration commands and
separate migration URL enforcement. Windows CMD syntax is documented, but native
Windows and live Supabase provisioning are not claimed as verified here.
