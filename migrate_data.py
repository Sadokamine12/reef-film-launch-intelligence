from __future__ import annotations

from pathlib import Path
import shutil
from datetime import datetime, timezone
import pandas as pd

from data_contracts import clean_eso_snapshots, ensure_campaign_frame, read_csv_safe, ESO_SNAPSHOT_COLUMNS
from campaign_lab import CAMPAIGN_PATH
from training_engine import generate_active_learning_plan
from experiment_protocol import write_protocol_files


def main():
    Path("data").mkdir(exist_ok=True)
    eso_path = Path("data/eso_comparable_snapshots.csv")
    raw = read_csv_safe(eso_path)
    if not raw.empty:
        clean = clean_eso_snapshots(raw)
        keep = [c for c in ESO_SNAPSHOT_COLUMNS if c in clean.columns]
        before = len(raw)
        candidate = clean[keep].reset_index(drop=True)
        current = raw.reindex(columns=keep).reset_index(drop=True)
        if not candidate.equals(current):
            backup_dir = Path("data/backups")
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / f"eso_comparable_snapshots_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.csv"
            shutil.copy2(eso_path, backup)
            candidate.to_csv(eso_path, index=False)
            print(f"Preserved raw snapshot backup: {backup}")
        print(f"ESO snapshots: {before} -> {len(clean)} canonical rows")
    campaign = ensure_campaign_frame(read_csv_safe(CAMPAIGN_PATH))
    existing = read_csv_safe(CAMPAIGN_PATH)
    if not CAMPAIGN_PATH.exists() or list(existing.columns) != list(campaign.columns):
        if CAMPAIGN_PATH.exists():
            backup_dir = Path("data/backups")
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(CAMPAIGN_PATH, backup_dir / f"campaign_history_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.csv")
        campaign.to_csv(CAMPAIGN_PATH, index=False)
    print(f"Campaign schema ready: {len(campaign)} row(s)")
    plan = generate_active_learning_plan()
    write_protocol_files()
    print(f"Experiment protocol ready: EUR {plan['planned_spend_eur'].sum():.0f} learning spend + protected scale reserve from config")


if __name__ == "__main__":
    main()
