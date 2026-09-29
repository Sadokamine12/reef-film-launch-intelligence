# Local handoff — 29 September 2026

This is a working local evaluation build, not a deployed or production-certified service.

## Verified in the build environment

- TypeScript: `npm run typecheck` passed.
- Frontend: `npm test` passed, 6 tests.
- Backend: `node scripts/with-local-db.mjs .venv/bin/python -m pytest apps/api/tests -q` passed, 75 tests. Database integration tests used PGlite's PostgreSQL protocol; native PostgreSQL CI has not run remotely.
- Production frontend: `npm run build` passed, all application routes built.
- Playwright: 6 browser tests passed: navigation, persisted sales observation, creative creation, campaign CSV preview/import and report download, persisted business rules and invalid ceiling rejection, mobile navigation/overflow.
- Local launcher: started persistent database, migrations, seed, API and frontend; dashboard API returned HTTP 200. Screenshot captured from this running application.
- Windows/macOS startup scripts are included but have not been executed on Windows/macOS hardware. Verification used Linux, Python 3.12 and Node 22+.

Browser verification used an extracted Chromium binary because Playwright's browser download was unavailable in this environment. Ordinary local E2E setup uses `npx playwright install chromium`; the optional REEF_CHROMIUM_PATH variable supports an existing Chromium executable. The current Playwright API startup command is for Linux/macOS; on Windows run E2E under WSL. The main local application launcher supports Windows directly.

## Included workflows

The workspace includes Resolution with six February 2027 screenings, booking curves, grouped historical baseline forecasts, a Forecast & Scenarios decision lab, configurable decision/budget/economics rules, sales entry, historical ESO inventory, campaign drafts/status and CSV preview/import, creatives, geographic radii and zone metrics, management reports with CSV/print export, settings and audit records. Session authentication exists for the standard PostgreSQL deployment path; quick local testing explicitly bypasses login on loopback only.

## Remaining work and external connections

- The requested new GitHub repository has not been created or pushed. The connected GitHub tools did not expose repository creation. The original repository remains untouched.
- No public deployment or hosted production database has been provisioned. Deployment configuration is preparation only; hosting credentials, service selection, and production validation remain necessary.
- ESO ticket inventory, Meta Ads, Google Ads and website analytics are adapter interfaces, not live API connections. Manual observation and CSV imports work.
- Confirm screening times, official ticket URLs, ticket opening dates, business assumptions and the venue location before operational use.
- Baseline demand now uses a transparent ridge model over archived ESO inventory with event-grouped validation. Final attendance remains an extrapolation and the uncertainty range is a planning range, not a calibrated prediction interval.
- Price elasticity, incremental advertising response and cross-screening cannibalization are not identified by the current evidence. The scenario engine labels them as planning assumptions/user inputs rather than measured effects.
- OSM map tiles require internet. They were unavailable during screenshot capture; the UI displays this explicitly while preserving the zone overlays.
- Reports export CSV and support browser Print / Save PDF. Dedicated formatted Excel/PDF generation is future work.
- Review authentication, backups, monitoring, accessibility and production database migrations in the actual hosting environment before exposing the service.

## Repeat checks locally (Linux/macOS)

After setup:

```bash
npm run typecheck
npm test
node scripts/with-local-db.mjs .venv/bin/python -m pytest apps/api/tests -q
npm run build
npx playwright install chromium
node scripts/with-local-db.mjs node node_modules/@playwright/test/cli.js test
```

Stop START_LOCAL before E2E tests, since the test services use the same ports. E2E uses an isolated temporary database. Never point tests at production.
