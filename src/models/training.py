"""
src/models/training.py

Entrenamiento con validacion temporal (walk-forward / expanding).
Separa FEATURES -> TARGET -> TRAINING -> PREDICTION -> TRADING RULE

Uso:
  - Define target: y_t = P_{t+60}/P_t -1 (return 60m futuro)
  - Features: return_*, volume_zscore, cvd, imbalance, volatility, RSI, MACD...
  - Nunca usar random split.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
import polars as pl
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error
from sklearn.ensemble import RandomForestRegressor

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

@dataclass
class SplitConfig:
    train_start: str
    train_end: str
    test_start: str
    test_end: str | None = None

def walk_forward_splits(folds: list[dict]) -> list[SplitConfig]:
    return [
        SplitConfig(
            train_start=f["train"][0], train_end=f["train"][1],
            test_start=f["test"][0], test_end=f["test"][1] if len(f["test"])>1 else None
        ) for f in folds
    ]

def prepare_xy(df: pl.DataFrame, feature_cols: list[str], target_col: str = "target_return_60m"):
    """Filtra nans y retorna X,y como numpy."""
    sub = df.select(feature_cols + [target_col, "timestamp"]).drop_nulls()
    X = sub.select(feature_cols).to_numpy()
    y = sub[target_col].to_numpy()
    ts = sub["timestamp"].to_numpy()
    return X, y, ts, sub

def train_predict(
    df: pl.DataFrame,
    feature_cols: list[str],
    target_col: str = "target_return_60m",
    model_type: Literal["xgboost","lightgbm","rf"] = "xgboost",
    folds: list[dict] | None = None,
):
    """
    Entrena en cada fold walk-forward y retorna predicciones out-of-sample concatenadas.
    """
    if folds is None:
        raise ValueError("Debes proveer folds walk-forward (ver configs/data.yaml)")

    oos_frames = []
    for fold in folds:
        train_mask = (pl.col("timestamp") >= pl.lit(fold["train"][0]).str.to_datetime()) & (pl.col("timestamp") <= pl.lit(fold["train"][1]).str.to_datetime())
        test_mask  = (pl.col("timestamp") >= pl.lit(fold["test"][0]).str.to_datetime())
        if len(fold["test"]) > 1 and fold["test"][1] is not None:
            test_mask = test_mask & (pl.col("timestamp") <= pl.lit(fold["test"][1]).str.to_datetime())

        train = df.filter(train_mask).drop_nulls(subset=feature_cols + [target_col])
        test  = df.filter(test_mask).drop_nulls(subset=feature_cols)

        if len(train) == 0 or len(test) == 0:
            print(f"[train] skip fold {fold} (train={len(train)}, test={len(test)})")
            continue

        X_train = train.select(feature_cols).to_numpy()
        y_train = train[target_col].to_numpy()
        X_test  = test.select(feature_cols).to_numpy()

        if model_type == "xgboost" and HAS_XGB:
            model = xgb.XGBRegressor(n_estimators=500, max_depth=6, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, n_jobs=-1)
        elif model_type == "lightgbm" and HAS_LGB:
            model = lgb.LGBMRegressor(n_estimators=500, max_depth=-1, learning_rate=0.05, n_jobs=-1, verbose=-1)
        else:
            model = RandomForestRegressor(n_estimators=200, n_jobs=-1)

        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        test = test.with_columns(pl.Series("prediction", preds))
        oos_frames.append(test.select(["timestamp","close", target_col, "prediction"]))

    if not oos_frames:
        raise RuntimeError("No se generaron predicciones OOS")
    return pl.concat(oos_frames).sort("timestamp"), model

def to_trading_signal(pred_df: pl.DataFrame, long_th: float = 0.001, short_th: float = -0.001) -> pl.DataFrame:
    """Convierte expected_return -> senal {-1,0,1}."""
    return pred_df.with_columns(
        pl.when(pl.col("prediction") > long_th).then(1)
        .when(pl.col("prediction") < short_th).then(-1)
        .otherwise(0)
        .alias("signal_ml")
    )
