"""Features package."""
from .price import add_price_features
from .volume import add_volume_features
from .cvd import add_cvd_features
from .volatility import add_volatility_features, add_vwap
from .technical import add_technical_features
import polars as pl

def build_features(
    df: pl.DataFrame,
) -> pl.DataFrame:
    """Pipeline completo de features -> dataset para estrategias rule-based."""
    df = add_price_features(df)
    df = add_volume_features(df)
    df = add_cvd_features(df)
    df = add_volatility_features(df)
    df = add_vwap(df)
    df = add_technical_features(df)
    return df
