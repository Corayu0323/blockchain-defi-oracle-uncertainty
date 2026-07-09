from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams["font.sans-serif"] = ["Songti SC", "Arial Unicode MS", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

from simulator import (
    AccountConfig,
    SimulationConfig,
    Zone,
    adaptive_close_factor_components,
    health_factor,
    twap_path,
    uncertainty_width_path,
)


MECHANISMS = [
    "fixed",
    "twap",
    "buffer",
    "uspl_no_c_user",
    "uspl_static_width",
    "uspl",
]


def account_for_window(initial_price: float, target_hf: float) -> AccountConfig:
    base = AccountConfig(initial_price=float(initial_price))
    debt = base.collateral_eth * initial_price * base.liquidation_threshold / target_hf
    return AccountConfig(initial_price=float(initial_price), debt_usdc=float(debt))


def _bad_debt_es95(path: pd.DataFrame) -> float:
    positive = path.loc[path["bad_debt"] > 0, "bad_debt"].sort_values(ascending=False)
    if positive.empty:
        return 0.0
    es_count = max(1, int(np.ceil(0.05 * len(path))))
    return float(positive.head(es_count).mean())


def simulate_variant(
    scenario: str,
    mechanism: str,
    market_prices: np.ndarray,
    oracle_prices: np.ndarray,
    config: SimulationConfig,
    account: AccountConfig,
) -> tuple[dict[str, float | str], pd.DataFrame]:
    if len(market_prices) != len(oracle_prices):
        raise ValueError("market_prices and oracle_prices must have the same length")

    oracle_input = twap_path(oracle_prices, config.twap_window) if mechanism == "twap" else oracle_prices
    width_config = (
        replace(config, use_dynamic_uncertainty=False)
        if mechanism == "uspl_static_width"
        else config
    )
    uncertainty_widths = uncertainty_width_path(oracle_prices, width_config)

    collateral = account.collateral_eth
    debt = account.debt_usdc
    first_true_unsafe_step: int | None = None
    first_liquidation_step: int | None = None
    rows = []

    for step, (market_price, oracle_price) in enumerate(zip(market_prices, oracle_input)):
        true_hf = health_factor(
            collateral, market_price, account.liquidation_threshold, debt
        )
        oracle_hf = health_factor(
            collateral, oracle_price, account.liquidation_threshold, debt
        )
        if first_true_unsafe_step is None and true_hf < 1:
            first_true_unsafe_step = step

        width = float(uncertainty_widths[step])
        price_low = oracle_price * (1.0 - width)
        price_high = oracle_price * (1.0 + width)
        hf_min = health_factor(
            collateral, price_low, account.liquidation_threshold, debt
        )
        hf_max = health_factor(
            collateral, price_high, account.liquidation_threshold, debt
        )

        zone = Zone.SAFE
        close_cap = 0.0
        adaptive_components = {
            "unsafe_probability": np.nan,
            "solvency_close_cap": np.nan,
            "user_close_cap": np.nan,
            "adaptive_close_cap": np.nan,
        }

        if mechanism in {"fixed", "twap"}:
            should_liquidate = oracle_hf < 1.0
            close_cap = config.cap_max if should_liquidate else 0.0
            zone = Zone.LIQUIDATION if should_liquidate else Zone.SAFE
        elif mechanism == "buffer":
            should_liquidate = oracle_hf < config.buffer_threshold
            close_cap = config.cap_max if should_liquidate else 0.0
            zone = Zone.LIQUIDATION if should_liquidate else Zone.SAFE
        elif mechanism in {"uspl", "uspl_no_c_user", "uspl_static_width"}:
            if hf_min > 1:
                should_liquidate = False
                zone = Zone.SAFE
            elif hf_max < 1:
                should_liquidate = True
                zone = Zone.LIQUIDATION
                close_cap = config.cap_max
            else:
                should_liquidate = True
                zone = Zone.UNCERTAIN
                adaptive_components = adaptive_close_factor_components(
                    collateral,
                    debt,
                    oracle_price,
                    price_low,
                    hf_min,
                    hf_max,
                    config,
                    account,
                )
                if mechanism == "uspl_no_c_user":
                    close_cap = config.cap_max
                else:
                    close_cap = adaptive_components["adaptive_close_cap"]
            should_liquidate = close_cap > 0
        else:
            raise ValueError(f"Unknown mechanism: {mechanism}")

        repaid = 0.0
        seized_eth = 0.0
        user_loss = 0.0
        false_liquidation = False
        false_liquidation_loss = 0.0

        if should_liquidate and debt > 0 and collateral > 0:
            if first_liquidation_step is None:
                first_liquidation_step = step
            repay_target = close_cap * debt
            max_repay_by_collateral = collateral * market_price / (
                1.0 + account.liquidation_bonus
            )
            repaid = min(debt, repay_target, max_repay_by_collateral)
            seized_eth = repaid * (1.0 + account.liquidation_bonus) / max(
                market_price, 1e-9
            )
            seized_eth = min(seized_eth, collateral)
            collateral -= seized_eth
            debt -= repaid
            user_loss = repaid * account.liquidation_bonus
            false_liquidation = true_hf >= 1.0
            false_liquidation_loss = user_loss if false_liquidation else 0.0

        bad_debt = max(0.0, debt - collateral * market_price)
        rows.append(
            {
                "step": step,
                "scenario": scenario,
                "mechanism": mechanism,
                "market_price": market_price,
                "oracle_price": oracle_price,
                "price_low": price_low,
                "price_high": price_high,
                "true_hf": true_hf,
                "oracle_hf": oracle_hf,
                "hf_min": hf_min,
                "hf_max": hf_max,
                "uncertainty_width": width,
                **adaptive_components,
                "zone": zone.value,
                "close_cap": close_cap,
                "collateral_eth": collateral,
                "debt_usdc": debt,
                "liquidated": should_liquidate,
                "repaid_usdc": repaid,
                "seized_eth": seized_eth,
                "user_loss": user_loss,
                "false_liquidation": false_liquidation,
                "false_liquidation_loss": false_liquidation_loss,
                "bad_debt": bad_debt,
            }
        )

    path = pd.DataFrame(rows)
    timing = (
        float(first_liquidation_step - first_true_unsafe_step)
        if first_true_unsafe_step is not None and first_liquidation_step is not None
        else np.nan
    )
    metrics: dict[str, float | str] = {
        "scenario": scenario,
        "mechanism": mechanism,
        "bad_debt_rate": float((path["bad_debt"] > 0).mean()),
        "max_bad_debt": float(path["bad_debt"].max()),
        "bad_debt_es95": _bad_debt_es95(path),
        "false_liquidation_count": int(path["false_liquidation"].sum()),
        "false_liquidation_loss": float(path["false_liquidation_loss"].sum()),
        "total_user_loss": float(path["user_loss"].sum()),
        "liquidation_count": int(path["liquidated"].sum()),
        "liquidation_timing": timing,
        "liquidation_delay": float(max(0.0, timing)) if not np.isnan(timing) else np.nan,
        "early_liquidation_lead": float(max(0.0, -timing)) if not np.isnan(timing) else 0.0,
        "uncertainty_steps": int((path["zone"] == Zone.UNCERTAIN.value).sum()),
        "avg_uncertainty_width": float(path["uncertainty_width"].mean()),
    }
    return metrics, path


def add_simple_scores(metrics_df: pd.DataFrame) -> pd.DataFrame:
    df = metrics_df.copy()
    metrics = [
        "max_bad_debt",
        "bad_debt_es95",
        "false_liquidation_loss",
        "total_user_loss",
        "liquidation_count",
    ]
    rank_cols = []
    for col in metrics:
        rank_col = f"{col}_rank"
        df[rank_col] = df.groupby("scenario")[col].rank(method="min", ascending=True)
        rank_cols.append(rank_col)
    df["mean_rank"] = df[rank_cols].mean(axis=1)
    df["solvency_feasible"] = (df["max_bad_debt"] <= 1e-9) & (df["bad_debt_es95"] <= 1e-9)
    return df


def build_scenarios(
    aligned_df: pd.DataFrame,
    windows_df: pd.DataFrame,
    stress_ratio: float,
) -> dict[str, pd.DataFrame]:
    aligned = aligned_df.copy()
    aligned["updated_at"] = pd.to_datetime(aligned["updated_at"], utc=True)
    scenarios: dict[str, pd.DataFrame] = {}

    for idx, row in windows_df.iterrows():
        start = pd.Timestamp(row["start_time"])
        end = pd.Timestamp(row["end_time"])
        frame = aligned.loc[
            (aligned["updated_at"] >= start) & (aligned["updated_at"] <= end)
        ].copy()
        scenarios[f"chainlink_drawdown_w{idx + 1}"] = frame

    stable_candidates = []
    window_size = 36
    for start in range(0, len(aligned) - window_size + 1):
        frame = aligned.iloc[start : start + window_size]
        market_return = frame["market_price"].iloc[-1] / frame["market_price"].iloc[0] - 1
        max_drawdown = (frame["market_price"] / frame["market_price"].cummax() - 1).min()
        stable_candidates.append(
            {
                "start": start,
                "score": abs(market_return) + abs(max_drawdown),
            }
        )
    stable = min(stable_candidates, key=lambda x: x["score"])
    frame = aligned.iloc[stable["start"] : stable["start"] + window_size].copy()
    shock_frame = frame.copy()
    shock_start = len(shock_frame) // 2
    shock_frame.loc[
        shock_frame.index[shock_start : shock_start + 3],
        "price",
    ] *= stress_ratio
    scenarios["empirically_calibrated_oracle_stress"] = shock_frame
    return scenarios


def plot_main_results(metrics_df: pd.DataFrame, output_dir: Path) -> None:
    mechanisms = MECHANISMS
    aggregate = (
        metrics_df.groupby("mechanism", as_index=False)
        .agg(
            max_bad_debt=("max_bad_debt", "max"),
            bad_debt_es95=("bad_debt_es95", "max"),
            false_liquidation_loss=("false_liquidation_loss", "sum"),
            total_user_loss=("total_user_loss", "sum"),
            liquidation_count=("liquidation_count", "sum"),
            uncertainty_steps=("uncertainty_steps", "sum"),
        )
    )
    aggregate["mechanism"] = pd.Categorical(
        aggregate["mechanism"], categories=mechanisms, ordered=True
    )
    aggregate = aggregate.sort_values("mechanism")

    labels = {
        "fixed": "Fixed",
        "twap": "TWAP",
        "buffer": "Buffer",
        "uspl_no_c_user": "OBCC-no-user",
        "uspl_static_width": "OBCC-static",
        "uspl": "OBCC",
    }
    palette = {
        "blue": "#1f77b4",
        "orange": "#ff7f0e",
        "red": "#d62728",
        "gray": "#7f7f7f",
    }
    point_colors = {
        "fixed": palette["blue"],
        "twap": palette["blue"],
        "buffer": palette["blue"],
        "uspl_no_c_user": palette["orange"],
        "uspl_static_width": palette["orange"],
        "uspl": palette["red"],
    }

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    ax_loss, ax_frontier = axes

    x = np.arange(len(aggregate))
    width = 0.36
    ax_loss.bar(
        x - width / 2,
        aggregate["total_user_loss"],
        width=width,
        color=palette["blue"],
        label="Total user loss",
    )
    ax_loss.bar(
        x + width / 2,
        aggregate["false_liquidation_loss"],
        width=width,
        color=palette["orange"],
        label="False-liquidation loss",
    )
    ax_loss.set_xticks(x)
    ax_loss.set_xticklabels([labels[str(m)] for m in aggregate["mechanism"]], rotation=25, ha="right")
    ax_loss.set_ylabel("Loss")
    ax_loss.set_title("A. User-side loss metrics")
    ax_loss.grid(axis="y", alpha=0.25)
    ax_loss.legend(frameon=False, fontsize=9)

    frontier_df = aggregate.copy()
    frontier_df["plot_liquidation_count"] = frontier_df["liquidation_count"].astype(float)
    frontier_df.loc[frontier_df["mechanism"] == "buffer", "plot_liquidation_count"] -= 0.12
    frontier_df.loc[frontier_df["mechanism"] == "uspl_no_c_user", "plot_liquidation_count"] += 0.12
    ax_frontier.scatter(
        frontier_df["total_user_loss"],
        frontier_df["plot_liquidation_count"],
        color=[point_colors[str(m)] for m in frontier_df["mechanism"]],
        s=70,
        alpha=0.9,
        edgecolor="white",
        linewidth=0.8,
    )
    label_offsets = {
        "fixed": (-40, 10),
        "twap": (8, -18),
        "buffer": (7, -13),
        "uspl_no_c_user": (-42, 10),
        "uspl_static_width": (5, 8),
        "uspl": (-24, -16),
    }
    for _, row in frontier_df.iterrows():
        mechanism = str(row["mechanism"])
        ax_frontier.annotate(
            labels[mechanism],
            (row["total_user_loss"], row["plot_liquidation_count"]),
            textcoords="offset points",
            xytext=label_offsets[mechanism],
            fontsize=8.5,
            fontweight="bold" if mechanism == "uspl" else "normal",
            color="#222222",
            ha="right" if mechanism in {"uspl", "uspl_no_c_user"} else "left",
        )
    frontier_line = frontier_df.set_index("mechanism").loc[["twap", "uspl"]]
    ax_frontier.plot(
        frontier_line["total_user_loss"],
        frontier_line["plot_liquidation_count"],
        color=palette["gray"],
        linestyle="--",
        linewidth=1.2,
        alpha=0.65,
        label="Pareto frontier",
    )
    ax_frontier.set_title("B. Pareto trade-off within the feasible set")
    ax_frontier.set_xlabel("Total user loss")
    ax_frontier.set_ylabel("Liquidation count (execution-cost proxy)")
    ax_frontier.set_xlim(45, 158)
    ax_frontier.set_ylim(0.5, 11.0)
    ax_frontier.grid(alpha=0.25)
    ax_frontier.legend(frameon=False, fontsize=9, loc="upper right")

    fig.tight_layout()
    fig.savefig(output_dir / "chainlink_calibrated_mechanism_results.png", dpi=200)
    plt.close(fig)


def plot_pipeline(output_dir: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 2.8))
    ax.axis("off")
    labels = [
        "Chainlink ETH/USD rounds",
        "Update interval\nprice jumps\ndeviation distribution",
        "Calibrated delay\nwidth bounds\nstress ratio",
        "USPL interval HF\nand close factor",
        "Mechanism metrics\nbad debt / false loss",
    ]
    x_positions = np.linspace(0.08, 0.92, len(labels))
    for idx, (x, label) in enumerate(zip(x_positions, labels)):
        ax.text(
            x,
            0.55,
            label,
            ha="center",
            va="center",
            fontsize=10,
            bbox={"boxstyle": "round,pad=0.35", "fc": "#F7F7F7", "ec": "#4C78A8"},
        )
        if idx < len(labels) - 1:
            ax.annotate(
                "",
                xy=(x_positions[idx + 1] - 0.07, 0.55),
                xytext=(x + 0.07, 0.55),
                arrowprops={"arrowstyle": "->", "lw": 1.5, "color": "#333333"},
            )
    ax.set_title("Chainlink-calibrated stress-test pipeline", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(output_dir / "chainlink_calibrated_pipeline.png", dpi=200)
    plt.close(fig)


def run_budget_sensitivity(
    scenarios: dict[str, pd.DataFrame],
    base_config: SimulationConfig,
) -> pd.DataFrame:
    budget_rates = [0.001, 0.003, 0.005, 0.008, 0.010, 0.015, 0.030, 0.050]
    rows = []
    for budget_rate in budget_rates:
        config = replace(base_config, false_loss_budget_rate=budget_rate)
        for scenario, frame in scenarios.items():
            target_hf = 1.08 if "drawdown" in scenario else 1.01
            account = account_for_window(float(frame["market_price"].iloc[0]), target_hf)
            metrics, _ = simulate_variant(
                scenario=scenario,
                mechanism="uspl",
                market_prices=frame["market_price"].to_numpy(dtype=float),
                oracle_prices=frame["price"].to_numpy(dtype=float),
                config=config,
                account=account,
            )
            rows.append(
                {
                    "false_loss_budget_rate": budget_rate,
                    **metrics,
                }
            )

    detail_df = pd.DataFrame(rows)
    aggregate_df = (
        detail_df.groupby("false_loss_budget_rate", as_index=False)
        .agg(
            bad_debt_scenario_count=("max_bad_debt", lambda x: int((x > 1e-9).sum())),
            max_bad_debt=("max_bad_debt", "max"),
            bad_debt_es95=("bad_debt_es95", "max"),
            false_liquidation_loss=("false_liquidation_loss", "sum"),
            total_user_loss=("total_user_loss", "sum"),
            liquidation_count=("liquidation_count", "sum"),
            uncertainty_steps=("uncertainty_steps", "sum"),
        )
    )
    return aggregate_df


def plot_budget_sensitivity(df: pd.DataFrame, output_dir: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 7))
    specs = [
        ("max_bad_debt", "A. Worst bad debt"),
        ("false_liquidation_loss", "B. False-liquidation loss"),
        ("total_user_loss", "C. Total user loss"),
        ("liquidation_count", "D. Liquidation count"),
    ]
    for ax, (col, title) in zip(axes.ravel(), specs):
        ax.plot(df["false_loss_budget_rate"], df[col], marker="o")
        ax.set_title(title)
        ax.set_xlabel("false loss budget B")
        ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "chainlink_calibrated_budget_sensitivity.png", dpi=200)
    plt.close(fig)


