from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from data_contracts import clean_eso_snapshots, read_csv_safe


def load_validated_snapshots(path: str | Path = "data/eso_comparable_snapshots.csv") -> pd.DataFrame:
    return clean_eso_snapshots(read_csv_safe(path))


def _pava(y: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
    """Pool-adjacent-violators algorithm for non-decreasing isotonic regression."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n == 0:
        return y
    w = np.ones(n, dtype=float) if weights is None else np.asarray(weights, dtype=float)
    levels = y.copy().tolist()
    block_w = w.copy().tolist()
    starts = list(range(n))
    ends = list(range(n))
    i = 0
    while i < len(levels) - 1:
        if levels[i] <= levels[i + 1] + 1e-15:
            i += 1
            continue
        new_w = block_w[i] + block_w[i + 1]
        new_level = (levels[i] * block_w[i] + levels[i + 1] * block_w[i + 1]) / new_w
        levels[i] = new_level
        block_w[i] = new_w
        ends[i] = ends[i + 1]
        del levels[i + 1], block_w[i + 1], starts[i + 1], ends[i + 1]
        if i > 0:
            i -= 1
    fitted = np.empty(n, dtype=float)
    for level, start, end in zip(levels, starts, ends):
        fitted[start:end + 1] = level
    return fitted


def fit_empirical_sales_curve(df: pd.DataFrame, horizon_days: int = 120) -> tuple[pd.DataFrame, dict]:
    """Pure-numpy monotonic ESO presale baseline.

    This is the operational fallback when a learned model does not pass grouped-by-show validation.
    It is descriptive, not a causal estimate of marketing lift.
    """
    if df is None or df.empty:
        return pd.DataFrame(), {}
    work = df.dropna(subset=["days_to_event", "sold_fraction"]).copy()
    if len(work) < 6 or work["days_to_event"].nunique() < 3:
        return pd.DataFrame(), {}

    # Average duplicate lead times, then fit monotonic sold share as showtime approaches.
    grouped = work.groupby("days_to_event", as_index=False).agg(sold_fraction=("sold_fraction", "mean"), n=("sold_fraction", "size"))
    grouped = grouped.sort_values("days_to_event", ascending=False).reset_index(drop=True)  # far -> near
    y = grouped["sold_fraction"].to_numpy(dtype=float)
    weights = grouped["n"].to_numpy(dtype=float)
    fit = _pava(y, weights)

    observed_days = grouped["days_to_event"].to_numpy(dtype=float)
    # np.interp needs ascending x. We want a smooth monotonic visual baseline.
    x_asc = observed_days[::-1]
    y_asc = fit[::-1]
    max_seen = int(max(30, min(horizon_days, np.nanmax(observed_days))))
    grid_days = np.arange(max_seen, -1, -1, dtype=int)
    base = np.interp(grid_days[::-1].astype(float), x_asc, y_asc, left=y_asc[0], right=y_asc[-1])[::-1]

    # Residual band on original observations against interpolated fitted baseline.
    expected_at_obs = np.interp(work["days_to_event"].to_numpy(dtype=float), x_asc, y_asc, left=y_asc[0], right=y_asc[-1])
    residual = work["sold_fraction"].to_numpy(dtype=float) - expected_at_obs
    if len(residual) >= 8:
        qlo, qhi = np.quantile(residual, [0.10, 0.90])
    else:
        qlo, qhi = -0.18, 0.18
    qlo = min(float(qlo), -0.10)
    qhi = max(float(qhi), 0.10)
    low = np.clip(base + qlo, 0, 1)
    high = np.clip(base + qhi, 0, 1)

    curve = pd.DataFrame({
        "days_to_event": grid_days,
        "low_sold_pct": low * 100,
        "base_sold_pct": base * 100,
        "high_sold_pct": high * 100,
    })
    unique_shows = int(work["show_key"].nunique()) if "show_key" in work.columns else int(len(work))
    repeat_counts = work.groupby("show_key")["snapshot_day"].nunique() if {"show_key", "snapshot_day"}.issubset(work.columns) else pd.Series(dtype=float)
    stats = {
        "rows": int(len(work)),
        "unique_shows": unique_shows,
        "repeated_shows": int((repeat_counts >= 2).sum()) if len(repeat_counts) else 0,
        "unique_programmes": int(work["programme_title"].nunique()) if "programme_title" in work.columns else 0,
        "min_days_to_event": int(work["days_to_event"].min()),
        "max_days_to_event": int(work["days_to_event"].max()),
        "day0_fill_base": float(base[-1]),
        "day0_fill_low": float(low[-1]),
        "day0_fill_high": float(high[-1]),
        "baseline_uncertainty": float(max(0.15, min(0.50, (high[-1] - low[-1]) / max(0.20, 2 * base[-1])))),
        "method": "pure-numpy PAVA empirical curve",
    }
    return curve, stats


def empirical_points(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    cols = [c for c in ["programme_title", "show_datetime_local", "days_to_event", "sold_fraction", "tickets_sold_so_far", "available_seats", "source_type", "show_key"] if c in df.columns]
    out = df[cols].copy()
    out["sold_pct"] = out["sold_fraction"] * 100
    return out
