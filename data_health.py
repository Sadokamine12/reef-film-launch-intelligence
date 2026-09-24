from __future__ import annotations

import pandas as pd
from project_doctor import run_checks
from campaign_lab import attribution_readiness
from model_quality import eso_coverage, load_status


def health_frame() -> pd.DataFrame:
    return pd.DataFrame(run_checks())


def health_summary() -> dict:
    frame = health_frame()
    blocking = int(((~frame["ok"]) & frame["level"].eq("error")).sum()) if not frame.empty else 0
    warnings = int(((~frame["ok"]) & frame["level"].eq("warning")).sum()) if not frame.empty else 0
    coverage = eso_coverage()
    attribution = attribution_readiness()
    status = load_status()
    return {"blocking":blocking, "warnings":warnings, "coverage":coverage, "attribution":attribution, "training":status}
