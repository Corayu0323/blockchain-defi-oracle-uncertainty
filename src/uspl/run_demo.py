from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from simulator import AccountConfig, SimulationConfig, compare_mechanisms


EVALUATION_METRICS = [
    "bad_debt_es95",
    "false_liquidation_loss",
    "total_user_loss",
    "liquidation_delay",
    "liquidation_count",
]


def _mark_pareto_efficient(group: pd.DataFrame, metrics: list[str]) -> pd.Series:
    values = group[metrics].fillna(0.0).astype(float).to_numpy()
    efficient = []
    for i, row in enumerate(values):
        others = values
        no_worse = (others <= row).all(axis=1)
        strictly_better = (others < row).any(axis=1)
        dominated = bool((no_worse & strictly_better).any())
        efficient.append(not dominated)
    return pd.Series(efficient, index=group.index)


def _topsis_lower_better(group: pd.DataFrame, metrics: list[str]) -> pd.Series:
    values = group[metrics].fillna(0.0).astype(float)
    norm = (values.pow(2).sum(axis=0) ** 0.5).replace(0.0, 1.0)
    weighted = values.div(norm, axis=1) / len(metrics)
    ideal = weighted.min(axis=0)
    anti_ideal = weighted.max(axis=0)
    distance_to_ideal = ((weighted - ideal) ** 2).sum(axis=1) ** 0.5
    distance_to_anti = ((weighted - anti_ideal) ** 2).sum(axis=1) ** 0.5
    denominator = (distance_to_ideal + distance_to_anti).replace(0.0, 1.0)
    return distance_to_anti / denominator


def add_evaluation_scores(metrics_df: pd.DataFrame) -> pd.DataFrame:
    scored = metrics_df.copy()
    scored["delay_for_score"] = scored["liquidation_delay"].fillna(0.0)
    scored["liquidation_delay"] = scored["delay_for_score"]
    scored["solvency_feasible"] = (
        (scored["max_bad_debt"] <= 1e-9) & (scored["bad_debt_es95"] <= 1e-9)
    )

    pieces = []
    for _, group in scored.groupby("scenario", sort=False):
        group = group.copy()
        group["pareto_efficient"] = _mark_pareto_efficient(group, EVALUATION_METRICS)
        group["topsis_score"] = _topsis_lower_better(group, EVALUATION_METRICS)
        group["topsis_rank"] = group["topsis_score"].rank(
            method="average",
            ascending=False,
        )
        for metric in EVALUATION_METRICS:
            group[f"{metric}_rank"] = group[metric].fillna(0.0).rank(
                method="average",
                ascending=True,
            )
        rank_cols = [f"{metric}_rank" for metric in EVALUATION_METRICS]
        group["mean_rank"] = group[rank_cols].mean(axis=1)
        group["metric_win_count"] = sum(
            group[metric].fillna(0.0) == group[metric].fillna(0.0).min()
            for metric in EVALUATION_METRICS
        )
        group["user_risk_axis"] = group["false_liquidation_loss"] + 0.25 * group[
            "total_user_loss"
        ]
        group["protocol_risk_axis"] = group["bad_debt_es95"] + 0.25 * group[
            "max_bad_debt"
        ]
        pieces.append(group)
    return pd.concat(pieces, ignore_index=True)


