from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from real_data import build_real_scenarios, fetch_eth_usd_daily
from run_demo import EVALUATION_METRICS, add_evaluation_scores
from simulator import AccountConfig, SimulationConfig, compare_mechanisms, delayed_oracle_path


def scenario_group(scenario: str) -> str:
    if scenario.startswith("real_normal"):
        return "normal"
    if scenario.startswith("real_drawdown"):
        return "drawdown"
    if scenario.startswith("counterfactual_oracle_shock"):
        return "oracle shock"
    return scenario


def aggregate_real_scores(metrics_df: pd.DataFrame) -> pd.DataFrame:
    aggregate = (
        metrics_df.groupby("mechanism", as_index=False)
        .agg(
            aggregate_mean_rank=("mean_rank", "mean"),
            aggregate_metric_win_count=("metric_win_count", "sum"),
            pareto_efficient_count=("pareto_efficient", "sum"),
            solvency_violation_count=("solvency_feasible", lambda x: int((~x).sum())),
            aggregate_topsis_score=("topsis_score", "mean"),
            max_bad_debt=("max_bad_debt", "max"),
            bad_debt_es95=("bad_debt_es95", "max"),
            false_liquidation_loss=("false_liquidation_loss", "sum"),
            total_user_loss=("total_user_loss", "sum"),
            liquidation_count=("liquidation_count", "sum"),
        )
        .sort_values(
            [
                "solvency_violation_count",
                "aggregate_topsis_score",
                "aggregate_mean_rank",
                "aggregate_metric_win_count",
            ],
            ascending=[True, False, True, False],
        )
    )
    return aggregate


def summarize_adaptive_components(
    selected_paths: dict[str, dict[str, pd.DataFrame]],
) -> pd.DataFrame:
    rows = []
    for scenario, paths in selected_paths.items():
        path = paths["uspl"]
        uncertain = path.loc[path["zone"] == "uncertainty"]
        if uncertain.empty:
            rows.append(
                {
                    "scenario": scenario,
                    "uncertainty_steps": 0,
                    "avg_unsafe_probability": 0.0,
                    "avg_solvency_close_cap": 0.0,
                    "avg_user_close_cap": 0.0,
                    "avg_adaptive_close_cap": 0.0,
                    "max_adaptive_close_cap": 0.0,
                }
            )
            continue
        rows.append(
            {
                "scenario": scenario,
                "uncertainty_steps": int(len(uncertain)),
                "avg_unsafe_probability": float(uncertain["unsafe_probability"].mean()),
                "avg_solvency_close_cap": float(uncertain["solvency_close_cap"].mean()),
                "avg_user_close_cap": float(uncertain["user_close_cap"].mean()),
                "avg_adaptive_close_cap": float(uncertain["adaptive_close_cap"].mean()),
                "max_adaptive_close_cap": float(uncertain["adaptive_close_cap"].max()),
            }
        )
    return pd.DataFrame(rows)


def summarize_adaptive_by_group(adaptive_summary_df: pd.DataFrame) -> pd.DataFrame:
    grouped = adaptive_summary_df.copy()
    grouped["scenario_group"] = grouped["scenario"].map(scenario_group)
    return (
        grouped.groupby("scenario_group", as_index=False)
        .agg(
            uncertainty_steps=("uncertainty_steps", "sum"),
            avg_unsafe_probability=("avg_unsafe_probability", "mean"),
            avg_solvency_close_cap=("avg_solvency_close_cap", "mean"),
            avg_user_close_cap=("avg_user_close_cap", "mean"),
            avg_adaptive_close_cap=("avg_adaptive_close_cap", "mean"),
            max_adaptive_close_cap=("max_adaptive_close_cap", "max"),
        )
        .sort_values("scenario_group")
    )