def _stale_path(values: np.ndarray, lag_steps: int) -> np.ndarray:
    if lag_steps <= 0:
        return values.copy()
    return np.concatenate([np.repeat(values[0], lag_steps), values[:-lag_steps]])


def _amplify_drawdown(values: np.ndarray, amplification: float) -> np.ndarray:
    initial = values[0]
    amplified = initial * (1.0 + amplification * (values / initial - 1.0))
    return np.maximum(amplified, initial * 0.15)


def run_boundary_pressure_ladder(
    scenarios: dict[str, pd.DataFrame],
    base_config: SimulationConfig,
) -> pd.DataFrame:
    """Stress diagnostic using real downturn shapes with amplified drawdowns."""
    target_hf = 1.05
    drawdown_amplification = 4.0
    stale_lag_steps = 6
    specs = [
        ("Fixed", "fixed", np.nan),
        ("TWAP", "twap", np.nan),
        ("Buffer", "buffer", np.nan),
        ("OBCC B=0.005", "uspl", 0.005),
        ("OBCC B=0.008", "uspl", 0.008),
        ("OBCC B=0.015", "uspl", 0.015),
        ("OBCC B=0.030", "uspl", 0.030),
    ]
    rows = []
    drawdown_scenarios = {
        name: frame for name, frame in scenarios.items() if "drawdown" in name
    }
    for label, mechanism, budget_rate in specs:
        config = (
            base_config
            if np.isnan(budget_rate)
            else replace(base_config, false_loss_budget_rate=float(budget_rate))
        )
        scenario_metrics = []
        for scenario, frame in drawdown_scenarios.items():
            market = _amplify_drawdown(
                frame["market_price"].to_numpy(dtype=float),
                drawdown_amplification,
            )
            oracle = _stale_path(
                _amplify_drawdown(
                    frame["price"].to_numpy(dtype=float),
                    drawdown_amplification,
                ),
                stale_lag_steps,
            )
            account = account_for_window(float(market[0]), target_hf)
            metrics, _ = simulate_variant(
                scenario=scenario,
                mechanism=mechanism,
                market_prices=market,
                oracle_prices=oracle,
                config=config,
                account=account,
            )
            scenario_metrics.append(metrics)

        df = pd.DataFrame(scenario_metrics)
        rows.append(
            {
                "mechanism": label,
                "base_mechanism": mechanism,
                "false_loss_budget_rate": budget_rate,
                "target_initial_hf": target_hf,
                "drawdown_amplification": drawdown_amplification,
                "stale_lag_steps": stale_lag_steps,
                "scenario_count": len(df),
                "bad_debt_scenario_count": int((df["max_bad_debt"] > 1e-9).sum()),
                "max_bad_debt": float(df["max_bad_debt"].max()),
                "bad_debt_es95": float(df["bad_debt_es95"].max()),
                "false_liquidation_loss": float(df["false_liquidation_loss"].sum()),
                "total_user_loss": float(df["total_user_loss"].sum()),
                "liquidation_count": int(df["liquidation_count"].sum()),
                "uncertainty_steps": int(df["uncertainty_steps"].sum()),
            }
        )
    return pd.DataFrame(rows)


