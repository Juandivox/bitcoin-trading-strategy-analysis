"""
src/models/prediction.py

Inference: carga modelo entrenado y genera predicciones + senales.
"""
from __future__ import annotations
import pickle
from pathlib import Path
import polars as pl

def save_model(model, path: str | Path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(model, f)

def load_model(path: str | Path):
    with open(path, "rb") as f:
        return pickle.load(f)

def predict(df: pl.DataFrame, model, feature_cols: list[str]) -> pl.DataFrame:
    X = df.select(feature_cols).to_numpy()
    preds = model.predict(X)
    return df.with_columns(pl.Series("prediction", preds))
