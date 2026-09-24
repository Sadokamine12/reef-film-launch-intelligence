from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
import json
import math

import numpy as np
import pandas as pd


PERCENT_TARGETS = {"sold_pct", "ctr_pct", "vtr75_pct", "lpv_per_click_pct", "conversion_pct"}


def _sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, -35, 35)
    return 1.0 / (1.0 + np.exp(-x))


def _transform_y(y: np.ndarray, target: str) -> tuple[np.ndarray, str]:
    y = np.asarray(y, dtype=float)
    if target in PERCENT_TARGETS:
        p = np.clip(y / 100.0, 0.005, 0.995)
        return np.log(p / (1.0 - p)), "logit_percent"
    if np.nanmin(y) >= 0:
        return np.log1p(np.maximum(0.0, y)), "log1p"
    return y, "identity"


def _inverse_y(z: np.ndarray, transform: str) -> np.ndarray:
    z = np.asarray(z, dtype=float)
    if transform == "logit_percent":
        return 100.0 * _sigmoid(z)
    if transform == "log1p":
        return np.maximum(0.0, np.expm1(np.clip(z, -20, 20)))
    return z


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        if math.isfinite(x):
            return x
    except Exception:
        pass
    return default


@dataclass
class EncoderState:
    numeric: list[str]
    categorical: list[str]
    medians: dict[str, float]
    means: dict[str, float]
    scales: dict[str, float]
    categories: dict[str, list[str]]
    feature_names: list[str]

    def to_dict(self) -> dict:
        return {
            "numeric": self.numeric,
            "categorical": self.categorical,
            "medians": self.medians,
            "means": self.means,
            "scales": self.scales,
            "categories": self.categories,
            "feature_names": self.feature_names,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EncoderState":
        return cls(
            numeric=list(d.get("numeric", [])),
            categorical=list(d.get("categorical", [])),
            medians={k: float(v) for k, v in d.get("medians", {}).items()},
            means={k: float(v) for k, v in d.get("means", {}).items()},
            scales={k: float(v) for k, v in d.get("scales", {}).items()},
            categories={k: list(v) for k, v in d.get("categories", {}).items()},
            feature_names=list(d.get("feature_names", [])),
        )


class LightweightEnsemble:
    """Windows-policy-friendly regression ensemble.

    Uses pandas/numpy only: manual one-hot encoding, nonlinear basis features,
    ridge regression and bootstrap ensembling. No sklearn / compiled sklearn DLLs.
    """

    def __init__(
        self,
        state: EncoderState,
        weights: list[list[float]],
        target: str,
        target_transform: str,
        clip_low: Optional[float] = None,
        clip_high: Optional[float] = None,
        meta: Optional[dict] = None,
    ):
        self.state = state
        self.weights = [np.asarray(w, dtype=float) for w in weights]
        self.target = target
        self.target_transform = target_transform
        self.clip_low = clip_low
        self.clip_high = clip_high
        self.meta = meta or {}

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        mat = encode_frame(X, self.state)
        preds = []
        for w in self.weights:
            z = mat @ w
            preds.append(_inverse_y(z, self.target_transform))
        if not preds:
            out = np.zeros(len(X), dtype=float)
        else:
            out = np.mean(np.vstack(preds), axis=0)
        if self.clip_low is not None:
            out = np.maximum(float(self.clip_low), out)
        if self.clip_high is not None:
            out = np.minimum(float(self.clip_high), out)
        return out

    def prediction_spread(self, X: pd.DataFrame) -> np.ndarray:
        mat = encode_frame(X, self.state)
        preds = [_inverse_y(mat @ w, self.target_transform) for w in self.weights]
        if len(preds) <= 1:
            return np.zeros(len(X), dtype=float)
        return np.std(np.vstack(preds), axis=0, ddof=1)

    def to_dict(self) -> dict:
        return {
            "format": "reef-lightweight-ml-v1",
            "target": self.target,
            "target_transform": self.target_transform,
            "clip_low": self.clip_low,
            "clip_high": self.clip_high,
            "state": self.state.to_dict(),
            "weights": [w.tolist() for w in self.weights],
            "meta": self.meta,
        }

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "LightweightEnsemble":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            state=EncoderState.from_dict(payload["state"]),
            weights=payload["weights"],
            target=payload["target"],
            target_transform=payload.get("target_transform", "identity"),
            clip_low=payload.get("clip_low"),
            clip_high=payload.get("clip_high"),
            meta=payload.get("meta", {}),
        )


