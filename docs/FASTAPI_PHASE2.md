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
4. Keep the service-role key and database URL only in backend environment/secrets.
   Never prefix them with `NEXT_PUBLIC_`, place them in browser code, or commit
   `.env`. Configure JWT verification and database as below. The service-role key
   bypasses Storage RLS: the backend's JWT and ownership checks are mandatory.
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
| `CLOUD_DATABASE_URL` | `postgresql+psycopg://...`; use TLS with `?sslmode=verify-full` and trusted CA in production |
| `SUPABASE_STORAGE_BUCKET` | Private bucket ID, lowercase alphanumeric, hyphen/underscore |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend-only Storage credential |
| `API_ALLOWED_ORIGINS` | Existing comma-separated exact HTTP(S) origins; no wildcard |
| `MAX_UPLOAD_MB` | Existing positive finite upload cap (parser cap also applies) |

`.env.example` contains placeholders only. `config` loads `.env` with real
environment values taking precedence. Separate Streamlit/API environments avoid
optional package conflicts. Cloud failure never silently redirects persistence to
SQLite. Database passwords with special characters must be URL-encoded.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-api.txt
# Export cloud settings securely before migrations/startup.
python -m alembic upgrade head
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

Alembic enables and forces RLS with USING and WITH CHECK owner policies using
`request.jwt.claim.sub`. With no setting, a nonprivileged role sees no rows. The
current FastAPI connection uses a **trusted backend role with BYPASSRLS**, so every
ORM query must retain its owner predicate; the backend does not impersonate users
with database session settings. Provision a separate runtime role with LOGIN and
BYPASSRLS, grant schema USAGE plus SELECT/INSERT/UPDATE/DELETE on only the four
cloud tables; use a separate migration-owner credential for DDL. Keep both out of
clients. A runtime role without BYPASSRLS will fail closed, not transparently work.
Do not grant these tables to anon/authenticated or expose them via public Data API
schemas. A BYPASSRLS credential compromise defeats database isolation. The RLS
test sets a transaction-local UUID only to verify policies with a restricted role.

Migration commands use `CLOUD_DATABASE_URL` only; SQLite is rejected. Startup
never runs migrations. Review/back up before production DDL. `alembic downgrade
base` **destroys cloud records**, so use it only in a disposable test database or
an approved rollback. It never touches existing local SQLite files/tables.

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
request/response bodies and signed URLs. Original local-app logs have their
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
CRUD ownership and verifies RLS using a restricted role. Without its environment
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
management or production observability. Storage service-role and BYPASSRLS roles
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
