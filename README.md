# REEF Film Launch Intelligence

**Share with your boss:** follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) to publish a private, view-only Streamlit app and invite them by email. The local `127.0.0.1` link cannot be opened on another computer.

Decision support for four Tuesday screenings of *Resolution* at ESO Supernova on 2, 9, 16 and 23 February 2027. ESO sells the tickets. Each screening has 109 seats, for 436 total. The paid marketing ceiling is EUR 500, aimed at adults 20–60.

## Windows setup

Use Python 3.12 with the Windows `py` launcher. Extract the complete folder to a writable location. No administrator rights or scikit-learn are needed.

1. Double-click `FIRST_SETUP.bat`. It creates `.venv`, installs dependencies, backs up any data changed by migration, trains eligible models, runs the doctor and tests. Internet is needed for the initial package installation.
2. Double-click `START_DASHBOARD.bat`. Open the local URL printed in its window, usually `http://127.0.0.1:8501`; it selects another port if 8501 is occupied.
3. Double-click `DAILY_UPDATE.bat` for collection, migration, training and health checks. One failed ESO page is a warning; valid pages still persist.
4. Double-click `TRAIN_MODELS.bat` to retrain without collection, or `PROJECT_DOCTOR.bat` to diagnose.

Equivalent commands from the project folder:

```bat
.venv\Scripts\python.exe migrate_data.py
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe train_models.py
.venv\Scripts\python.exe project_doctor.py
.venv\Scripts\python.exe run_dashboard_stable.py
```

`FIRST_SETUP.bat` only sets up and checks the project. Start the dashboard separately. To move the project to another Windows machine, zip the project folder, extract it, and run `FIRST_SETUP.bat`; the generated `.venv` can be omitted from the zip.

## Current evidence boundary

The comparable ESO sample contains booking inventory, not final sales. It includes programmes unlike an adult Tuesday film and currently has no observations in the final two weeks. Its fitted day-zero value is therefore a weak extrapolation. The learned demand model is evaluated with booking-grouped folds and is used only if it passes quality gates and beats the empirical fit.

No real campaign rows, controlled incremental ticket labels, or public Resolution booking IDs are configured. Paid lift, spend-response, and occupancy probabilities are **planning scenarios**, not learned marketing effects. Hand-set targeting priorities are test priorities, not conversion probabilities. A tracked purchase is not necessarily an incremental purchase.

## EUR 500 experiment

The precommitted learning plan totals EUR 240: EUR 90 for three geographies × two creatives, EUR 80 for age refinement in the strongest measured geographies, EUR 40 for search, and EUR 30 for retargeting if an audience exists. EUR 260 remains uncommitted for scaling. Run a no-paid Resolution baseline before the first paid wave. The reserve may remain unspent if marginal evidence is weak.

## Required external inputs

- Four public ESO booking URLs, one for each screening, once ESO publishes them. Add each URL to `tracking.resolution_booking_urls` in `config/project.json`.
- Actual Meta/Google daily exports with date, area, age band, creative, spend, impressions, and clicks. The Campaign Training Lab supports explicit column mapping.
- A defensible incremental design or label before ticket-lift ML can run. ESO purchase source reports, source codes, or reliable conversion events support tracked purchases; controlled holdout/staggered tests are needed to establish *incremental* lift. Aggregate seats alone can support only an uncertain overall campaign comparison.

No credentials are stored. The project uses only public ESO pages until campaign data is imported.

## Layout

- `config/project.json`: business facts and gates.
- `data/eso_comparable_snapshots.csv`: canonical daily booking observations. Migration backups go to `data/backups/` when data changes.
- `data/eso_discovered_programmes.csv`: raw discovery diagnostics; historical cookie-page rows are retained for audit and excluded from training.
- `data/campaign_history.csv`: campaign observations with provenance fields.
- `models/*.json`: portable NumPy model artefacts.
- `pages/`: Streamlit drill-down pages.
- `docs/ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/MODEL_CARD.md`, `docs/DATA_DICTIONARY.md`, `docs/EXPERIMENT_PROTOCOL.md`, `docs/PROJECT_PLAN.md`: methods and operations.

The dashboard distinguishes **actual**, **empirical fitted**, **learned ML**, and **scenario** claims. See `CHANGELOG.md` for changes in this revision.

The first page is a decision brief. It shows the current spend decision, no-paid and test scenarios, the main uncertainty, and the next decision trigger. The sidebar leads to Sales Forecast, Ad Targeting Map, Campaign Experiment, Budget Scenarios, Campaign Data, Model Quality, Data Health, and Evidence Methodology. Technical details and raw rows sit in expanders on the relevant pages.