def fit_encoder(df: pd.DataFrame, numeric: list[str], categorical: list[str]) -> EncoderState:
    medians: dict[str, float] = {}
    means: dict[str, float] = {}
    scales: dict[str, float] = {}
    categories: dict[str, list[str]] = {}
    feature_names = ["intercept"]

    for c in numeric:
        s = pd.to_numeric(df.get(c, pd.Series(index=df.index, dtype=float)), errors="coerce")
        med = float(s.median()) if s.notna().any() else 0.0
        filled = s.fillna(med).astype(float)
        mean = float(filled.mean()) if len(filled) else 0.0
        scale = float(filled.std(ddof=0)) if len(filled) else 1.0
        if not math.isfinite(scale) or scale < 1e-8:
            scale = 1.0
        medians[c] = med
        means[c] = mean
        scales[c] = scale
        feature_names += [f"{c}:z", f"{c}:z2", f"{c}:signed_sqrt"]
        if c in {"spend_eur", "days_to_event"}:
            feature_names.append(f"{c}:log1p_abs")

    for c in categorical:
        s = df.get(c, pd.Series(index=df.index, dtype=str)).fillna("Unknown").astype(str)
        vals = sorted(v for v in s.unique().tolist() if v and v.lower() != "nan")
        if "Unknown" not in vals:
            vals.append("Unknown")
        categories[c] = vals
        feature_names += [f"{c}={v}" for v in vals]

    # Spend-by-category interaction terms help marketing response differ by geo/channel/creative.
    if "spend_eur" in numeric:
        for c in categorical:
            for v in categories[c]:
                feature_names.append(f"spend_x_{c}={v}")

    return EncoderState(numeric, categorical, medians, means, scales, categories, feature_names)


def encode_frame(df: pd.DataFrame, state: EncoderState) -> np.ndarray:
    n = len(df)
    cols: list[np.ndarray] = [np.ones(n, dtype=float)]
    numeric_z: dict[str, np.ndarray] = {}

    for c in state.numeric:
        s = pd.to_numeric(df.get(c, pd.Series(index=df.index, dtype=float)), errors="coerce")
        arr = s.fillna(state.medians.get(c, 0.0)).to_numpy(dtype=float)
        z = (arr - state.means.get(c, 0.0)) / max(1e-8, state.scales.get(c, 1.0))
        numeric_z[c] = z
        cols.append(z)
        cols.append(z * z)
        cols.append(np.sign(z) * np.sqrt(np.abs(z)))
        if c in {"spend_eur", "days_to_event"}:
            cols.append(np.log1p(np.abs(arr)) * np.sign(arr))

    cat_masks: dict[tuple[str, str], np.ndarray] = {}
    for c in state.categorical:
        s = df.get(c, pd.Series(index=df.index, dtype=str)).fillna("Unknown").astype(str).to_numpy()
        allowed = set(state.categories.get(c, []))
        s = np.asarray([v if v in allowed else "Unknown" for v in s], dtype=object)
        for v in state.categories.get(c, []):
            mask = (s == v).astype(float)
            cat_masks[(c, v)] = mask
            cols.append(mask)

    if "spend_eur" in numeric_z:
        spend_z = numeric_z["spend_eur"]
        for c in state.categorical:
            for v in state.categories.get(c, []):
                cols.append(spend_z * cat_masks[(c, v)])

    mat = np.column_stack(cols) if cols else np.empty((n, 0), dtype=float)
    return np.nan_to_num(mat, nan=0.0, posinf=0.0, neginf=0.0)


