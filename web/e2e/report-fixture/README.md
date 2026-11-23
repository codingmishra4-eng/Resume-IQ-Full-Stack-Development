# Offline Analyzer UI checks

This test-only Vite harness renders the actual Analyzer and application shell with
synthetic fixtures. It is outside the Next.js application routes and is not shipped
as an application page. It replaces auth/workspace providers; no authentication,
backend or Supabase client runs. Playwright blocks non-loopback HTTP requests and
the fixture server disables dotenv loading.

From `web`, with dependencies and a Playwright Chromium browser installed:

```cmd
npm run test:e2e -- e2e/analyzer-report.spec.ts --workers=1
```

No running Next.js server, credentials, accounts or uploads are required. The
existing `public.spec.ts` still requires a separately started local Next.js server.
The live integration suite is separate and is not part of these offline checks.

The tests cover all six requested widths, keyboard navigation and accordion focus,
real fixture scores and word counts, missing findings, loading, errors, retries,
upload controls, long evidence text and reduced-motion layout. Synthetic values
are test evidence only, not results from a real candidate's resume.
