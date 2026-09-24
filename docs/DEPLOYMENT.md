# Share the dashboard with REEF management

## Recommended: private Streamlit Community Cloud app

The local address (`http://127.0.0.1:8501` or `:8502`) works only on the computer running Streamlit. For a stable link accessible from another computer, deploy this repository to Streamlit Community Cloud.

1. Create a **private GitHub repository** for this project. Upload the project files, including `Executive_Forecast.py`, `pages/`, `data/`, `models/`, `config/`, `requirements.txt`, and `.streamlit/config.toml`. Leave out `.venv/`, local logs, credentials, and `.streamlit/secrets.toml`. Keep the repository private because future campaign exports may be commercially sensitive.
2. Sign in at [Streamlit Community Cloud](https://share.streamlit.io/) and connect the GitHub account with access to that repository.
3. Select **Create app**, choose the repository and branch, and set the main file path to **`Executive_Forecast.py`**. In Advanced settings, select **Python 3.12**. Give the app a memorable subdomain, such as `reef-resolution-forecast` if available. No secrets are needed for the current public ESO data.
4. Deploy. Open the generated `https://<your-subdomain>.streamlit.app/` link and check the Executive Forecast, Ad Targeting Map, and Model Quality pages.
5. Keep the app **private** in its Sharing settings. Use **Share → Invite** with the boss's email address. They can open the emailed link after signing in. Streamlit currently allows one private Community Cloud app per account; check the current platform policy before using it for more projects.

Do not send the local `127.0.0.1` address. The URL is created by Streamlit after deployment; this repository cannot know it in advance.

If Git is available, run these commands from the project folder after creating the empty private repository (replace the example URL with yours):

```powershell
git init
git branch -M main
git add .
git commit -m "Initial REEF dashboard"
git remote add origin https://github.com/YOUR_ACCOUNT/reef-film-launch-intelligence.git
git push -u origin main
```

This workstation currently has no Git repository or configured GitHub remote for the project. Publishing therefore needs your GitHub account and repository. GitHub Desktop can perform the same publish step if you prefer a graphical interface.

## What the hosted app can do

The hosted app is intentionally **view-only**. The local Windows launcher sets `REEF_ENABLE_EDITING=1`, which enables campaign import and in-app retraining on your own machine. Cloud deployment runs `Executive_Forecast.py` directly, so those controls are hidden. This prevents a viewer from changing shared campaign data and avoids implying that a cloud CSV write is durable. Do not set `REEF_ENABLE_EDITING=1` in Community Cloud secrets or environment settings.

To refresh the boss's dashboard:

1. Run `DAILY_UPDATE.bat` locally, and import any real campaign exports locally using `START_DASHBOARD.bat`.
2. Run `PROJECT_DOCTOR.bat` and `TRAIN_MODELS.bat` when appropriate.
3. Commit and push the changed `data/`, `models/`, and source files to the private GitHub repository. Community Cloud redeploys from the updated repository. Inspect exports before committing them: a private repository still contains the files for everyone with repository access.

The hosted copy does **not** run the Windows daily collector on a schedule. It displays the last published data and model artifacts. For automatic live updates, add an external scheduled collector and durable storage later; the current CSV files on Community Cloud are not guaranteed to persist after server restart. This is a hosting constraint, not evidence of live Resolution ticket sales.

## Before sharing

- Verify all four screens still show the published data and the paid-lift scenario warning.
- Check that `data/campaign_history.csv` contains only data approved for management viewing.
- Confirm the link is private by opening it in a browser where you are signed out.
- If deployment fails, open **Manage app → Logs** in Community Cloud. The entrypoint must be `Executive_Forecast.py`, not `run_dashboard_stable.py` or a `.bat` file.

Official instructions: [deploy an app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [share a private app](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app), and [Cloud file persistence](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data).
