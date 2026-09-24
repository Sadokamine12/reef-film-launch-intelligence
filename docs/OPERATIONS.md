# Operations

Run `FIRST_SETUP.bat` after extraction. It requires a normal user account, Python 3.12 and initial internet access for pip. It installs to `.venv` within the project. `START_DASHBOARD.bat` starts Streamlit locally at `127.0.0.1:8501`. Stop it with Ctrl+C. `DAILY_UPDATE.bat` runs the collector, migration, training and doctor. `TRAIN_MODELS.bat` and `PROJECT_DOCTOR.bat` run those tasks individually.

The collector's ESO page failures are logged to the console and diagnostic CSV. A run with zero valid new pages can still succeed when existing data is intact. Do not treat cookie/privacy detail rows in `eso_discovered_programmes.csv` as sales; they are historical failed discovery attempts.

When ESO publishes Resolution tickets, add four distinct URLs to `tracking.resolution_booking_urls` in `config/project.json`. The collector will store their actual seats separately in `data/eso_sales_snapshots.csv`. Check the Sales Forecast page after at least two collection days for velocity. Add real campaign observations through Campaign Training Lab; review its field mapping before import. Back up `data/` before moving or editing manually. Migration automatically backs up changed CSV files in `data/backups/`.

Daily decision: inspect the executive forecast, check attribution level and data freshness, compare actual Resolution velocity with the same lead-time ESO fit, then consider the next EUR 25 only when measured performance supports it. A low engagement CPA does not prove ticket lift. The EUR 260 reserve is a ceiling, not a required spend.

For automated Windows Task Scheduler use `DAILY_UPDATE.bat` as the action and set the working directory to this folder. No administrator rights are required. Keep the computer awake during collection. No secrets belong in project files.
