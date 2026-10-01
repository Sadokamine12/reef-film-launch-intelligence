# REEF Launch Intelligence — local evaluation build

New Next.js + FastAPI application for Resolution at ESO Supernova. Standard PostgreSQL is the production database. No Supabase dependency.

## Quick start: Windows

1. Install **Node.js 22 LTS or newer** and **Python 3.12**. Enable Python's launcher during installation.
2. Extract the whole ZIP into a normal writable folder (do not run it inside the ZIP).
3. Double-click **SETUP_LOCAL.cmd**. The first setup downloads dependencies and builds the frontend. Internet is required.
4. When setup finishes, double-click **START_LOCAL.cmd**.
5. Open **http://localhost:3000**. Keep the terminal open.

If you have Python 3.13+ instead of 3.12, open a terminal in the folder and run `python scripts/setup-local.py` (or `py -3.13 scripts/setup-local.py`). Then run START_LOCAL.cmd.

## Quick start: macOS / Linux

Install Node.js 22+ and Python 3.12+, extract the ZIP, then in Terminal:

```bash
cd /path/to/reef-launch-intelligence
bash SETUP_LOCAL.sh
bash START_LOCAL.sh
```

Open **http://localhost:3000**. Stop with Ctrl+C.

## What local mode does

- Starts a persistent **PGlite development database** (a PostgreSQL WASM build), FastAPI on port 8000 and Next.js on port 3000.
- Binds the services to 127.0.0.1. This is for testing on your own computer.
- Enables an explicitly labeled local sign-in bypass. No password is required in this mode.
- Keeps your observations, campaigns and settings in `.local/local-test-database`; closing the terminal does not erase them.
- Does not launch ads, connect to Meta/Google APIs or scrape ESO automatically.
- Does not require Docker or a PostgreSQL installation for the quick local test.

**Use exactly http://localhost:3000 for the local launcher.** A different origin may be rejected when saving. If ports 3000, 8000 or 55432 are occupied, close the other program first.

## Test the workflows

1. Dashboard: inspect the initial planning state and the “WHAT SHOULD WE DO TODAY?” section.
2. Ticket Sales: record a cumulative ESO ticket count. No sales are invented in the seed data. Three-/seven-day pace needs observations covering that full period.
3. Forecast & Scenarios: test ticket price, any analytical advertising budget, attendance target and optional REEF economics. Price elasticity and ad response are always labeled as assumptions unless evidence exists.
4. Settings: enter official booking links and confirmed times/opening dates. A future confirmed opening still stays in pre-launch until that date.
5. Campaigns: create a draft, linked to a screening, creative and geography. Drafts do not reserve budget. Imported dates must be within its start/end dates.
6. Download the CSV template. Add `date,spend_eur,impressions,clicks,landing_page_views,attributed_tickets` rows. Preview before saving. Blank ticket attribution stays unknown; Google “Conversions” is not automatically ticket sales.
7. Creatives and Geography: inspect the metrics after importing campaign results.
8. Reports: choose a report, export CSV, or use Print / Save PDF.

The calendar and rules are real: before the paid window, the app will recommend preparation/organic promotion and €0 spend. It does not manufacture an urgent campaign for demonstration. The six screenings are 2, 5, 6, 9, 16 and 23 February 2027, each currently modeled at 109 seats (654 provisional seats total). Times are not yet confirmed.

## Stack and layout

- `apps/web`: Next.js 16, TypeScript, Tailwind CSS, Radix/shadcn-style source-owned UI, Recharts, Leaflet.
- `apps/api`: FastAPI, SQLAlchemy, PostgreSQL, Alembic migrations, session authentication.
- `packages/types`: shared frontend contracts.
- `packages/ui`: accessible reusable UI components.
- `packages/config`: shared navigation/product configuration.
- `data`: 26 archived ESO inventory observations, separated from Resolution sales.
- `tests/e2e`: Playwright workflow tests.
- `.github/workflows/ci.yml`: native PostgreSQL 17, Python tests, frontend checks/build and browser tests.

## Production / standard PostgreSQL

The local launcher is **not** a production deployment. Docker Compose, Dockerfiles, a Render Blueprint and a Vercel configuration are included as preparation, not evidence of a completed deployment.

For Docker Compose, install Docker Desktop and create `.env` with:

```dotenv
POSTGRES_PASSWORD=replace-with-a-long-random-alphanumeric-value
REEF_ADMIN_EMAIL=your-work-email@example.com
REEF_ADMIN_PASSWORD=replace-with-a-unique-password-of-12-or-more-characters
APP_ORIGIN=http://localhost:3000
ENVIRONMENT=development
```

Then run `docker compose up --build`. This path uses native PostgreSQL 17 and sign-in instead of the quick launcher's PGlite database. Its data is kept in a named Docker volume. The two paths have separate databases.

For an Internet deployment set `ENVIRONMENT=production`, disable `DEV_AUTH_BYPASS`, configure an HTTPS `APP_ORIGIN` and matching API `CORS_ORIGINS`, and supply a PostgreSQL connection string as a server secret. Never expose the local test launcher to the Internet. Invite further users with `python -m reef.users email@example.com --role viewer` from the API environment; the password is collected interactively.

## Verification and limits

See `docs/LOCAL_HANDOFF.md` for the latest verification results and remaining work. Baseline forecasts use a transparent small-data ridge model with grouped leave-one-event-out validation and bootstrap planning ranges. Archived unavailable inventory is a demand proxy, not verified final attendance. Price elasticity and advertising response remain explicit planning assumptions unless future evidence supports empirical estimates; attributed tickets are not proven incremental lift.

The original repository was only read for historical data and was not modified. This ZIP is the new application's source, without dependencies, runtime databases, credentials or Git history.

### Evidence-aware sales and geography intelligence

The local decision workspace now includes a sales-intelligence layer and a dynamic marketing ranking. Final demand is forecast for each screening, near-term 7/14-day selling is updated from live pace when observations exist, and the scenario engine ranks which screening and geography should receive a selected test budget. Geography ranking uses imported campaign response when available and otherwise falls back to an explicitly labelled travel-friction planning prior. It never treats attributed tickets as causal lift or invents advertising conversions when CPA evidence is missing.

### Phase 5 decision semantics and evidence ingestion

The workspace now separates **forecast risk** from **action urgency**. A screening can have high pre-sales demand risk while the correct current action remains €0 paid spend because tickets are not yet open. Scenario budget allocations are explicitly what-if plans, not spend instructions. Geography output is a **market-test priority** until campaign or website evidence exists. Location-level traffic (`sessions`, `ticket_clicks`) and batch ticket snapshots can be imported by CSV, and those observations update the ranking/velocity layers. Price decisions now run an elasticity sensitivity check; an apparent revenue-leading price is not called robust unless it survives the tested assumption range and clears the current forecast-uncertainty threshold.
