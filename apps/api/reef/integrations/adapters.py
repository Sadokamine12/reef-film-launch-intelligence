"""Provider boundary: no provider claims LIVE until a successful authenticated retrieval.

CSV rows represent one campaign/ad-set/creative/zone daily aggregate, not arbitrary segments.
"""

import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Protocol

from reef.schemas import MetricInput


class SourceAdapter(Protocol):
    provider: str

    def fetch(self, **kwargs) -> list[dict]: ...


class UnconfiguredProvider:
    def __init__(self, provider: str):
        self.provider = provider

    def fetch(self, **kwargs):
        raise RuntimeError(
            f"{self.provider} is not connected; configure credentials and a provider adapter first"
        )


PROVIDERS = {name: UnconfiguredProvider(name) for name in ["ESO", "META", "GOOGLE", "ANALYTICS"]}

ALIASES = {
    "date": ["date", "Day", "Reporting starts"],
    "spend": ["spend_eur", "Amount spent (EUR)", "Cost"],
    "impressions": ["impressions", "Impressions", "Impr."],
    "clicks": ["clicks", "Link clicks", "Clicks"],
    "landing_page_views": ["landing_page_views", "Landing page views"],
    # Generic platform 'Conversions' and 'Purchases' are deliberately not assumed to mean tickets.
    "attributed_tickets": ["attributed_tickets", "Attributed tickets"],
}


def parse_campaign_csv(content: bytes, platform: str) -> list[MetricInput]:
    if platform not in {"META", "GOOGLE", "MANUAL"}:
        raise ValueError("Unsupported CSV provider")
    if len(content) > 2_000_000:
        raise ValueError("CSV exceeds 2 MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("Save the export as UTF-8 CSV") from None
    reader = csv.DictReader(io.StringIO(text))
    fields = reader.fieldnames or []
    mapping = {key: next((a for a in aliases if a in fields), None) for key, aliases in ALIASES.items()}
    if any(mapping[x] is None for x in ["date", "spend", "impressions", "clicks"]):
        raise ValueError(
            "Missing columns: use date, spend_eur, impressions, clicks or the supported Meta/Google headers"
        )
    rows, dates, identities = [], set(), set()
    for index, raw in enumerate(reader, 2):
        if len(rows) >= 5000:
            raise ValueError("Maximum 5,000 rows per import")
        if not any(raw.values()):
            continue
        try:
            currency = raw.get("Currency", raw.get("currency", "EUR")).strip()
            if currency != "EUR":
                raise ValueError("Only EUR exports are supported")
            for name in ["Campaign ID", "Campaign name", "Ad set ID", "Ad ID"]:
                if raw.get(name):
                    identities.add((name, raw[name]))
            if any(
                sum(1 for k, v in identities if k == name) > 1
                for name in ["Campaign ID", "Campaign name", "Ad set ID", "Ad ID"]
            ):
                raise ValueError("Filter the export to one campaign/ad set/creative before importing")
            values = {k: raw.get(col, "").strip() if col else "" for k, col in mapping.items()}
            spend = Decimal(values.pop("spend"))
            if not spend.is_finite() or spend.as_tuple().exponent < -2:
                raise ValueError("Spend must be a finite EUR amount with at most two decimal places")
            row = MetricInput(
                date=values["date"],
                spend_cents=int(spend * 100),
                impressions=int(values["impressions"]),
                clicks=int(values["clicks"]),
                landing_page_views=int(values["landing_page_views"])
                if values["landing_page_views"]
                else None,
                attributed_tickets=int(values["attributed_tickets"])
                if values["attributed_tickets"]
                else None,
            )
            if row.date in dates:
                raise ValueError("Duplicate date: import daily totals for one ad set/creative/zone only")
            if raw.get("Reporting ends") and raw["Reporting ends"] != str(row.date):
                raise ValueError("Use a daily breakdown, not a multi-day reporting total")
            dates.add(row.date)
            rows.append(row)
        except (ValueError, InvalidOperation) as exc:
            raise ValueError(f"Row {index}: {exc}") from None
    if not rows:
        raise ValueError("CSV contains no data rows")
    return rows
