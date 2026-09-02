"""
src/evaluation/plots.py

Graficos basicos con matplotlib (equity curve, drawdown, distribucion retornos).
"""
from __future__ import annotations
import matplotlib.pyplot as plt
import polars as pl
import numpy as np

def plot_equity(bt_df: pl.DataFrame, title: str = "Equity Curve", save: str | None = None):
    fig, ax = plt.subplots(figsize=(12,5))
    ax.plot(bt_df["timestamp"].to_list(), bt_df["equity"].to_list(), label="Strategy")
    if "bh_equity" in bt_df.columns:
        ax.plot(bt_df["timestamp"].to_list(), bt_df["bh_equity"].to_list(), label="Buy & Hold", alpha=0.6)
    ax.set_title(title)
    ax.set_ylabel("Equity (USDT)")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    if save:
        plt.savefig(save, dpi=150)
    return fig

def plot_drawdown(bt_df: pl.DataFrame, save: str | None = None):
    eq = bt_df["equity"].to_numpy()
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak)/peak * 100
    fig, ax = plt.subplots(figsize=(12,3))
    ax.fill_between(range(len(dd)), dd, 0, color="red", alpha=0.3)
    ax.set_title("Drawdown %")
    ax.set_ylabel("DD %")
    plt.tight_layout()
    if save:
        plt.savefig(save, dpi=150)
    return fig
