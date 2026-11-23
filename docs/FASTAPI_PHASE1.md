# FastAPI foundation — Phase 1

The API reuses the existing Python parser. Streamlit, analysis engines, builder,
and database models remain unchanged. This phase does not implement authentication,
PostgreSQL, private storage, ATS analysis APIs, or public production readiness.

## Install and run

Use Python 3.12 and a separate virtual environment for the API:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux instead:
# source .venv/bin/activate
python -m pip install -r requirements-api.txt
python -m pip check
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for the typed multipart request and response
schemas. The API dependency file includes the dependencies needed to execute the
existing Python tests; it does not install Streamlit or optional AI/NLP packages.
Continue using `requirements.txt` and `streamlit run app.py` for the original app.
Use separate environments to keep the API lock reproducible.

`requirements-api.in` records direct dependencies. `requirements-api.txt` pins the
entire resolved graph, tested on CPython 3.12/Linux. To update the lock, install the
input in a fresh environment, run the tests, and freeze that environment. Do not
freeze a shared environment containing unrelated packages. These are version pins,
not artifact hashes or a security certification.

## Configuration

Copy `.env.example` to `.env` or configure environment variables before startup:

| Variable | Default | Behavior |
| --- | --- | --- |
| `API_ALLOWED_ORIGINS` | Empty | Comma-separated exact browser origins, e.g. `http://localhost:3000,https://your-frontend.vercel.app` |
| `MAX_UPLOAD_MB` | `10` | Positive finite upload limit in MiB; existing parser limit also applies |

Restart the API after changing configuration. An empty origin list grants no
cross-origin browser access. Wildcards, credentials in origins, paths, trailing
slashes, and malformed origins fail startup. CORS permits GET/POST and the
Content-Type header; credentialed requests are disabled in this phase. Explicit
origins follow FastAPI's [CORS guidance](https://fastapi.tiangolo.com/tutorial/cors/).
CORS is a browser policy, not authentication or protection against direct HTTP
clients. No Supabase tokens or auth configuration are added in this phase.

## Endpoint compatibility and deliberate privacy changes

| Endpoint | Success contract |
| --- | --- |
| `GET /` | Unchanged 200: `{"message":"Welcome to ResumeIQ API"}` |
| `GET /api/health` | Unchanged 200: `{"status":"ok","application":"ResumeIQ"}`; liveness only |
| `POST /api/resume/upload` | Multipart field `file`; 200 envelope remains `{"success":true,"resume":{...}}` |

The upload endpoint still accepts PDF/DOCX and reuses `ResumeParser`. An example
request using your own document is:

```bash
curl -F "file=@resume.pdf" http://127.0.0.1:8000/api/resume/upload
```

The upload response is intentionally narrower. Clients using the old personal or
free-text fields must update. Only these fields are returned:

```json
{
  "success": true,
  "resume": {
    "file_name": "resume.pdf",
    "file_type": "pdf",
    "pages": 1,
    "word_count": 120,
    "section_order": ["skills", "education"],
    "bullet_count": 3,
    "tables_detected": 0,
    "images_detected": 0,
    "headings_look_caps": false
  }
}
```

The values above illustrate the schema, not a fixed analysis result. `file_name`
is a generated display name, not the uploaded filename. Raw text, section bodies,
contact data, emails, phones, URLs, arbitrary metadata, guessed names and free-text
warnings are not returned. Section names are limited to existing canonical names.
The parser still receives the complete document in memory; this endpoint does
not persist it, call AI, or write it into the database. Existing shared config
still creates its normal runtime directories/log file on import.

All application errors use `{"detail":"safe message","code":"stable_code"}`.
Validation errors remain HTTP 400, including oversize uploads, to preserve the
existing upload status behavior. Missing or non-file `file` fields remain 422.
Error details are now sanitized strings, not parser internals or Pydantic input
objects. Additional form fields and duplicate file fields are rejected with 400.
Unexpected exceptions yield a generic 500; their content is not serialized or
logged by the API handlers. Protocol-level CORS preflight rejections retain the
middleware's standard response.

| Code | HTTP status | Meaning |
| --- | --- | --- |
| `unsupported_format` | 400 | Extension is not PDF/DOCX |
| `empty_file` | 400 | No file bytes |
| `file_too_large` | 400 | File or whole request exceeds its limit |
| `invalid_file` | 400 | Mismatched content, corrupt, encrypted or unreadable document |
| `unsafe_document` | 400 | DOCX archive safety limit exceeded |
| `invalid_request` | 400 / 422 | Extra fields / missing or invalid file field |
| `http_error` | HTTP status | Malformed multipart, unknown route, unsupported method |
| `internal_error` | 500 | Unexpected server failure |

## Upload boundaries and limits

Validation follows a layered approach consistent with the
[OWASP file upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html):

1. Bound the whole POST body before multipart parsing, counting actual received
   bytes rather than trusting Content-Length, with 64 KiB reserved for multipart
   overhead. Buffering is bounded per request and also applies without a length
   header. A disconnected upload is discarded.
2. Accept one multipart file and no additional form fields. Starlette also applies
   its multipart field/part limits. Read at most the file limit plus one byte;
   reject empty files and oversized content before document parsing.
3. Allow only PDF/DOCX extensions. Do not use the uploaded name as a filesystem
   path; browser-supplied MIME types do not establish the actual document type.
4. Check PDF signature in its first 1,024 bytes. DOCX must be a Word ZIP container
   with `[Content_Types].xml`, `_rels/.rels`, and `word/document.xml`. Reject
   duplicate members, encrypted members, unsupported compression methods, more
   than 1,000 members, more than 50 MiB declared expanded content, or member
   compression ratios greater than 200:1. No ZIP members are extracted to disk.
5. Run the existing parser on a worker thread and return allowlisted metadata.
   Close the uploaded file even when validation or parsing fails.

These checks do not provide malware scanning, CPU/memory sandboxing for native
PDF/XML libraries, or a durable job queue. Archive limits inspect ZIP metadata;
they are not a proof that arbitrary files are safe. The bounded body buffer costs
up to the request limit per concurrent upload, in addition to parser memory.
Worker threads keep the event loop responsive but are not process isolation.
Hosting-level timeouts, concurrency/rate controls and further hardening are still
needed before public deployment. Authentication and per-user ownership belong to
Phase 2 and are not claimed here.

## Modules

- `backend/api.py`: existing import target and application factory.
- `backend/api_v1/router.py`: registers the existing paths without changing URLs.
- `backend/api_v1/routes/`: health/root and upload endpoints.
- `backend/api_v1/schemas/`: Pydantic multipart request and public response/error contracts.
- `backend/api_v1/settings.py`: isolated API environment validation.
- `backend/api_v1/errors.py`: consistent safe errors.
- `backend/api_v1/middleware.py`: body cap before multipart parsing.
- `backend/api_v1/upload_validation.py`: content and archive guards.
- `tests/api/`: endpoint, privacy, upload, configuration and request-boundary tests.

## Verification

```bash
python -m pytest -ra                  # Existing suite and API tests
python -m pytest tests/api -ra        # API tests only
python smoke_test.py                  # Existing synthetic pipeline/template check
python -m pip check                  # Dependency consistency
```

The tests use synthetic documents and mocked failure cases; they do not require
credentials or make live AI requests. See the pull request for actual execution
results. All existing Streamlit/business-logic source files remain unchanged;
passing unit/smoke tests does not establish production readiness or browser UI
feature parity.