def aggregate_by_scenario_group(metrics_df: pd.DataFrame) -> pd.DataFrame:
    grouped = metrics_df.copy()
    grouped["scenario_group"] = grouped["scenario"].map(scenario_group)
    return (
        grouped.groupby(["scenario_group", "mechanism"], as_index=False)
        .agg(
            window_count=("scenario", "nunique"),
            solvency_violation_count=("solvency_feasible", lambda x: int((~x).sum())),
            max_bad_debt=("max_bad_debt", "max"),
            bad_debt_es95=("bad_debt_es95", "max"),
            false_liquidation_loss=("false_liquidation_loss", "sum"),
            total_user_loss=("total_user_loss", "sum"),
            liquidation_delay=("delay_for_score", "mean"),
            liquidation_count=("liquidation_count", "sum"),
            avg_topsis_score=("topsis_score", "mean"),
            avg_mean_rank=("mean_rank", "mean"),
        )
        .sort_values(["scenario_group", "mechanism"])
    )


def account_for_window(initial_price: float, target_hf: float = 1.18) -> AccountConfig:
    base = AccountConfig(initial_price=float(initial_price))
    debt = base.collateral_eth * initial_price * base.liquidation_threshold / target_hf
    return AccountConfig(initial_price=float(initial_price), debt_usdc=float(debt))


def rolling_window_stats(df: pd.DataFrame, window: int) -> pd.DataFrame:
    rows = []
    prices = df["eth_usd"].reset_index(drop=True)
    for start in range(0, len(prices) - window + 1):
        segment = prices.iloc[start : start + window]
        returns = segment.pct_change().dropna()
        rows.append(
            {
                "start": start,
                "end": start + window,
                "start_date": df["date"].iloc[start],
                "end_date": df["date"].iloc[start + window - 1],
                "initial_price": float(segment.iloc[0]),
                "ending_price": float(segment.iloc[-1]),
                "cumulative_return": float(segment.iloc[-1] / segment.iloc[0] - 1.0),
                "volatility": float(returns.std()),
                "max_drawdown": float((segment / segment.cummax() - 1.0).min()),
            }
        )
    return pd.DataFrame(rows)


