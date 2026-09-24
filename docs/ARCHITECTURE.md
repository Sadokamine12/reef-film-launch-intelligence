# Architecture

The project has four data layers. `eso_sales_tracker.py` discovers detail pages but accepts only booking pages with a valid seat count as sales observations. `data_contracts.py` canonicalizes booking IDs across German and English URLs and keeps one Berlin-local daily observation per booking. `eso_baseline.py` fits a monotone empirical presales curve. `training_engine.py` trains NumPy ridge ensembles and validates by booking group. `advanced_ml.py` provides explicitly labelled spend scenarios until controlled lift data exists. `campaign_lab.py` validates real imports and their label provenance. Streamlit `Executive_Forecast.py` and `pages/` display the evidence.

Data flows from ESO booking HTML to daily CSV, then validation/migration, empirical fit and eligible training, and finally dashboard views. Campaign exports flow through explicit column mapping, row validation and deduplication into campaign history. Model JSON files are portable across Windows machines with the stated dependencies.

The three prediction targets are deliberately separate: baseline demand, engagement response, and incremental ticket lift. Directly attributed purchases are tracked purchases; they do not establish incremental lift. Only controlled incremental estimates can currently activate the lift trainer.

The doctor reports blocking integrity problems as FAIL and unavailable future evidence as WARNING. Historical raw discovery records are retained even when excluded from training.


## Target-market selection

`market_context.py` defines paid-media market presets and neutral custom-city zones. Streamlit stores the boss's current market choice in session state. The selected market changes experiment geography, map centres, campaign tagging and planning allocation labels. It does **not** change the ESO Supernova venue, capacity, screening dates, or empirical demand baseline. Campaign rows include a `city` field so engagement and later controlled-lift models can learn cross-city effects once enough real observations exist.
