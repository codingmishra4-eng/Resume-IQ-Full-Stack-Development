# Phase 5 dependency advisory review

Review date: **2026-11-19 (Asia/Kolkata)**. Base:
`codex/phase-5-production-readiness` at
`168260ef85977b01abf2f2e2cff177ae0005ac42`. PR #6 and PR #7 are separate
unmodified branches; their historical results are not overwritten by this review.

## Finding: withdrawal, not a dependency patch

The previous report's **17 high entries represented one root advisory propagated
through 17 package names**, not 17 independent CVEs. The root was
[GHSA-fc5q-39xc-vjpf / CVE-2026-112366](https://github.com/advisories/GHSA-fc5q-39xc-vjpf),
covering repeated-extglob regex denial of service in picomatch. GitHub now marks
it **withdrawn on November 18, 2026**. The original affected range was `<=4.0.7`;
no patched version is listed, and npm's current `latest` is still **4.0.7**.

The [upstream discussion](https://github.com/micromatch/picomatch/pull/235)
contains the maintainer's dispute of the security classification and closure of
the proposed patch. This review does not silently turn that dispute into proof
that all regex patterns are safe. Do not accept attacker-controlled globs.

A fresh npm registry audit now returns zero findings on the **unchanged** lockfile.
No package was upgraded, downgraded, overridden, vendored or excluded to obtain
that result. The lower count is an advisory-database change, not a code-level fix.

| Measurement | Full audit | Production-only audit |
|---|---:|---:|
| Earlier Phase 5/PR #7 checkpoint | 17 high, 17 total | 0 |
| Fresh audit before this review's changes | 0 high, 0 total | 0 |
| Repeated audit after frontend verification | 0 high, 0 total | 0 |

All current severity buckets (critical/high/moderate/low/info) are zero. These are
point-in-time npm results, not proof of absence of vulnerabilities, bundled-code
issues or future advisories. Audit errors must fail CI, not become a zero count.

## Historical package inventory and dependency chains

Installed versions below come from the committed `web/package-lock.json` and
`npm ls`/`npm explain picomatch` in an isolated installation. Historical ranges
are the previous npm report's **propagated metavulnerability ranges**, except the
root picomatch row, which uses the original advisory range. All seventeen package
nodes are marked `dev: true`; none is a direct production dependency.

| Package | Installed version(s) | Directness/scope | Historical affected range | Route to root |
|---|---|---|---|---|
| `@next/eslint-plugin-next` | 16.4.6 | Transitive dev | `>=14.3.0-canary.0` | fast-glob → micromatch → picomatch |
| `@typescript-eslint/eslint-plugin` | 8.73.0 | Transitive dev | `>=8.47.1-alpha.0` | parser/type-utils/utils → typescript-estree → tinyglobby |
| `@typescript-eslint/parser` | 8.73.0 | Transitive dev | `>=8.47.1-alpha.0` | typescript-estree → tinyglobby |
| `@typescript-eslint/type-utils` | 8.73.0 | Transitive dev | `>=8.47.1-alpha.0` | typescript-estree/utils → tinyglobby |
| `@typescript-eslint/typescript-estree` | 8.73.0 | Transitive dev | `>=8.47.1-alpha.0` | tinyglobby → picomatch |
| `@typescript-eslint/utils` | 8.73.0 | Transitive dev | `>=8.47.1-alpha.0` | typescript-estree → tinyglobby |
| `@vitejs/plugin-react` | 6.3.0 | **Direct dev** | `>=6.0.0-beta.0` | Vite peer → picomatch/tinyglobby |
| `eslint-config-next` | 16.4.6 | **Direct dev** | `>=14.3.0-canary.0` | Next plugin / typescript-eslint → chains above |
| `eslint-import-resolver-typescript` | 3.10.1 | Transitive dev | `>=3.8.0` | tinyglobby → picomatch |
| `fast-glob` | 3.3.1 | Transitive dev | `>=3.0.0` | micromatch → picomatch |
| `fdir` | 6.5.0 | Transitive dev | `>=5.2.1` | picomatch peer |
| `micromatch` | 4.0.8 | Transitive dev | `>=4.0.0` | picomatch 2.3.2 |
| `picomatch` | **2.3.2, 4.0.7** | Transitive dev | **`<=4.0.7`** | Root advisory |
| `tinyglobby` | 0.2.17 | Transitive dev | `*` | picomatch 4.0.7; fdir peer route |
| `typescript-eslint` | 8.73.0 | Transitive dev | `>=8.47.1-alpha.0` | parser/plugin/utils/estree chains above |
| `vite` | 8.3.8 | Transitive dev | `>=6.3.0-beta.0` | picomatch 4.0.7 / tinyglobby |
| `vitest` | 5.1.0 | **Direct dev** | `>=3.1.2` | picomatch / tinyglobby / Vite peer |

**Fixed-version column for every row: no applicable published root fix.** Parent
packages had propagated alerts rather than separate advisories with independent
fixed releases. Current classification is withdrawn, not “patched in latest.”
The old npm report's top-level picomatch metavulnerability range was `*`; that
must not be confused with the root advisory's original `<=4.0.7` range.

Representative full chains (arrows include resolved peers where noted):

- eslint-config-next@16.4.6 → @next/eslint-plugin-next@16.4.6 → fast-glob@3.3.1
  → micromatch@4.0.8 → picomatch@2.3.2.
- eslint-config-next@16.4.6 → typescript-eslint@8.73.0 →
  @typescript-eslint/typescript-estree@8.73.0 → tinyglobby@0.2.17 → picomatch@4.0.7.
- eslint-config-next@16.4.6 → eslint-import-resolver-typescript@3.10.1 →
  tinyglobby@0.2.17 → picomatch@4.0.7.
- tinyglobby@0.2.17 → fdir@6.5.0 → picomatch@4.0.7 (resolved peer).
- vitest@5.1.0 → picomatch@4.0.7, and vitest → tinyglobby → picomatch.
- vitest@5.1.0 / @vitejs/plugin-react@6.3.0 → vite@8.3.8 (peer)
  → picomatch@4.0.7 / tinyglobby@0.2.17 → picomatch.

There are four locked picomatch package locations: root 2.3.2 plus copies under
`tinyglobby`, `vite` and `vitest` at 4.0.7. The historical npm count grouped these
under one package entry; it did not mean four additional independent advisories.

## Applicability to ResumeIQ

The identified ReDoS scenario requires dangerous patterns reaching the regex/glob
compiler and matching inputs in a running Node process. ResumeIQ does not offer
user-supplied glob evaluation: source searches found no application imports or
calls to picomatch, micromatch or these glob APIs. Job descriptions/resumes do not
become frontend build/test glob patterns. ESLint/Vitest use reviewed repository
configuration and fixed test/source globs. No hostile-pattern benchmark was run.
This is a source/configuration reachability assessment, not formal verification.

**Do not infer “no runtime glob code” from dev-only flags.** The production
`next@16.4.6` package also vendors an unversioned bundled picomatch implementation
under `next/dist/compiled/picomatch`. Its inspected image local/remote-pattern
helpers compile server-configured patterns; the application does not configure
custom image remote/local glob patterns. This vendored copy is outside the
seventeen lockfile package entries and cannot be assigned the root package's
version from its bundled manifest. A production-only npm audit does not enumerate
all embedded library versions. Future dynamic pattern/config changes need review.

Build/dev/test processes can still be harmed by pathological configuration, and
untrusted PR/build configuration can execute code independently of this advisory.
Keep dev servers private, run builds in isolated workers, set time/resource limits,
withhold production secrets from PRs, and do not introduce untrusted globs. These
controls remain useful after withdrawal. Supply-chain/provenance and hosted Auth,
Storage, RLS and application correctness are separate from this dependency audit.

## Minimal compatible update decision

Keep package.json and package-lock.json unchanged. No current registry advisory
requires a security version bump, and no patched picomatch release exists to test.
Do not run npm audit fix --force. The earlier report's suggested major downgrades
(eslint-config-next to 14.2.35, @vitejs/plugin-react to 5.2.0, Vitest to 3.1.4) do
not establish a fixed picomatch version and would cross the tested Next/Vite/Vitest
compatibility boundary. Do not vendor an unmerged patch or replace all 2.x/4.x
copies with a single major override merely to suppress a scanner.

Any future patched release should be updated within its parent-compatible major
range first, then verified through npm ci, both audits, typecheck, zero-warning
lint, all tests and a production build on Linux and Windows. No advisory ignore
or exception is added here. All future reported vulnerabilities fail the new
full audit gate; a withdrawal is not an allowlist.

Unchanged manifest SHA-256:
`01ad4f9b6eb0b3ee8e59c7f32b1cfbe5062e74483e2cd739d468af1371a293d2`.
Unchanged lockfile SHA-256:
`8d9cd39af453e29225863bc4a0aa69188a754561af69c7a7308480ae1bb96082`.

## Verification and CI

The local installation copied only tracked frontend source into an isolated
`web/`, excluding private dotenv/configuration and inherited service credentials.
Tooling used Node 24.22.1 / npm 11.9.0 on Linux. Actual results:

| Check | Result |
|---|---|
| Clean npm ci | PASS |
| Fresh full audit before changes | PASS, zero findings |
| Fresh production-only audit before changes | PASS, zero findings |
| Typecheck | PASS |
| ESLint --max-warnings=0 | PASS, zero warnings |
| Frontend tests | PASS, 77 passed / 0 failed / 0 skipped / 0 errors |
| Production build | PASS |
| Repeated full and production-only audits | PASS, zero findings in both |
| npm explain picomatch / locked inventory | PASS |

The new dedicated audit workflow repeats installation, five frontend checks and
both strict JSON audits on Node 24 with **Linux and Windows** runners. It uses
contents:read, non-persistent checkout credentials, no repository secrets or live
service configuration, and uploads only npm audit JSON reports for seven days.
No browser accounts, Supabase access, migrations or deployment are involved.

The combined Phase 5 workflow excludes documentation and these audit-only CI
files so this review does not start unrelated database/migration jobs. Other
source changes still run it, and its explicit manual trigger is unchanged.
PR #6/#7 refs and metadata are not modified. Matrix CI status must be checked from
its actual run; local Linux results are not a Windows claim.
