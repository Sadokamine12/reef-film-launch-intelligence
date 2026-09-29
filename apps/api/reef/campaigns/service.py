from reef.models import Campaign, CampaignMetric
from reef.schemas import Rules
from sqlalchemy import select
from sqlalchemy.orm import Session


def metrics_for(db: Session, campaign_id: str) -> dict:
    rows = list(db.scalars(select(CampaignMetric).where(CampaignMetric.campaign_id == campaign_id)))
    spend = sum(x.spend_cents for x in rows)
    impressions, clicks = sum(x.impressions for x in rows), sum(x.clicks for x in rows)
    tickets = (
        sum(x.attributed_tickets for x in rows if x.attributed_tickets is not None)
        if any(x.attributed_tickets is not None for x in rows)
        else None
    )
    lpv = (
        sum(x.landing_page_views for x in rows if x.landing_page_views is not None)
        if any(x.landing_page_views is not None for x in rows)
        else None
    )
    return {
        "spend_cents": spend,
        "impressions": impressions,
        "clicks": clicks,
        "landing_page_views": lpv,
        "attributed_tickets": tickets,
        "ctr": round(clicks / impressions * 100, 2) if impressions else None,
        "landing_page_response": round(lpv / clicks * 100, 2) if lpv is not None and clicks else None,
        "cost_per_ticket_cents": round(spend / tickets) if tickets else None,
        "source_label": "OBSERVED" if rows else "PLANNING ASSUMPTION",
        "observations": len(rows),
        "last_imported_at": max((x.imported_at.isoformat() for x in rows), default=None),
    }


def budget(db: Session, project_id: str, rules: Rules) -> dict:
    campaigns = list(db.scalars(select(Campaign).where(Campaign.project_id == project_id)))
    channels = {}
    for platform, ceiling in [("META", rules.meta_ceiling_cents), ("GOOGLE", rules.google_ceiling_cents)]:
        spend = committed = 0
        for campaign in campaigns:
            if campaign.platform != platform:
                continue
            actual = metrics_for(db, campaign.id)["spend_cents"]
            spend += actual
            committed += (
                max(0, campaign.budget_cents - actual)
                if campaign.status in {"PLANNED", "ACTIVE", "PAUSED"}
                else 0
            )
        channels[platform] = {
            "ceiling_cents": ceiling,
            "spent_cents": spend,
            "committed_cents": committed,
            "available_cents": max(0, ceiling - spend - committed),
            "over_ceiling": spend + committed > ceiling,
        }
    spend = sum(c["spent_cents"] for c in channels.values())
    committed = sum(c["committed_cents"] for c in channels.values())
    return {
        "ceiling_cents": rules.total_ceiling_cents,
        "spent_cents": spend,
        "committed_cents": committed,
        "available_cents": max(0, rules.total_ceiling_cents - rules.reserve_cents - spend - committed),
        "reserve_cents": rules.reserve_cents,
        "remaining_cents": max(0, rules.total_ceiling_cents - spend),
        "over_ceiling": spend + committed > rules.total_ceiling_cents
        or any(x["over_ceiling"] for x in channels.values()),
        "channels": channels,
    }
