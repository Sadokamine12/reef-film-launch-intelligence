# Architecture

The project has four data layers. `eso_sales_tracker.py` discovers detail pages but accepts only booking pages with a valid seat count as sales observations. `data_contracts.py` canonicalizes booking IDs across German and English URLs and keeps one Berlin-local daily observation per booking. `eso_baseline.py` fits a monotone empirical presales curve. `training_engine.py` trains NumPy ridge ensembles and validates by booking group. `advanced_ml.py` provides explicitly labelled spend scenarios until controlled lift data exists. `campaign_lab.py` validates real imports and their label provenance. Streamlit `Executive_Forecast.py` and `pages/` display the evidence.

Data flows from ESO booking HTML to daily CSV, then validation/migration, empirical fit and eligible training, and finally dashboard views. Campaign exports flow through explicit column mapping, row validation and deduplication into campaign history. Model JSON files are portable across Windows machines with the stated dependencies.

The three prediction targets are deliberately separate: baseline demand, engagement response, and incremental ticket lift. Directly attributed purchases are tracked purchases; they do not establish incremental lift. Only controlled incremental estimates can currently activate the lift trainer.

The doctor reports blocking integrity problems as FAIL and unavailable future evidence as WARNING. Historical raw discovery records are retained even when excluded from training.


## Target-market selection

`market_context.py` defines paid-media market presets and neutral custom-city zones. Streamlit stores the boss's current market choice in session state. The selected market changes experiment geography, map centres, campaign tagging and planning allocation labels. It does **not** change the ESO Supernova venue, capacity, screening dates, or empirical demand baseline. Campaign rows include a `city` field so engagement and later controlled-lift models can learn cross-city effects once enough real observations exist.


## Pre-campaign city prediction

Before controlled campaign evidence exists, city selection affects the paid-media planning prior through a transparent accessibility factor implemented in `market_context.market_prediction_context`. The function first checks `data/market_evidence.csv`. When a sourced public-transport time is present and marked model-eligible, that time drives the bounded scenario-friction prior; otherwise it falls back to straight-line distance/access. Population is context only and is deliberately excluded from lift calculation until real campaign data can calibrate any relationship. It never changes the empirical ESO no-paid baseline and is replaced/anchored by real campaign modelling once controlled evidence becomes operational.


## Screening-level forecast split

The project now separates the **series total forecast** from the **screening allocation**. `advanced_ml.per_show_forecast` preserves the low/base/high four-show totals and allocates them across 2, 9, 16 and 23 February with transparent scenario weights stored in `config/project.json`. Current indices are 96 / 92 / 108 / 104, averaging exactly 100 so the total forecast is not inflated or reduced by the split.

Calendar facts used as context: TUM and LMU Wintersemester 2026/27 lecture periods end on 5 February 2027; Bavaria's spring school holidays run 8–12 February 2027. The code treats campaign maturity, holiday/local-presence risk and final-show urgency as **scenario assumptions**, not measured causal effects. Once Resolution booking URLs produce repeated per-show observations, those priors should be updated or superseded by actual pace.

Sources: https://www.km.bayern.de/termine/ferien-und-feiertage ; https://www.tum.de/studium/bewerbung/infoportal-bewerbung/termine-und-fristen ; https://www.lmu.de/de/workspace-fuer-studierende/1x1-des-studiums/vorlesungszeiten/


## Management Decision Simulator

`pages/5_Decision_Simulator.py` is the management-facing what-if layer. It combines the empirical ESO baseline with the selected market, budget ceiling and campaign start timing, while keeping provenance visible. Baseline outputs are labelled empirical; paid lift and city effects stay scenario/assumption until real evidence exists. The page deliberately shows market accessibility as HIGH / MEDIUM / LOW and keeps the internal numeric factor out of the main management view.

External market-strength inputs belong in `data/market_evidence.csv`. The current public layer contains a working-age 20–64 population context/proxy, public-transport travel time to ESO, source URLs, methods, year, and model-eligibility flags for every preset market. Munich uses an official 20–64 count; several other municipal values are transparently derived from official total population plus the published total quotient, so they are estimates rather than exact target-audience counts. Meta reachable audience, Google search demand and ESO visitor-origin share remain blank until those proprietary/venue inputs are actually obtained.
