# Changelog

## Private sharing preparation

- Added a view-only default for hosted Streamlit sessions. Campaign import and retraining are enabled only by the trusted local dashboard launcher.
- Added private Streamlit Community Cloud deployment and data-refresh instructions, and excluded local secrets and key files from Git.

## Executive dashboard redesign

- Rebuilt the launch page as a decision brief with a clear current spend decision, forecast provenance, confidence, and next decision trigger.
- Introduced one light visual system across every Streamlit page; fixed low-contrast cards and truncated metric layouts.
- Simplified navigation to Executive Forecast, Sales Forecast, Ad Targeting Map, Campaign Experiment, Budget Scenarios, Campaign Data, Model Quality, Data Health, and Evidence Methodology.
- Reworked the map to show the three actual EUR 30 geography allocations and moved display controls out of the sidebar. Fixed an encoding mismatch that had incorrectly put all EUR 90 in one area.
- Replaced the dense prediction and campaign import screens with focused tabs and progressive detail.
- Archived an obsolete, unmeasured zone-prediction cache that was no longer used by the redesigned pages.

## 2026-09-24

- Audited all existing source, configuration, datasets, model artefacts, Streamlit pages and documentation.
- Restricted ticket-lift training to controlled incremental estimates. Tracked purchases no longer masquerade as causal lift labels.
- Removed unmeasured geography, age, creative, channel and Tuesday performance multipliers from the planning prior.
- Strengthened booking snapshot validation, Berlin-local daily deduplication, campaign import validation, and mapped CSV import.
- Added grouped model RMSE and seat MAE, expanded project doctor checks, a Sales Forecast page, an Evidence page, and automated tests.
- Added migration backups and portable Windows setup, dashboard, daily update, model training and doctor workflows.
- Preserved historical discovery diagnostics, including excluded privacy-page failures, for audit.
- Archived the obsolete 24-cell training-test CSV while retaining its history; the live experiment plan is the 6-cell broad-age first wave.