def run_stress_grid(
    scenarios: dict[str, pd.DataFrame],
    base_config: SimulationConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    target_hf = 1.05
    amplifications = [1.0, 2.0, 3.0, 4.0, 5.0]
    lag_steps = [0, 2, 6, 12, 24]
    budget_rates = [0.003, 0.005, 0.008, 0.010, 0.015, 0.030, 0.050]
    baseline_mechanisms = ["fixed", "twap", "buffer"]
    drawdown_scenarios = {
        name: frame for name, frame in scenarios.items() if "drawdown" in name
    }
    rows = []
    for amplification in amplifications:
        for lag in lag_steps:
            for scenario, frame in drawdown_scenarios.items():
                market = _amplify_drawdown(
                    frame["market_price"].to_numpy(dtype=float),
                    amplification,
                )
                oracle = _stale_path(
                    _amplify_drawdown(
                        frame["price"].to_numpy(dtype=float),
                        amplification,
                    ),
                    lag,
                )
                account = account_for_window(float(market[0]), target_hf)
                for mechanism in baseline_mechanisms:
                    metrics, _ = simulate_variant(
                        scenario=scenario,
                        mechanism=mechanism,
                        market_prices=market,
                        oracle_prices=oracle,
                        config=base_config,
                        account=account,
                    )
                    rows.append(
                        {
                            "drawdown_amplification": amplification,
                            "stale_lag_steps": lag,
                            "target_initial_hf": target_hf,
                            "false_loss_budget_rate": np.nan,
                            **metrics,
                        }
                    )
                for budget_rate in budget_rates:
                    config = replace(
                        base_config,
                        false_loss_budget_rate=budget_rate,
                    )
                    metrics, _ = simulate_variant(
                        scenario=scenario,
                        mechanism="uspl",
                        market_prices=market,
                        oracle_prices=oracle,
                        config=config,
                        account=account,
                    )
                    rows.append(
                        {
                            "drawdown_amplification": amplification,
                            "stale_lag_steps": lag,
                            "target_initial_hf": target_hf,
                            "false_loss_budget_rate": budget_rate,
                            **metrics,
                        }
                    )

    detail = pd.DataFrame(rows)
    aggregate = (
        detail.groupby(
            [
                "drawdown_amplification",
                "stale_lag_steps",
                "mechanism",
                "false_loss_budget_rate",
            ],
            dropna=False,
            as_index=False,
        )
        .agg(
            scenario_count=("scenario", "nunique"),
            bad_debt_scenario_count=("max_bad_debt", lambda x: int((x > 1e-9).sum())),
            max_bad_debt=("max_bad_debt", "max"),
            bad_debt_es95=("bad_debt_es95", "max"),
            false_liquidation_loss=("false_liquidation_loss", "sum"),
            total_user_loss=("total_user_loss", "sum"),
            liquidation_count=("liquidation_count", "sum"),
            uncertainty_steps=("uncertainty_steps", "sum"),
        )
    )

    summary_rows = []
    for (amplification, lag), group in aggregate.groupby(
        ["drawdown_amplification", "stale_lag_steps"]
    ):
        obcc = group[group["mechanism"] == "uspl"].sort_values(
            "false_loss_budget_rate"
        )
        feasible = obcc[obcc["max_bad_debt"] <= 1e-9]
        base_obcc = obcc[np.isclose(obcc["false_loss_budget_rate"], 0.005)]
        twap = group[group["mechanism"] == "twap"].iloc[0]
        fixed = group[group["mechanism"] == "fixed"].iloc[0]
        buffer = group[group["mechanism"] == "buffer"].iloc[0]
        best_feasible = (
            feasible.sort_values("total_user_loss").iloc[0]
            if not feasible.empty
            else None
        )
        min_feasible = feasible.iloc[0] if not feasible.empty else None
        summary_rows.append(
            {
                "drawdown_amplification": amplification,
                "stale_lag_steps": lag,
                "fixed_max_bad_debt": fixed["max_bad_debt"],
                "twap_max_bad_debt": twap["max_bad_debt"],
                "buffer_max_bad_debt": buffer["max_bad_debt"],
                "obcc_b0005_max_bad_debt": float(base_obcc["max_bad_debt"].iloc[0]),
                "min_feasible_B": (
                    float(min_feasible["false_loss_budget_rate"])
                    if min_feasible is not None
                    else np.nan
                ),
                "min_feasible_B_user_loss": (
                    float(min_feasible["total_user_loss"])
                    if min_feasible is not None
                    else np.nan
                ),
                "best_feasible_B": (
                    float(best_feasible["false_loss_budget_rate"])
                    if best_feasible is not None
                    else np.nan
                ),
                "best_feasible_user_loss": (
                    float(best_feasible["total_user_loss"])
                    if best_feasible is not None
                    else np.nan
                ),
                "twap_user_loss": float(twap["total_user_loss"]),
                "fixed_user_loss": float(fixed["total_user_loss"]),
                "buffer_user_loss": float(buffer["total_user_loss"]),
            }
        )
    summary = pd.DataFrame(summary_rows)
    return aggregate, summary


def _heatmap(
    ax: plt.Axes,
    df: pd.DataFrame,
    value: str,
    title: str,
    cmap: str = "Blues",
    fmt: str = ".1f",
) -> None:
    pivot = df.pivot(
        index="drawdown_amplification",
        columns="stale_lag_steps",
        values=value,
    ).sort_index(ascending=False)
    image = ax.imshow(pivot.to_numpy(dtype=float), cmap=cmap, aspect="auto")
    ax.set_title(title)
    ax.set_xlabel("oracle lag (rounds)")
    ax.set_ylabel("drawdown amplification")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(x)) for x in pivot.columns])
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels([f"{x:g}" for x in pivot.index])
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.iloc[i, j]
            text = "NA" if pd.isna(val) else format(val, fmt)
            ax.text(j, i, text, ha="center", va="center", fontsize=8, color="#222222")
    plt.colorbar(image, ax=ax, fraction=0.046, pad=0.04)


