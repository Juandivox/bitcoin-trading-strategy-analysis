"""
scripts/audit_and_run_atr.py

Ejecuta la estrategia E2-A (A1, A2, PSO) comparando:
1. Version actual (SIN ATR, como estaba corriendo).
2. Version con STOP LOSS ATR FIJO (stop = entry - k*ATR).
3. Version con TRAILING STOP ATR (stop = max(stop, close - k*ATR)).
4. Evaluacion tanto en cierre de vela (close < stop) como intra-vela (low < stop).

Muestra metricas en IS70 (2017-2023), OOS30 (2023-2026) y FULL (2017-2026).
"""
import numpy as np
import polars as pl
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features.technical import cci, sma
from src.backtesting.metrics import summarize
from src.strategies.e2a_composite import E2A_A1, E2A_A2_BEST
E2A_PSO = {
    "cci_period": 10, "cci_entry": 50.0, "cci_exit": 250.0,
    "sma_fast": 27, "sma_slow": 227,
    "vol_window": 60, "vol_z_thr": 0.1431,
    "atr_period": 14, "atr_k": 2.0
}

def volume_zscore(vol: pl.Expr, window: int) -> pl.Expr:
    mu = vol.rolling_mean(window_size=window, min_samples=window)
    sigma = vol.rolling_std(window_size=window, min_samples=window)
    return ((vol - mu) / sigma).alias(f"vol_z_{window}")

def atr(high: pl.Expr, low: pl.Expr, close: pl.Expr, period: int) -> pl.Expr:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pl.max_horizontal(tr1, tr2, tr3)
    return tr.rolling_mean(window_size=period, min_samples=period).alias(f"atr_{period}")

def run_simulation(df: pl.DataFrame, params: dict, stop_mode: str = "none", intra_bar: bool = False):
    """
    stop_mode: 'none', 'fixed_atr', 'trailing_atr'
    intra_bar: False (evalua con close), True (evalua con low)
    """
    cp = params["cci_period"]
    ce = params["cci_entry"]
    cx = params["cci_exit"]
    sf = params["sma_fast"]
    ss = params["sma_slow"]
    vw = params["vol_window"]
    vz = params["vol_z_thr"]
    ap = params.get("atr_period", 14)
    ak = params.get("atr_k", 2.0)

    # 1. Indicadores
    d = df.sort("timestamp").with_columns([
        cci(pl.col("high"), pl.col("low"), pl.col("close"), cp).alias("_cci"),
        sma(pl.col("close"), sf).alias("_sma_f"),
        sma(pl.col("close"), ss).alias("_sma_s"),
        volume_zscore(pl.col("volume"), vw).alias("_vz"),
        atr(pl.col("high"), pl.col("low"), pl.col("close"), ap).alias("_atr"),
    ])

    close = d["close"].to_numpy()
    low = d["low"].to_numpy()
    high = d["high"].to_numpy()
    _cci = d["_cci"].to_numpy()
    _sma_f = d["_sma_f"].to_numpy()
    _sma_s = d["_sma_s"].to_numpy()
    _vz = d["_vz"].to_numpy()
    _atr = d["_atr"].to_numpy()

    n = len(close)
    sig = np.zeros(n, dtype=np.int8)
    stop_price_series = np.full(n, np.nan, dtype=np.float64)

    # Precalcular cruces y condiciones tecnicas
    trend_vol = (_sma_f > _sma_s) & (_vz > vz)
    cci_prev = np.full(n, np.nan)
    cci_prev[1:] = _cci[:-1]
    raw_entry = (cci_prev < ce) & (_cci > ce) & trend_vol
    raw_exit = (_cci > cx) | (_sma_f < _sma_s)

    state = 0
    curr_entry_price = 0.0
    curr_stop = 0.0

    for t in range(n):
        if state == 0:
            if raw_entry[t]:
                state = 1
                curr_entry_price = close[t]
                curr_stop = curr_entry_price - ak * _atr[t]
            sig[t] = state
        else: # state == 1 (LONG)
            # Actualizar trailing si aplica
            if stop_mode == "trailing_atr":
                curr_stop = max(curr_stop, close[t] - ak * _atr[t])

            # Chequear stop loss
            stopped = False
            if stop_mode in ("fixed_atr", "trailing_atr"):
                test_price = low[t] if intra_bar else close[t]
                if test_price < curr_stop:
                    stopped = True

            # Chequear salida tecnica
            tech_exit = raw_exit[t]

            if stopped or tech_exit:
                state = 0
                sig[t] = 0
            else:
                sig[t] = 1
                stop_price_series[t] = curr_stop

    # Backtest con lag=1 y costos Binance (10 bps fee + 5 bps slippage)
    pos = np.zeros(n, dtype=np.float64)
    pos[1:] = sig[:-1] # lag=1

    price_ret = np.zeros(n, dtype=np.float64)
    price_ret[1:] = close[1:] / close[:-1] - 1.0

    gross_ret = pos * price_ret
    turnover = np.abs(np.diff(pos, prepend=0))
    cost_rate = (10.0 + 5.0) / 10_000.0 # 15 bps
    cost = turnover * cost_rate
    strat_ret = gross_ret - cost

    equity = 10_000.0 * np.cumprod(1.0 + strat_ret)

    # Metricas: fuente unica (src/backtesting/metrics.py).
    metrics_df = pl.DataFrame({
        "timestamp": df["timestamp"],
        "position": pos,
        "strategy_ret": strat_ret,
        "equity": equity,
        "_turnover": turnover,
    })
    m = summarize(metrics_df, rf_annual=0.0)

    return {
        "final_equity": m["final_equity"],
        "total_ret_%": m["total_return_%"],
        "CAGR_%": m["CAGR_%"],
        "sharpe": m["sharpe"],
        "maxDD_%": m["maxDD_%"],
        "trades": m["trades"],
        "win_rate_%": m["win_rate_%"],
        # inf conserva el formato de la tabla de este script auxiliar
        "profit_factor": m["profit_factor"] if m["profit_factor"] is not None else float("inf"),
        "exposure": m["exposure"],
    }