def aggregate_stress_scores(metrics_df: pd.DataFrame) -> pd.DataFrame:
    stress = metrics_df.loc[metrics_df["scenario"].isin(["drawdown", "flash_crash"])]
    aggregate = (
        stress.groupby("mechanism", as_index=False)
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


def main() -> None:
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    account = AccountConfig()
    config = SimulationConfig()

    all_metrics = []
    selected_paths = {}
    for scenario in ["normal", "drawdown", "flash_crash"]:
        metrics, paths = compare_mechanisms(scenario, config=config, account=account)
        all_metrics.append(metrics)
        selected_paths[scenario] = paths

    metrics_df = add_evaluation_scores(pd.concat(all_metrics, ignore_index=True))
    aggregate_df = aggregate_stress_scores(metrics_df)
    metrics_df.to_csv(output_dir / "demo_metrics.csv", index=False)
    aggregate_df.to_csv(output_dir / "aggregate_scores.csv", index=False)
    print(metrics_df.round(4).to_string(index=False))
    print("\nAggregate stress scores")
    print(aggregate_df.round(4).to_string(index=False))

    fig, axes = plt.subplots(3, 2, figsize=(13, 11), sharex=True)
    for row, scenario in enumerate(selected_paths):
        path = selected_paths[scenario]["uspl"]

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
        price_ax.set_title(f"{scenario}: price interval")
        price_ax.set_ylabel("Price")
        price_ax.legend(loc="best")

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
        hf_ax.legend(loc="best")

    axes[-1, 0].set_xlabel("Step")
    axes[-1, 1].set_xlabel("Step")
    fig.tight_layout()
    fig.savefig(output_dir / "demo_paths.png", dpi=180)

    metrics_to_plot = [
        ("false_liquidation_loss", "False liquidation loss"),
        ("bad_debt_es95", "Bad debt ES95"),
        ("total_user_loss", "Total user loss"),
        ("topsis_score", "TOPSIS score"),
    ]
    fig2, axes2 = plt.subplots(2, 2, figsize=(13, 8))
    for ax, (metric, title) in zip(axes2.ravel(), metrics_to_plot):
        pivot = metrics_df.pivot(index="scenario", columns="mechanism", values=metric)
        pivot.plot(kind="bar", ax=ax)
        ax.set_title(title)
        ax.set_xlabel("")
        ax.legend(loc="best", fontsize=8)
    fig2.tight_layout()
    fig2.savefig(output_dir / "mechanism_metrics.png", dpi=180)

    fig3, axes3 = plt.subplots(1, 3, figsize=(15, 4.5), sharex=False, sharey=False)
    markers = {"fixed": "o", "twap": "s", "buffer": "^", "uspl": "D"}
    for ax, scenario in zip(axes3, ["normal", "drawdown", "flash_crash"]):
        group = metrics_df.loc[metrics_df["scenario"] == scenario]
        for _, row in group.iterrows():
            ax.scatter(
                row["protocol_risk_axis"],
                row["user_risk_axis"],
                marker=markers[row["mechanism"]],
                s=80,
                label=row["mechanism"],
            )
            ax.annotate(
                row["mechanism"],
                (row["protocol_risk_axis"], row["user_risk_axis"]),
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
    fig3.savefig(output_dir / "pareto_risk_frontier.png", dpi=180)

    fig4, ax4 = plt.subplots(figsize=(8, 4.5))
    aggregate_plot = aggregate_df.set_index("mechanism")["aggregate_topsis_score"]
    aggregate_plot.plot(kind="bar", ax=ax4, color="tab:blue")
    ax4.set_title("Aggregate stress TOPSIS score (higher is better)")
    ax4.set_xlabel("")
    ax4.set_ylabel("TOPSIS score")
    ax4.grid(axis="y", alpha=0.25)
    fig4.tight_layout()
    fig4.savefig(output_dir / "aggregate_topsis_score.png", dpi=180)
    fig4.savefig(output_dir / "aggregate_risk_score.png", dpi=180)
    print(f"\nSaved: {output_dir / 'demo_metrics.csv'}")
    print(f"Saved: {output_dir / 'aggregate_scores.csv'}")
    print(f"Saved: {output_dir / 'demo_paths.png'}")
    print(f"Saved: {output_dir / 'mechanism_metrics.png'}")
    print(f"Saved: {output_dir / 'pareto_risk_frontier.png'}")
    print(f"Saved: {output_dir / 'aggregate_topsis_score.png'}")


if __name__ == "__main__":
    main()
