# Model card

## Purpose

Support marketing decisions for Resolution at ESO Supernova without overstating what sparse observational data can prove.

## Model 1 — ESO baseline demand

**Task:** predict occupancy / construct normal ESO presale trajectory.

**Training data:** validated public ESO booking snapshots.

**Primary operational baseline:** empirical monotonic (PAVA) sales curve.

**Candidate ML:** portable bootstrap ridge ensemble with nonlinear numeric transformations and categorical encoding.

**Validation:** grouped by show, so observations from one performance are not intentionally split across training and validation folds.

**Benchmark:** empirical curve scored on the same held-out booking folds.

**Operational gate:** configured MAE/R² requirements plus requirement that ML is no worse than the empirical benchmark.

If the gate fails, the dashboard uses the empirical curve and labels ML as low confidence.

## Model 2 — engagement response

**Task:** predict engagement response from real campaign variables.

**Possible targets:** landing-page views, CTR, 75% video-view rate.

**Inputs:** spend, lead time, area, age band, creative, and channel when enough channel diversity exists.

**Meaning:** predictive engagement only. It does not prove ticket sales.

## Model 3 — ticket lift

**Task:** predict controlled incremental ticket estimates from marketing cells.

**Training restriction:** only `incremental_tickets_estimate` with `controlled_residual` or `staggered_test` provenance is eligible. Directly attributed purchases are tracked purchases, not proof of lift.

**Activation gate:** minimum verified rows, geography diversity, creative diversity, and validation quality.

**Operational use:** automatic scenario/budget allocation is allowed only when this model is operational. Otherwise the system labels geo/channel/creative outputs as planning priors / experiments.

## Technical constraints

The work PC blocks scikit-learn compiled DLLs through Windows Application Control. The project therefore uses numpy/pandas models serialized to JSON. This avoids requiring admin privileges or weakening system security.

## Known limitations

- Sparse historical booking data can make cross-show generalization weak.
- Comparable ESO programmes are not identical to Resolution.
- Seat inventory shows purchases but may not expose cancellations/refunds/source attribution.
- External ad-platform delivery can change independently of the model.
- Without purchase attribution or a valid experiment, geo/channel causal lift cannot be identified from aggregate seat sales alone.

## Interpretation rule

A prediction is a decision aid, not a guarantee. Always show scenario intervals and model quality beside the point estimate.

## Current status, 24 September 2026

The ESO candidate trained on 26 snapshots from 13 unique bookings, with 13 repeated shows and observed lead times of 17–88 days. Grouped CV MAE is 17.03 occupancy points (18.56 seats at 109 capacity), RMSE 18.36 points, and R² 0.409. The empirical benchmark MAE on the same folds is 19.31 points. The candidate beats that benchmark but fails the configured 12-point absolute MAE gate; **operational model: empirical fit**, with very low confidence for final-day extrapolation. The engagement and lift models have zero real campaign rows and are waiting. Last training UTC is recorded in `data/training_status.json`.

The pre-campaign spend curve uses an explicit **unverified scenario assumption** from `config/project.json`: EUR 0.85 per click and 0.045 incremental tickets per click, with diminishing return after EUR 75 in a cell. These values are not estimated from REEF or ESO marketing outcomes. They are held equal across geography, age, channel and creative until real evidence exists. The conditional EUR 260 reserve is not allocated by the prior-only optimizer.