def plot_stress_grid(summary: pd.DataFrame, output_dir: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 8.5))
    _heatmap(
        axes[0, 0],
        summary,
        "fixed_max_bad_debt",
        "A. Fixed: worst bad debt",
        cmap="Blues",
    )
    _heatmap(
        axes[0, 1],
        summary,
        "twap_max_bad_debt",
        "B. TWAP: worst bad debt",
        cmap="Greens",
    )
    _heatmap(
        axes[1, 0],
        summary,
        "buffer_max_bad_debt",
        "C. Buffer: worst bad debt",
        cmap="Purples",
    )
    _heatmap(
        axes[1, 1],
        summary,
        "obcc_b0005_max_bad_debt",
        "D. OBCC B=0.005: worst bad debt",
        cmap="Oranges",
    )
    fig.tight_layout()
    fig.savefig(output_dir / "chainlink_stress_grid_bad_debt_heatmaps.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(1, 1, figsize=(5.8, 4.5))
    _heatmap(
        ax,
        summary,
        "min_feasible_B",
        "Minimum feasible B for OBCC",
        cmap="Reds",
        fmt=".3f",
    )
    fig.tight_layout()
    fig.savefig(output_dir / "chainlink_stress_grid_min_feasible_b.png", dpi=200)
    plt.close(fig)


def plot_boundary_pressure_ladder(df: pd.DataFrame, output_dir: Path) -> None:
    palette = {
        "blue": "#1f77b4",
        "orange": "#ff7f0e",
        "red": "#d62728",
        "gray": "#7f7f7f",
    }
    colors = [
        palette["blue"] if not str(m).startswith("OBCC") else palette["orange"]
        for m in df["mechanism"]
    ]
    colors = [palette["red"] if m == "OBCC B=0.030" else c for m, c in zip(df["mechanism"], colors)]

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    ax_safety, ax_cost = axes
    ax_safety.scatter(
        df["total_user_loss"],
        df["max_bad_debt"],
        color=colors,
        s=75,
        edgecolor="white",
        linewidth=0.8,
        zorder=3,
    )
    ax_safety.axhline(0, color=palette["gray"], linestyle="--", linewidth=1.1)
    for _, row in df.iterrows():
        ax_safety.annotate(
            row["mechanism"],
            (row["total_user_loss"], row["max_bad_debt"]),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=8,
        )
    ax_safety.set_title("A. Bad-debt boundary under amplified downturn")
    ax_safety.set_xlabel("Total user loss")
    ax_safety.set_ylabel("Worst bad debt")
    ax_safety.grid(alpha=0.25)

    ax_cost.scatter(
        df["total_user_loss"],
        df["liquidation_count"],
        color=colors,
        s=75,
        edgecolor="white",
        linewidth=0.8,
        zorder=3,
    )
    for _, row in df.iterrows():
        ax_cost.annotate(
            row["mechanism"],
            (row["total_user_loss"], row["liquidation_count"]),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=8,
        )
    ax_cost.set_title("B. User-loss / liquidation-count trade-off")
    ax_cost.set_xlabel("Total user loss")
    ax_cost.set_ylabel("Liquidation count")
    ax_cost.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "chainlink_pressure_ladder_frontier.png", dpi=200)
    plt.close(fig)