def evaluate_rolling_drawdown_windows(
    df: pd.DataFrame,
    config: SimulationConfig,
    target_hf: float,
    top_n: int = 20,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    windows = rolling_window_stats(df, config.n_steps)
    stress_windows = (
        windows.sort_values(["max_drawdown", "cumulative_return"])
        .head(top_n)
        .reset_index(drop=True)
    )

    all_metrics = []
    for idx, row in stress_windows.iterrows():
        frame = df.iloc[int(row["start"]) : int(row["end"])]
        market = frame["eth_usd"].to_numpy(dtype=float)
        raw_oracle = delayed_oracle_path(market, config.oracle_delay)
        account = account_for_window(float(market[0]), target_hf=target_hf)
        metrics, _ = compare_mechanisms(
            f"rolling_drawdown_{idx + 1:02d}",
            config=config,
            account=account,
            market_prices=market,
            raw_oracle_prices=raw_oracle,
        )
        metrics["window_rank"] = idx + 1
        metrics["window_start_date"] = row["start_date"]
        metrics["window_end_date"] = row["end_date"]
        metrics["window_cumulative_return"] = row["cumulative_return"]
        metrics["window_max_drawdown"] = row["max_drawdown"]
        all_metrics.append(metrics)

    scored = add_evaluation_scores(pd.concat(all_metrics, ignore_index=True))
    aggregate = (
        scored.groupby("mechanism", as_index=False)
        .agg(
            window_count=("scenario", "nunique"),
            bad_debt_window_count=("max_bad_debt", lambda x: int((x > 1e-9).sum())),
            avg_topsis_score=("topsis_score", "mean"),
            avg_mean_rank=("mean_rank", "mean"),
            max_bad_debt=("max_bad_debt", "max"),
            avg_bad_debt_es95=("bad_debt_es95", "mean"),
            total_false_liquidation_loss=("false_liquidation_loss", "sum"),
            total_user_loss=("total_user_loss", "sum"),
            total_liquidation_count=("liquidation_count", "sum"),
        )
        .sort_values(
            ["bad_debt_window_count", "avg_topsis_score", "avg_mean_rank"],
            ascending=[True, False, True],
        )
    )
    return stress_windows, scored, aggregate


def _add_value_labels(ax, fmt: str = "{:.2f}", padding: float = 0.01) -> None:
    y_min, y_max = ax.get_ylim()
    offset = (y_max - y_min) * padding
    for patch in ax.patches:
        height = patch.get_height()
        if abs(height) < 1e-12:
            continue
        ax.text(
            patch.get_x() + patch.get_width() / 2,
            height + offset,
            fmt.format(height),
            ha="center",
            va="bottom",
            fontsize=8,
        )


def plot_visual_summary(
    aggregate_df: pd.DataFrame,
    rolling_aggregate_df: pd.DataFrame,
    adaptive_summary_df: pd.DataFrame,
    output_dir: Path,
) -> None:
    """Create a one-page evidence figure for the course report.

    The existing figures are useful for detailed checking, but a course report
    benefits from one visual that compresses the main evaluation logic:
    solvency first, then borrower protection, then MCDM ranking, then the USPL
    mechanism's interpretable internal quantities.
    """
    mechanism_order = ["fixed", "twap", "buffer", "uspl"]
    colors = {
        "fixed": "#4C78A8",
        "twap": "#F58518",
        "buffer": "#54A24B",
        "uspl": "#E45756",
    }
    aggregate = aggregate_df.set_index("mechanism").reindex(mechanism_order)
    rolling = rolling_aggregate_df.set_index("mechanism").reindex(mechanism_order)
    adaptive = adaptive_summary_df.set_index("scenario")
    adaptive = adaptive.loc[[s for s in ["drawdown", "oracle shock"] if s in adaptive.index]]

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.2))
    fig.suptitle(
        "USPL evaluation summary: solvency constraint, user protection, and adaptive close factor",
        fontsize=15,
        fontweight="bold",
        y=0.98,
    )

    ax = axes[0, 0]
    counts = rolling["bad_debt_window_count"]
    ax.bar(
        counts.index,
        counts.values,
        color=[colors[m] for m in counts.index],
        width=0.65,
    )
    ax.set_title("A. Rolling drawdown stress: bad-debt windows")
    ax.set_ylabel("windows with bad debt / 20")
    ax.set_ylim(0, 21)
    ax.grid(axis="y", alpha=0.25)
    _add_value_labels(ax, "{:.0f}")

    ax = axes[0, 1]
    false_loss = aggregate["false_liquidation_loss"]
    ax.bar(
        false_loss.index,
        false_loss.values,
        color=[colors[m] for m in false_loss.index],
        width=0.65,
    )
    ax.set_title("B. Representative scenarios: total false-liquidation loss")
    ax.set_ylabel("loss")
    ax.grid(axis="y", alpha=0.25)
    _add_value_labels(ax, "{:.1f}")

    ax = axes[1, 0]
    topsis = aggregate["aggregate_topsis_score"]
    violations = aggregate["solvency_violation_count"]
    bars = ax.bar(
        topsis.index,
        topsis.values,
        color=[colors[m] for m in topsis.index],
        width=0.65,
    )
    for bar, mechanism in zip(bars, topsis.index):
        value = topsis.loc[mechanism]
        if violations.loc[mechanism] > 0:
            bar.set_hatch("//")
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.045,
                f"{value:.2f}\nsolvency\nviolation",
                ha="center",
                va="bottom",
                fontsize=8,
            )
        else:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.012,
                f"{value:.2f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )
    ax.set_title("C. Aggregate TOPSIS score with solvency-feasibility flag")
    ax.set_ylabel("TOPSIS score")
    ax.set_ylim(0, max(0.55, topsis.max() + 0.16))
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 1]
    component_cols = [
        "avg_unsafe_probability",
        "avg_solvency_close_cap",
        "avg_user_close_cap",
        "avg_adaptive_close_cap",
    ]
    component_labels = ["pi", "c_solv", "c_user", "cap"]
    component_colors = ["#B279A2", "#72B7B2", "#FF9DA6", "#E45756"]
    if not adaptive.empty:
        x = range(len(adaptive.index))
        width = 0.18
        for idx, (col, label, color) in enumerate(
            zip(component_cols, component_labels, component_colors)
        ):
            offsets = [pos + (idx - 1.5) * width for pos in x]
            ax.bar(
                offsets,
                adaptive[col].values,
                width=width,
                label=label,
                color=color,
            )
        ax.set_xticks(list(x))
        ax.set_xticklabels(list(adaptive.index))
        ax.set_ylim(0, 0.62)
    ax.set_title("D. USPL uncertainty-zone components")
    ax.set_ylabel("average value")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(ncol=4, fontsize=8, loc="upper center")

    for ax in axes.ravel():
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(axis="x", labelrotation=0)

    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(output_dir / "real_visual_summary.png", dpi=200)


