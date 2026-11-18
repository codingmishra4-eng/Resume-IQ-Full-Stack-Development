# Phase 5 — automatic Windows frontend verification

The dedicated **Phase 5 Windows frontend verification** GitHub Actions workflow
runs Node.js 24 on `windows-latest`. No local Windows terminal commands are needed
to run its checks: open/update a PR targeting `codex/phase-5-production-readiness`
with frontend source or this workflow/documentation, then inspect its Checks tab.
Draft PRs are included. The workflow also declares `workflow_dispatch` for manual
runs when GitHub makes that workflow available in the repository Actions UI.

## Five required checks

Each command runs in `web/`, in order, and must succeed:

1. `npm ci` — install exactly the committed lockfile, without changing versions.
2. `npm run typecheck` — generate Next.js route types, then run TypeScript.
3. `npm run lint -- --max-warnings=0` — no ESLint errors or warnings allowed.
4. `npm test` — existing mocked unit/component tests; no live browser accounts.
5. `npm run build` — production Next.js compilation with no service configuration.

The log records actual Node/npm versions and separate check outcomes. A failed
step fails the job; no tests are disabled or ignored and no deployment follows.
A successful CI run verifies a fresh hosted Windows installation, not the state
of a developer's personal Windows checkout.

## Security and scope

- Read-only `contents` permission; all other token permissions are absent.
- Checkout does not persist Git credentials. No repository secret references,
  environment-specific deployments, service accounts or production credentials.
- No private dotenv files are permitted in the verification checkout, and no
  Supabase/cloud/public service configuration is accepted. The guard checks file
  presence and variable names only, without reading or printing their contents.
- No real Auth, Storage, uploads, migrations, backend startup or live tests.
- No Vercel/Render/Netlify commands or production configuration changes.
- npm dependency downloads and GitHub Actions/cache access are expected; this is
  credential-free service verification, not an air-gapped package installation.
- Supabase-dependent application flows remain unconfigured; unit tests use their
  synthetic mocks. Production integration must be separately approved/tested.
- Only the npm download cache is cached, not dotenv files or built private content.

The existing combined Phase 5 workflow has a narrow `paths-ignore` list for this
new workflow, this guide, and the combined workflow's own configuration file.
Consequently a PR changing only these automation/docs files runs the dedicated
Windows frontend checks without starting unrelated Python/PostgreSQL/cloud jobs.
Any other changed file still triggers the existing full combined workflow, and
its manual dispatch remains available. CI-only edits to the combined workflow
should also be manually validated when they affect its Python/job behavior; this
change only adjusts trigger paths. No existing backend or frontend test step was
removed from that workflow.

## Reading the result

1. Open the draft PR and find **Windows Node 24 frontend checks** in Checks.
2. Open Details to inspect each of the five steps and the reported tool versions.
3. PASS means the job completed successfully; FAIL requires reviewing the failed
   step and fixing the underlying issue; queued/running/unavailable is PENDING.
4. Do not infer a Windows PASS from Linux runs or an unexecuted workflow file.

The project and lockfile declare Node `>=24.0.0`; Node 24 is the verified target.
No dependency upgrades/overrides are part of this change. Existing development
advisories remain a separate review item; successful lint/tests/build are not a
claim that dependency audits or hosted integration have passed.

## Local verification recorded for this change

Linux, Node **24.22.1**, npm **11.9.0**. Checks ran in `web/` inside an isolated
copy of tracked frontend source; private dotenv files and inherited service
configuration were neither copied nor loaded. npm used a separate cache and empty
verification-only npm configuration files, without changing repository config.

| Check | Actual result |
|---|---|
| npm ci | PASS; committed dependency versions/lockfile unchanged |
| npm run typecheck | PASS |
| npm run lint -- --max-warnings=0 | PASS, zero warnings |
| npm test | PASS: 77 passed, 0 failed, 0 skipped, 0 errors; 10 files |
| npm run build | PASS |
| Workflow YAML/target/trigger consistency | PASS |

No genuine frontend failure was found, so no application source or package files
were changed. npm ci reported the existing 17 high dependency advisories; no
unsafe automatic fixes or forced overrides were applied. Windows status must be
read from the new job's actual result; local Linux success does not establish it.
Live Supabase flows, authenticated browser QA and deployment remain out of scope.