def main():
    df4h = pl.read_parquet(ROOT / "data" / "processed" / "btcusdt_4h.parquet").sort("timestamp")
    n_total = len(df4h)
    n_is = int(n_total * 0.70)
    df_is = df4h[:n_is]
    df_oos = df4h[n_is:]

    variants = [
        ("E2-A A1 (Paper)", E2A_A1),
        ("E2-A A2 (Optuna)", E2A_A2_BEST),
        ("E2-A PSO (Optimizado)", E2A_PSO),
    ]

    modes = [
        ("1. SIN ATR (Actual)", "none", False),
        ("2. STOP ATR FIJO (a cierre)", "fixed_atr", False),
        ("3. STOP ATR FIJO (intra-vela)", "fixed_atr", True),
        ("4. TRAILING STOP ATR (a cierre)", "trailing_atr", False),
    ]

    print("=" * 85)
    print("AUDITORIA EMPIRICA: IMPACTO DE INTEGRAR EL STOP LOSS POR ATR")
    print(f"Dataset 4H: {n_total:,} velas (IS70: {len(df_is):,}, OOS30: {len(df_oos):,})")
    print("Costos: 10 bps fee + 5 bps slippage | Lag: 1")
    print("=" * 85)

    for vname, params in variants:
        print(f"\n>>> ESTRATEGIA: {vname}")
        print(f"    Params: CCI {params['cci_period']}/{params['cci_entry']}/{params['cci_exit']} | SMA {params['sma_fast']}/{params['sma_slow']} | Vol {params['vol_window']}/{params['vol_z_thr']:.2f} | ATR {params.get('atr_period',14)}/k={params.get('atr_k',2.0):.2f}")
        print("-" * 85)
        print(f"{'Configuracion ATR':<30} | {'Periodo':<7} | {'Retorno':<9} | {'Sharpe':<7} | {'MaxDD':<8} | {'Trades':<6} | {'WinRate':<7} | {'ProfFact':<8}")
        print("-" * 85)

        for mlabel, smode, intra in modes:
            # IS70
            m_is = run_simulation(df_is, params, stop_mode=smode, intra_bar=intra)
            print(f"{mlabel:<30} | {'IS70':<7} | {m_is['total_ret_%']:>8.1f}% | {m_is['sharpe']:>7.3f} | {m_is['maxDD_%']:>7.1f}% | {m_is['trades']:>6} | {m_is['win_rate_%']:>6.1f}% | {m_is['profit_factor']:>8.2f}")

            # OOS30
            m_oos = run_simulation(df_oos, params, stop_mode=smode, intra_bar=intra)
            print(f"{'':<30} | {'OOS30':<7} | {m_oos['total_ret_%']:>8.1f}% | {m_oos['sharpe']:>7.3f} | {m_oos['maxDD_%']:>7.1f}% | {m_oos['trades']:>6} | {m_oos['win_rate_%']:>6.1f}% | {m_oos['profit_factor']:>8.2f}")

            # FULL
            m_full = run_simulation(df4h, params, stop_mode=smode, intra_bar=intra)
            print(f"{'':<30} | {'FULL':<7} | {m_full['total_ret_%']:>8.1f}% | {m_full['sharpe']:>7.3f} | {m_full['maxDD_%']:>7.1f}% | {m_full['trades']:>6} | {m_full['win_rate_%']:>6.1f}% | {m_full['profit_factor']:>8.2f}")
            print("." * 85)

if __name__ == "__main__":
    main()
