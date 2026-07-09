from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from simulator import AccountConfig, SimulationConfig, simulate


def run_sensitivity() -> pd.DataFrame:
    account = AccountConfig()
    budget_rates = [0.001, 0.003, 0.005, 0.008, 0.010, 0.015]
    scenarios = ["drawdown", "flash_crash"]
    rows = []

    for scenario in scenarios:
        for budget_rate in budget_rates:
            config = SimulationConfig(false_loss_budget_rate=budget_rate)
            result = simulate(scenario, "uspl", config=config, account=account)
            rows.append(
                {
                    "scenario": scenario,
                    "false_loss_budget_rate": budget_rate,
                    **result.metrics,
                }
            )

    return pd.DataFrame(rows)


def plot_sensitivity(df: pd.DataFrame, output_dir: Path) -> None:
    metrics = [
        ("false_liquidation_loss", "False liquidation loss"),
        ("total_user_loss", "Total user loss"),
        ("max_bad_debt", "Max bad debt"),
        ("liquidation_count", "Liquidation count"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    for ax, (metric, title) in zip(axes.ravel(), metrics):
        for scenario, group in df.groupby("scenario"):
            ax.plot(
                group["false_loss_budget_rate"],
                group[metric],
                marker="o",
                label=scenario,
            )
        ax.set_title(title)
        ax.set_xlabel("false loss budget B")
        ax.grid(alpha=0.25)
        ax.legend()

    fig.tight_layout()
    fig.savefig(output_dir / "uspl_budget_sensitivity.png", dpi=180)


def main() -> None:
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    df = run_sensitivity()
    df.to_csv(output_dir / "uspl_budget_sensitivity.csv", index=False)
    plot_sensitivity(df, output_dir)

    cols = [
        "scenario",
        "false_loss_budget_rate",
        "false_liquidation_loss",
        "total_user_loss",
        "max_bad_debt",
        "liquidation_count",
        "liquidation_delay",
    ]
    print(df[cols].round(4).to_string(index=False))
    print(output_dir / "uspl_budget_sensitivity.csv")
    print(output_dir / "uspl_budget_sensitivity.png")


if __name__ == "__main__":
    main()