def main() -> None:
    output_dir = Path("outputs")
    data_dir = Path("data")
    output_dir.mkdir(exist_ok=True)
    data_dir.mkdir(exist_ok=True)

    config = SimulationConfig()
    target_hf = 1.18
    shock_ratio = 0.75
    raw_df = fetch_eth_usd_daily(data_dir / "eth_usd_coingecko_daily.csv")
    scenarios = build_real_scenarios(
        raw_df,
        window=config.n_steps,
        oracle_delay=config.oracle_delay,
        shock_ratio=shock_ratio,
        windows_per_type=3,
    )

    all_metrics = []
    selected_paths = {}
    window_rows = []
    for scenario, payload in scenarios.items():
        frame = payload["frame"]
        market = payload["market"]
        raw_oracle = payload["raw_oracle"]
        account = account_for_window(float(market[0]), target_hf=target_hf)
        metrics, paths = compare_mechanisms(
            scenario,
            config=config,
            account=account,
            market_prices=market,
            raw_oracle_prices=raw_oracle,
        )
        all_metrics.append(metrics)
        selected_paths[scenario] = paths
        window_rows.append(
            {
                "scenario": scenario,
                "scenario_group": scenario_group(scenario),
                "start_date": frame["date"].iloc[0],
                "end_date": frame["date"].iloc[-1],
                "initial_price": float(market[0]),
                "ending_price": float(market[-1]),
                "cumulative_return": float(market[-1] / market[0] - 1.0),
                "account_debt_usdc": account.debt_usdc,
            }
        )

    metrics_df = add_evaluation_scores(pd.concat(all_metrics, ignore_index=True))
    aggregate_df = aggregate_real_scores(metrics_df)
    windows_df = pd.DataFrame(window_rows)
    adaptive_summary_df = summarize_adaptive_components(selected_paths)
    adaptive_group_summary_df = summarize_adaptive_by_group(adaptive_summary_df)
    group_metrics_df = aggregate_by_scenario_group(metrics_df)
    rolling_windows_df, rolling_metrics_df, rolling_aggregate_df = (
        evaluate_rolling_drawdown_windows(
            raw_df,
            config=config,
            target_hf=target_hf,
            top_n=20,
        )
    )

    metrics_df.to_csv(output_dir / "real_data_metrics.csv", index=False)
    aggregate_df.to_csv(output_dir / "real_aggregate_scores.csv", index=False)
    group_metrics_df.to_csv(output_dir / "real_group_metrics.csv", index=False)
    windows_df.to_csv(output_dir / "real_data_windows.csv", index=False)
    adaptive_summary_df.to_csv(output_dir / "real_adaptive_summary.csv", index=False)
    adaptive_group_summary_df.to_csv(
        output_dir / "real_adaptive_group_summary.csv",
        index=False,
    )
    rolling_windows_df.to_csv(output_dir / "real_rolling_drawdown_windows.csv", index=False)
    rolling_metrics_df.to_csv(output_dir / "real_rolling_drawdown_metrics.csv", index=False)
    rolling_aggregate_df.to_csv(
        output_dir / "real_rolling_drawdown_aggregate.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "target_initial_health_factor": target_hf,
                "oracle_shock_ratio": shock_ratio,
                "use_adaptive_close_factor": config.use_adaptive_close_factor,
                "false_loss_budget_rate": config.false_loss_budget_rate,
                "cap_min": config.cap_min,
                "cap_max": config.cap_max,
                "curve_low_uncertainty": config.curve_low_uncertainty,
                "curve_high_uncertainty": config.curve_high_uncertainty,
            }
        ]
    ).to_csv(output_dir / "real_adaptive_parameters.csv", index=False)

    print(windows_df.round(4).to_string(index=False))
    print("\nAdaptive parameters")
    print(pd.read_csv(output_dir / "real_adaptive_parameters.csv").round(4).to_string(index=False))
    print("\nAdaptive close-factor summary")
    print(adaptive_summary_df.round(4).to_string(index=False))
    print(metrics_df.round(4).to_string(index=False))
    print("\nReal-data aggregate scores")
    print(aggregate_df.round(4).to_string(index=False))
    print("\nRolling drawdown robustness aggregate")
    print(rolling_aggregate_df.round(4).to_string(index=False))
    plot_visual_summary(
        aggregate_df=aggregate_df,
        rolling_aggregate_df=rolling_aggregate_df,
        adaptive_summary_df=adaptive_group_summary_df.rename(
            columns={"scenario_group": "scenario"}
        ),
        output_dir=output_dir,
    )

    path_scenarios = [
        "real_normal_1",
        "real_drawdown_1",
        "counterfactual_oracle_shock_1",
    ]
    fig, axes = plt.subplots(3, 2, figsize=(13, 11), sharex=False)
    for row, scenario in enumerate(path_scenarios):
        path = selected_paths[scenario]["uspl"]
        frame = scenarios[scenario]["frame"]
        title_range = f"{frame['date'].iloc[0].date()} to {frame['date'].iloc[-1].date()}"

        price_ax = axes[row, 0]
        price_ax.plot(path["step"], path["market_price"], label="market price")
        price_ax.plot(path["step"], path["oracle_price"], label="oracle price")
        price_ax.fill_between(
            path["step"],
            path["price_low"],
            path["price_high"],
            alpha=0.18,
            label="oracle uncertainty interval",
        )
        price_ax.set_title(f"{scenario}: {title_range}")
        price_ax.set_ylabel("ETH/USD")
        price_ax.legend(loc="best", fontsize=8)

        hf_ax = axes[row, 1]
        hf_ax.plot(path["step"], path["true_hf"], label="true HF")
        hf_ax.plot(path["step"], path["oracle_hf"], label="oracle HF")
        hf_ax.fill_between(
            path["step"],
            path["hf_min"],
            path["hf_max"],
            alpha=0.20,
            label="USPL HF interval",
        )
        hf_ax.axhline(1.0, color="black", linewidth=1, linestyle=":")
        for liq_step in path.loc[path["liquidated"], "step"]:
            hf_ax.axvline(liq_step, color="tab:red", alpha=0.25, linewidth=1)
        hf_ax.set_title(f"{scenario}: Health Factor interval")
        hf_ax.set_ylabel("Health Factor")
        hf_ax.legend(loc="best", fontsize=8)

    axes[-1, 0].set_xlabel("Step")
    axes[-1, 1].set_xlabel("Step")
    fig.tight_layout()
    fig.savefig(output_dir / "real_data_paths.png", dpi=180)

    group_plot_df = metrics_df.copy()
    group_plot_df["scenario_group"] = group_plot_df["scenario"].map(scenario_group)
    scenario_order = ["normal", "drawdown", "oracle shock"]
    mechanism_order = ["fixed", "twap", "buffer", "uspl"]
    metrics_to_plot = [
        ("false_liquidation_loss", "False liquidation loss"),
        ("bad_debt_es95", "Bad debt ES95"),
        ("total_user_loss", "Total user loss"),
        ("topsis_score", "TOPSIS score"),
    ]
    fig2, axes2 = plt.subplots(2, 2, figsize=(13, 8))
    for ax, (metric, title) in zip(axes2.ravel(), metrics_to_plot):
        plot_values = (
            group_plot_df.groupby(["scenario_group", "mechanism"], as_index=False)[metric]
            .mean()
        )
        pivot = plot_values.pivot(
            index="scenario_group",
            columns="mechanism",
            values=metric,
        )
        pivot = pivot.reindex(index=scenario_order, columns=mechanism_order)
        pivot.plot(kind="bar", ax=ax)
        ax.set_title(title)
        ax.set_xlabel("")
        ax.tick_params(axis="x", labelrotation=0)
        ax.grid(axis="y", alpha=0.25)
        ax.legend(loc="best", fontsize=8)
    fig2.tight_layout()
    fig2.savefig(output_dir / "real_mechanism_metrics.png", dpi=180)

    fig3, axes3 = plt.subplots(1, 3, figsize=(15, 4.5), sharex=False, sharey=False)
    markers = {"fixed": "o", "twap": "s", "buffer": "^", "uspl": "D"}
    for ax, scenario in zip(axes3, path_scenarios):
        group = metrics_df.loc[metrics_df["scenario"] == scenario]
        for _, record in group.iterrows():
            ax.scatter(
                record["protocol_risk_axis"],
                record["user_risk_axis"],
                marker=markers[record["mechanism"]],
                s=80,
                label=record["mechanism"],
            )
            ax.annotate(
                record["mechanism"],
                (record["protocol_risk_axis"], record["user_risk_axis"]),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=8,
            )
        ax.set_title(f"{scenario}: protocol-user risk")
        ax.set_xlabel("Protocol risk axis")
        ax.set_ylabel("User risk axis")
        ax.grid(alpha=0.25)
    handles, labels = axes3[0].get_legend_handles_labels()
    fig3.legend(handles, labels, loc="upper center", ncol=4)
    fig3.tight_layout(rect=(0, 0, 1, 0.90))
    fig3.savefig(output_dir / "real_pareto_risk_frontier.png", dpi=180)

    fig4, ax4 = plt.subplots(figsize=(8, 4.5))
    aggregate_df.set_index("mechanism")["aggregate_topsis_score"].plot(
        kind="bar",
        ax=ax4,
        color="tab:blue",
    )
    ax4.set_title("Real-data aggregate TOPSIS score (higher is better)")
    ax4.set_xlabel("")
    ax4.set_ylabel("TOPSIS score")
    ax4.grid(axis="y", alpha=0.25)
    fig4.tight_layout()
    fig4.savefig(output_dir / "real_aggregate_topsis_score.png", dpi=180)
    fig4.savefig(output_dir / "real_aggregate_mean_rank.png", dpi=180)

    print("\nEvaluation metrics:", ", ".join(EVALUATION_METRICS))
    print(output_dir / "real_adaptive_parameters.csv")
    print(output_dir / "real_adaptive_summary.csv")
    print(output_dir / "real_adaptive_group_summary.csv")
    print(output_dir / "real_data_metrics.csv")
    print(output_dir / "real_group_metrics.csv")
    print(output_dir / "real_aggregate_scores.csv")
    print(output_dir / "real_rolling_drawdown_aggregate.csv")
    print(output_dir / "real_visual_summary.png")
    print(output_dir / "real_data_paths.png")


if __name__ == "__main__":
    main()
