import csv
from datetime import date, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from reef.db import engine
from reef.models import Creative, Geography, HistoricalSnapshot, Project, Screening
from reef.schemas import Rules

PROJECT_ID = "resolution-eso-2027"


def seed(db: Session):
    if not db.get(Project, PROJECT_ID):
        db.add(
            Project(
                id=PROJECT_ID,
                name="Resolution at ESO Supernova",
                film="Resolution",
                venue="ESO Supernova, Garching",
                latitude=48.259828,
                longitude=11.670136,
                timezone="Europe/Berlin",
                rules=Rules().model_dump(mode="json"),
                revision=1,
            )
        )
        db.flush()
    for day in [2, 9, 16, 23]:
        sid = f"resolution-2027-02-{day:02}"
        if not db.get(Screening, sid):
            db.add(
                Screening(
                    id=sid,
                    project_id=PROJECT_ID,
                    date=date(2027, 2, day),
                    time=None,
                    capacity=109,
                    sales_open_date=date(2026, 11, 16),
                    sales_open_confirmed=False,
                )
            )
    for key, name, lo, hi, priority, note in [
        ("zone-a", "Zone A · Core", 0, 15, "Highest priority", "Garching and the immediate ESO catchment."),
        (
            "zone-b",
            "Zone B · Munich North",
            15,
            30,
            "High priority",
            "North Munich and neighbouring towns; evaluate local travel access.",
        ),
        (
            "zone-c",
            "Zone C · Expansion",
            30,
            50,
            "Experimental",
            "Test only after the inner zones demonstrate ticket response.",
        ),
    ]:
        if not db.get(Geography, key):
            db.add(
                Geography(
                    id=key,
                    project_id=PROJECT_ID,
                    name=name,
                    min_km=lo,
                    max_km=hi,
                    priority=priority,
                    notes=note,
                )
            )
    for key, name, concept, headline, body in [
        (
            "creative-a",
            "Creative A — Experience",
            "Experience",
            "Music. Light. A world beyond the screen.",
            "An immersive music and fulldome experience. Discover Resolution at ESO Supernova.",
        ),
        (
            "creative-b",
            "Creative B — Event",
            "Event",
            "Your Tuesday, in another dimension.",
            "Resolution at ESO Supernova · [exact Tuesday] · Garching / U6. Book your ticket via ESO.",
        ),
    ]:
        if not db.get(Creative, key):
            db.add(
                Creative(
                    id=key,
                    project_id=PROJECT_ID,
                    name=name,
                    concept=concept,
                    headline=headline,
                    body=body,
                    status="DRAFT",
                )
            )
    source = Path(__file__).resolve().parents[3] / "data" / "eso_historical_inventory.csv"
    if not source.exists():
        source = Path("/app/data/eso_historical_inventory.csv")
    if source.exists():
        for row in csv.DictReader(source.open()):
            key = str(uuid5(NAMESPACE_URL, row["programme_url"] + row["collected_at_utc"]))
            if not db.get(HistoricalSnapshot, key):
                db.add(
                    HistoricalSnapshot(
                        id=key,
                        programme=row["programme_title"],
                        show_date=date.fromisoformat(row["show_datetime_local"][:10]),
                        observed_at=datetime.fromisoformat(row["collected_at_utc"]),
                        days_before=int(row["days_to_event"]),
                        unavailable_seats=int(row["capacity"]) - int(row["available_seats"]),
                        capacity=int(row["capacity"]),
                        source_url=row["programme_url"],
                    )
                )
    db.commit()


if __name__ == "__main__":
    with Session(engine()) as db:
        seed(db)
    print("Resolution project seeded. No sales or campaign metrics were fabricated.")
