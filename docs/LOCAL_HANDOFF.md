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

## Phase 4 — Sales + Marketing Intelligence

The decision layer now goes beyond fixed geography rules:

- `dashboard.sales_intelligence` exposes expected final tickets, next-7/14-day ticket outlook, forecast risk, pace trend, and a per-screening priority score.
- `/v1/scenarios` now also returns `marketing_plan` with dynamic screening, geography, channel, and audience rankings for the selected budget.
- Geography ranking can change when imported campaign evidence changes. Distance is only a travel-friction prior when conversion evidence is absent.
- Attributed campaign tickets are treated as a signal, not proof of causal advertising lift.
- If no incremental CPA is configured, the application can rank test locations and allocate a planning budget but does not invent additional ticket sales.
- Ticket Sales now shows a forecast trajectory and expected new tickets over the next 7/14 days.

After applying this phase, run the existing backend suite, `npm.cmd run typecheck`, `npm.cmd test`, and `npm.cmd run build` before committing.

## Phase 5 — evidence ingestion and decision semantics

- Pre-sales baseline risk is now separated from action urgency. Before confirmed sales opening, next-7/14-day selling is N/A and paid action urgency is zero even when final-demand risk is high.
- Marketing output separates a what-if scenario allocation from the recommended paid spend today. Pre-sales/non-urgent screenings receive €0 current paid recommendation.
- Geography output is labelled `MARKET_TEST_PRIORITY` until evidence exists. Campaign attribution, CTR, and location-level website ticket-click CSV imports can change the ranking; website clicks are intent signals, not purchases.
- Ticket snapshots can be batch imported through `/v1/imports/ticket-sales` using `screening_id, observed_at, tickets_sold, note`. This supports repeated exports or an external collector without fabricating sales.
- Location traffic can be imported through `/v1/imports/traffic` using `date, geography_id, sessions, ticket_clicks, source`.
- Price analysis now includes elasticity sensitivity and only emits a robust revenue price when the same winner survives the tested elasticity range and clears a forecast-uncertainty threshold. A scenario-specific revenue leader is not automatically a recommendation.
- Live ESO/Meta/Google/analytics API synchronization still requires provider credentials or a stable provider-specific adapter. The current implementation provides safe ingestion boundaries rather than pretending those connections are live.
