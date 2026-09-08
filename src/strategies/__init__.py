"""Strategies package — fiel a notebooks/05 (etapa 1) y 06 (etapa 2). Todo long-only (0/1)."""
from .individuals import signal_rsi_long, signal_macd_long, signal_ma_long, signal_cci_long
from .e2a_composite import signal_e2a_long, E2A_A1, E2A_A2_BEST
from .e2c_winners import signal_e2c_long
from .buy_and_hold import signal_buy_and_hold

__all__ = [
    "signal_rsi_long",
    "signal_macd_long",
    "signal_ma_long",
    "signal_cci_long",
    "signal_e2a_long",
    "E2A_A1",
    "E2A_A2_BEST",
    "signal_e2c_long",
    "signal_buy_and_hold",
]
