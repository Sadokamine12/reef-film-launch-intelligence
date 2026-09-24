# Project plan — Resolution @ ESO marketing intelligence

Current checkpoint (24 September 2026): 26 canonical ESO booking/day observations from 13 shows; no Resolution booking IDs or campaign rows. The empirical curve is the operational baseline; the grouped-validated ML candidate fails the MAE gate. The only authorised initial paid action after a no-paid window is the EUR 90 six-cell Meta test. The other EUR 410 remains conditional. Historical `next_training_tests.csv` from an older 24-cell plan is archived under `data/backups/` and is not used.

## 1. Objective

Predict and measure whether EUR 500 of paid marketing materially improves attendance for four Tuesday screenings of Resolution at ESO Supernova in February 2027, and allocate spend to the highest-value test cells without inventing causal certainty.

## 2. Final decision outputs

The finished system provides, in one place:

- expected tickets without paid marketing;
- expected tickets with a selected marketing budget;
- estimated incremental tickets caused by marketing;
- low/base/high attendance scenarios;
- probabilities of reaching 50%, 60%, and 75% occupancy;
- expected tickets by Tuesday;
- budget-response curve from EUR 0 upward;
- recommended experimental ad zones on a map;
- measured geography/channel/creative performance when verified labels exist;
- model confidence, validation error, and benchmark comparison;
- explicit next data requirements if a claim is not yet supported.

## 3. System layers

### Layer A — Comparable ESO demand

Source: public ESO booking pages.

Features include days to show, weekday, time, month, duration/age when available, programme family, and observed seats sold.

Operational output: empirical monotonic presale curve. A lightweight ML model may replace it only after grouped-by-show validation passes the project quality gate and is at least as good as the empirical benchmark.

### Layer B — Resolution live demand

Begins when the four Resolution booking URLs become public.

The system tracks remaining seats daily and compares actual pace with comparable ESO expectations.

Outputs include pace index, projected final occupancy, and changes in sales velocity before/after campaign phases.

### Layer C — Engagement response

Source: real Meta/Google ad-set observations.

Labels: CTR, video completion, landing-page visits, and other non-purchase engagement metrics.

Purpose: learn which geographies, age bands, creatives, and channels generate qualified traffic before purchase attribution is available.

### Layer D — Ticket lift

Source: verified purchase attribution or controlled/staggered incremental-lift labels.

The ticket-lift model is intentionally locked until sufficient labels, geography coverage, and creative coverage exist.

## 4. Locked campaign budget

- Total: EUR 500
- Learning: EUR 240
- Protected scale reserve: EUR 260

The complete testing protocol is defined before launch; the reserve is not assigned until evidence exists.

## 5. Data collection timeline

### Now through booking launch

- Run ESO comparable tracker daily or several times per week.
- Grow the number of unique shows and repeated observations.
- Track model quality using grouped-by-show validation.
- Prepare creative assets, UTM convention, campaign/ad-set IDs, and attribution route.

### When Resolution booking opens

- Add all four public booking URLs to `config/project.json`.
- Establish a short no-paid baseline window.
- Confirm purchase attribution method.
- Start structured learning tests.

### During paid tests

- Keep ad sets isolated by test cell.
- Record spend, delivery, engagement, IDs, UTMs, and verified ticket labels if available.
- Retrain after each meaningful wave, not after every click.

### Scale phase

- Allocate the EUR 260 reserve only when evidence passes the decision gate.
- If no test cell performs acceptably, keep or reduce the reserve rather than forcing spend.

## 6. Model governance

The system uses these rules:

- Grouped validation by performance/campaign group to reduce leakage.
- Empirical benchmark comparison for the ESO model.
- No guessed purchase attribution in ticket-lift training.
- Low-confidence trained models are visible for research but are not operational.
- Scenario priors are labeled as priors until a verified ticket-lift model exists.
- All model artifacts are JSON-based numpy/pandas ensembles for Windows compatibility.

## 7. Completion definition

The architecture is complete now. Remaining future inputs are external evidence, not missing modules:

1. Resolution's four ESO booking URLs when ESO publishes them.
2. Real campaign metrics once paid tests begin.
3. A defensible purchase-attribution or controlled-lift mechanism if exact geo/channel ticket causality is required.

No additional architectural phase is required to handle those inputs; the current modules already include their ingestion, validation, retraining, and reporting paths.