def main() -> None:
    data_dir = Path("data")
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    aligned = pd.read_csv(data_dir / "chainlink_coinbase_aligned.csv")
    windows = pd.read_csv(output_dir / "oracle_downturn_windows.csv")
    params = pd.read_csv(output_dir / "oracle_calibrated_stress_params.csv").iloc[0]

    config = SimulationConfig(
        n_steps=1,
        oracle_delay=1,
        base_uncertainty_width=float(params["base_uncertainty_width_empirical"]),
        uncertainty_width=float(params["max_uncertainty_width_empirical"]),
        twap_window=6,
        buffer_threshold=1.01,
        cap_min=0.05,
        cap_max=0.50,
        use_dynamic_uncertainty=True,
        deviation_sensitivity=0.45,
        volatility_sensitivity=2.0,
        false_loss_budget_rate=0.005,
    )
    scenarios = build_scenarios(
        aligned,
        windows,
        stress_ratio=float(params["stress_shock_ratio_from_q01"]),
    )

    metrics_rows = []
    path_frames = []
    scenario_rows = []
    for scenario, frame in scenarios.items():
        target_hf = 1.08 if "drawdown" in scenario else 1.01
        account = account_for_window(float(frame["market_price"].iloc[0]), target_hf)
        scenario_rows.append(
            {
                "scenario": scenario,
                "start_time": frame["updated_at"].iloc[0],
                "end_time": frame["updated_at"].iloc[-1],
                "steps": len(frame),
                "target_initial_hf": target_hf,
                "initial_price": float(frame["market_price"].iloc[0]),
                "ending_price": float(frame["market_price"].iloc[-1]),
                "market_return": float(frame["market_price"].iloc[-1] / frame["market_price"].iloc[0] - 1),
                "oracle_return": float(frame["price"].iloc[-1] / frame["price"].iloc[0] - 1),
                "max_abs_oracle_market_deviation": float(frame["abs_oracle_market_deviation"].max()),
            }
        )
        market = frame["market_price"].to_numpy(dtype=float)
        oracle = frame["price"].to_numpy(dtype=float)
        for mechanism in MECHANISMS:
            metrics, path = simulate_variant(
                scenario=scenario,
                mechanism=mechanism,
                market_prices=market,
                oracle_prices=oracle,
                config=config,
                account=account,
            )
            metrics_rows.append(metrics)
            path_frames.append(path.assign(timestamp=list(frame["updated_at"])))

    metrics_df = add_simple_scores(pd.DataFrame(metrics_rows))
    paths_df = pd.concat(path_frames, ignore_index=True)
    scenarios_df = pd.DataFrame(scenario_rows)
    aggregate_df = (
        metrics_df.groupby("mechanism", as_index=False)
        .agg(
            scenario_count=("scenario", "nunique"),
            bad_debt_scenario_count=("max_bad_debt", lambda x: int((x > 1e-9).sum())),
            max_bad_debt=("max_bad_debt", "max"),
            bad_debt_es95=("bad_debt_es95", "max"),
            false_liquidation_loss=("false_liquidation_loss", "sum"),
            total_user_loss=("total_user_loss", "sum"),
            liquidation_count=("liquidation_count", "sum"),
            avg_mean_rank=("mean_rank", "mean"),
            uncertainty_steps=("uncertainty_steps", "sum"),
        )
        .sort_values(["bad_debt_scenario_count", "avg_mean_rank", "false_liquidation_loss"])
    )

    metrics_df.to_csv(output_dir / "chainlink_calibrated_mechanism_metrics.csv", index=False)
    aggregate_df.to_csv(output_dir / "chainlink_calibrated_mechanism_aggregate.csv", index=False)
    scenarios_df.to_csv(output_dir / "chainlink_calibrated_scenarios.csv", index=False)
    paths_df.to_csv(output_dir / "chainlink_calibrated_paths.csv", index=False)
    plot_main_results(metrics_df, output_dir)
    plot_pipeline(output_dir)
    budget_sensitivity_df = run_budget_sensitivity(scenarios, config)
    budget_sensitivity_df.to_csv(
        output_dir / "chainlink_calibrated_budget_sensitivity.csv",
        index=False,
    )
    plot_budget_sensitivity(budget_sensitivity_df, output_dir)
    pressure_ladder_df = run_boundary_pressure_ladder(scenarios, config)
    pressure_ladder_df.to_csv(
        output_dir / "chainlink_pressure_ladder_metrics.csv",
        index=False,
    )
    plot_boundary_pressure_ladder(pressure_ladder_df, output_dir)
    stress_grid_df, stress_grid_summary = run_stress_grid(scenarios, config)
    stress_grid_df.to_csv(
        output_dir / "chainlink_stress_grid_metrics.csv",
        index=False,
    )
    stress_grid_summary.to_csv(
        output_dir / "chainlink_stress_grid_summary.csv",
        index=False,
    )
    plot_stress_grid(stress_grid_summary, output_dir)

    print("Scenarios")
    print(scenarios_df.round(6).to_string(index=False))
    print("\nMetrics")
    print(metrics_df.round(6).to_string(index=False))
    print("\nAggregate")
    print(aggregate_df.round(6).to_string(index=False))
    print("\nBudget sensitivity")
    print(budget_sensitivity_df.round(6).to_string(index=False))
    print("\nBoundary pressure ladder")
    print(pressure_ladder_df.round(6).to_string(index=False))
    print("\nStress grid summary")
    print(stress_grid_summary.round(6).to_string(index=False))


if __name__ == "__main__":
    main()
