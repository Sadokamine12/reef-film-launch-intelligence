# Data dictionary

## `data/eso_comparable_snapshots.csv`

Validated public booking inventory from comparable ESO shows.

Important fields:

- `collected_at_utc` — observation timestamp
- `programme_title` — public show title
- `show_datetime_local` — local scheduled performance datetime
- `days_to_event` — lead time at observation
- `available_seats` — seats remaining
- `capacity` — venue capacity
- `tickets_sold_so_far` — capacity minus available seats
- `programme_url` — exact public booking URL
- `source_type` — must be booking-page evidence for training
- `retrieval_mode` — requests / selenium / browser fallback
- `status` — validated status
- derived canonical fields added during migration: booking ID, show key, snapshot day, sold fraction

The migration step collapses English/German URLs that refer to the same ESO booking ID on the same observation day.

## `data/eso_sales_snapshots.csv`

Same concept, but for the four Resolution performances once their public booking pages exist.

## `data/campaign_history.csv`

One row per useful campaign/ad-set/test observation.

Core fields:

- `observation_id`
- `date`
- `show_date`
- `days_to_event`
- `experiment_wave`
- `control_group`
- `channel`
- `area`
- `age_band`
- `creative`
- `spend_eur`
- `impressions`
- `video_views_75`
- `clicks`
- `landing_page_views`
- `tickets_attributed`
- `incremental_tickets_estimate`
- `label_source`
- `attribution_level`
- `campaign_id`
- `adset_id`
- `test_id`
- `utm_campaign`
- `utm_content`
- `notes`

## Ticket label sources accepted by the model

For the incremental ticket-lift model, `incremental_tickets_estimate` requires:

- `controlled_residual`
- `staggered_test`

`tickets_attributed` may record directly tracked purchases from:

- `platform_conversion`
- `promo_code`
- `eso_source_report`
- `manual_verified`

Tracked purchases do not train the causal ticket-lift model without a controlled incremental estimate. Unlabeled or guessed rows never train that model.

`booking_id`, `show_key`, `snapshot_day`, and `sold_fraction` are derived in memory by `data_contracts.py`. `snapshot_day` uses Europe/Berlin local time. The source CSV retains the original collected UTC timestamp and URL. Migration creates a timestamped backup before changing historical CSV rows.

## `data/training_status.json`

Current state of each model, including:

- training rows
- target
- features
- validation MAE/R²
- empirical benchmark MAE/R² when applicable
- validation mode
- operational flag
- model artifact path

## `data/training_history.csv`

Appended on every training run so the dashboard can show whether model quality improves as evidence grows.