def _ridge_fit(mat: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    p = mat.shape[1]
    reg = np.eye(p, dtype=float) * float(alpha)
    if p:
        reg[0, 0] = 0.0  # do not regularize intercept
    a = mat.T @ mat + reg
    b = mat.T @ y
    try:
        return np.linalg.solve(a, b)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(a) @ b


def _clip_for_target(target: str) -> tuple[Optional[float], Optional[float]]:
    if target in PERCENT_TARGETS:
        return 0.0, 100.0
    if target in {"landing_page_views", "tickets_attributed", "incremental_tickets_estimate", "ticket_lift", "clicks", "video_views_75"}:
        return 0.0, None
    return None, None


def fit_bootstrap_ridge_ensemble(
    X: pd.DataFrame,
    y: pd.Series,
    numeric: list[str],
    categorical: list[str],
    target: str,
    seed: int = 42,
    n_models: int = 31,
) -> LightweightEnsemble:
    state = fit_encoder(X, numeric, categorical)
    mat = encode_frame(X, state)
    y_raw = pd.to_numeric(y, errors="coerce").to_numpy(dtype=float)
    y_t, transform = _transform_y(y_raw, target)
    rng = np.random.default_rng(seed)
    alphas = np.array([0.05, 0.1, 0.3, 0.7, 1.5, 3.0, 7.0, 15.0], dtype=float)
    weights: list[list[float]] = []
    n = len(y_t)
    for i in range(max(7, int(n_models))):
        if i == 0:
            idx = np.arange(n)
        else:
            idx = rng.integers(0, n, size=n)
        alpha = float(alphas[i % len(alphas)])
        w = _ridge_fit(mat[idx], y_t[idx], alpha)
        weights.append(w.tolist())
    low, high = _clip_for_target(target)
    return LightweightEnsemble(
        state=state,
        weights=weights,
        target=target,
        target_transform=transform,
        clip_low=low,
        clip_high=high,
        meta={"algorithm": "bootstrap ridge ensemble", "n_models": len(weights), "seed": seed},
    )


def cv_predict(
    X: pd.DataFrame,
    y: pd.Series,
    numeric: list[str],
    categorical: list[str],
    target: str,
    folds: int,
    seed: int = 42,
) -> np.ndarray:
    n = len(y)
    folds = int(max(2, min(folds, n)))
    rng = np.random.default_rng(seed)
    order = np.arange(n)
    rng.shuffle(order)
    split_indices = np.array_split(order, folds)
    pred = np.full(n, np.nan, dtype=float)
    for fold_i, test_idx in enumerate(split_indices):
        train_idx = np.setdiff1d(order, test_idx, assume_unique=False)
        if len(train_idx) < 3 or len(test_idx) == 0:
            continue
        model = fit_bootstrap_ridge_ensemble(
            X.iloc[train_idx].reset_index(drop=True),
            y.iloc[train_idx].reset_index(drop=True),
            numeric,
            categorical,
            target,
            seed=seed + 101 * fold_i,
            n_models=13,
        )
        pred[test_idx] = model.predict(X.iloc[test_idx].reset_index(drop=True))
    return pred


def regression_metrics(y_true: pd.Series | np.ndarray, y_pred: np.ndarray) -> tuple[Optional[float], Optional[float]]:
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    mask = np.isfinite(yt) & np.isfinite(yp)
    if mask.sum() < 2:
        return None, None
    yt = yt[mask]
    yp = yp[mask]
    mae = float(np.mean(np.abs(yt - yp)))
    denom = float(np.sum((yt - yt.mean()) ** 2))
    r2 = None if denom <= 1e-12 else float(1.0 - np.sum((yt - yp) ** 2) / denom)
    return mae, r2


def feature_importance_from_weights(model: LightweightEnsemble) -> pd.DataFrame:
    if not model.weights:
        return pd.DataFrame(columns=["feature", "importance"])
    arr = np.vstack(model.weights)
    imp = np.mean(np.abs(arr), axis=0)
    names = model.state.feature_names
    if len(names) != len(imp):
        names = [f"feature_{i}" for i in range(len(imp))]
    out = pd.DataFrame({"feature": names, "importance": imp})
    out = out[out["feature"] != "intercept"].sort_values("importance", ascending=False).reset_index(drop=True)
    total = float(out["importance"].sum())
    if total > 0:
        out["importance_share"] = out["importance"] / total
    else:
        out["importance_share"] = 0.0
    return out
