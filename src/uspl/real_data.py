from __future__ import annotations

from pathlib import Path
import time

import numpy as np
import pandas as pd
import requests

from simulator import delayed_oracle_path


COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/ethereum/market_chart/range"


def fetch_eth_usd_daily(cache_path: Path, lookback_days: int = 360) -> pd.DataFrame:
    if cache_path.exists():
        return pd.read_csv(cache_path, parse_dates=["date"])

    end = int(time.time())
    start = end - lookback_days * 24 * 3600
    response = requests.get(
        COINGECKO_URL,
        params={
            "vs_currency": "usd",
            "from": start,
            "to": end,
        },
        timeout=30,
    )
    response.raise_for_status()
    prices = response.json()["prices"]
    df = pd.DataFrame(prices, columns=["timestamp_ms", "eth_usd"])
    df["date"] = pd.to_datetime(df["timestamp_ms"], unit="ms").dt.date
    df = (
        df.assign(date=lambda x: pd.to_datetime(x["date"]))
        .groupby("date", as_index=False)["eth_usd"]
        .last()
        .sort_values("date")
        .reset_index(drop=True)
    )
    cache_path.parent.mkdir(exist_ok=True)
    df.to_csv(cache_path, index=False)
    return df


def _rolling_windows(prices: pd.Series, window: int) -> pd.DataFrame:
    rows = []
    for start in range(0, len(prices) - window + 1):
        segment = prices.iloc[start : start + window]
        returns = segment.pct_change().dropna()
        rows.append(
            {
                "start": start,
                "end": start + window,
                "cumulative_return": segment.iloc[-1] / segment.iloc[0] - 1.0,
                "volatility": returns.std(),
                "max_drawdown": (segment / segment.cummax() - 1.0).min(),
            }
        )
    return pd.DataFrame(rows)


def _select_distinct_windows(
    windows: pd.DataFrame,
    sort_cols: list[str],
    n: int,
    min_gap: int,
    ascending: list[bool] | bool = True,
) -> list[pd.Series]:
    selected: list[pd.Series] = []
    for _, row in windows.sort_values(sort_cols, ascending=ascending).iterrows():
        start = int(row["start"])
        if all(abs(start - int(prev["start"])) >= min_gap for prev in selected):
            selected.append(row)
        if len(selected) == n:
            break
    return selected


def select_real_windows(
    df: pd.DataFrame,
    window: int,
    windows_per_type: int = 3,
) -> dict[str, pd.DataFrame]:
    windows = _rolling_windows(df["eth_usd"], window)
    windows = windows.assign(
        normal_score=lambda x: x["cumulative_return"].abs() + x["volatility"]
    )

    min_gap = max(window // 2, 1)
    normal_rows = _select_distinct_windows(
        windows,
        sort_cols=["normal_score", "max_drawdown"],
        n=windows_per_type,
        min_gap=min_gap,
    )
    drawdown_rows = _select_distinct_windows(
        windows,
        sort_cols=["max_drawdown", "cumulative_return"],
        n=windows_per_type,
        min_gap=min_gap,
    )

    selected: dict[str, pd.DataFrame] = {}
    for idx, row in enumerate(normal_rows, start=1):
        selected[f"real_normal_{idx}"] = df.iloc[
            int(row["start"]) : int(row["end"])
        ].copy()
    for idx, row in enumerate(drawdown_rows, start=1):
        selected[f"real_drawdown_{idx}"] = df.iloc[
            int(row["start"]) : int(row["end"])
        ].copy()
    return selected


def build_real_scenarios(
    df: pd.DataFrame,
    window: int,
    oracle_delay: int,
    shock_ratio: float = 0.80,
    shock_length: int = 2,
    windows_per_type: int = 3,
) -> dict[str, dict[str, np.ndarray | pd.DataFrame]]:
    selected = select_real_windows(df, window, windows_per_type=windows_per_type)
    scenarios: dict[str, dict[str, np.ndarray | pd.DataFrame]] = {}

    for name, frame in selected.items():
        market = frame["eth_usd"].to_numpy(dtype=float)
        scenarios[name] = {
            "frame": frame,
            "market": market,
            "raw_oracle": delayed_oracle_path(market, oracle_delay),
        }

    for idx in range(1, windows_per_type + 1):
        normal_name = f"real_normal_{idx}"
        if normal_name not in selected:
            continue
        shock_frame = selected[normal_name].copy()
        shock_market = shock_frame["eth_usd"].to_numpy(dtype=float)
        shock_oracle = delayed_oracle_path(shock_market, oracle_delay)
        shock_start = len(shock_oracle) // 2
        shock_oracle[shock_start : shock_start + shock_length] *= shock_ratio
        scenarios[f"counterfactual_oracle_shock_{idx}"] = {
            "frame": shock_frame,
            "market": shock_market,
            "raw_oracle": shock_oracle,
        }
    return scenarios
