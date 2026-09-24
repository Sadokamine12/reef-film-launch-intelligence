# Live data connections

The dashboard is ready to ingest live advertising and Resolution booking evidence, but credentials are never committed to GitHub.

## Current connection state — 24 September 2026

### Meta Ads

A Meta Ads connector exists in Windsor.ai, but the currently connected account is **not confirmed as the REEF advertising account** and returned **0 reporting rows over the last two years** in the connector check. The project therefore does not import or label that account as REEF data.

Authorize the actual REEF Meta Ads account here:

https://onboard.windsor.ai/connect?connector=facebook&client=CHATGPT&next=/facebook/authorize

After authorization, verify the account name and campaign rows before importing anything into `data/campaign_history.csv`.

Expected fields for campaign learning include date, campaign, ad set, ad, spend, impressions, clicks, reach, landing-page views and verified purchase/conversion fields when available.

### Google Ads

No Google Ads account is currently connected through Windsor.ai.

Authorize the REEF Google Ads account here:

https://onboard.windsor.ai/connect?connector=google_ads&client=CHATGPT&next=/google_ads/authorize

After authorization, confirm the account and pull search/campaign metrics before marking Google data as connected.

### ESO Resolution bookings

No public booking pages were found for *Resolution* on 2, 9, 16 or 23 February 2027 in the latest check. ESO's current public release says planetarium shows are bookable through the end of 2026.

The four URLs belong in `tracking.resolution_booking_urls` in `config/project.json` only after the public booking pages exist and have been verified.

## Safety rule

Do not commit OAuth tokens, cookies, API keys or ad-platform credentials. The repository stores only non-secret readiness metadata and imported campaign observations that are intentionally approved for the project.

Do not treat an account as REEF data simply because it is connected. Confirm the account identity and that real REEF campaign rows exist first.
