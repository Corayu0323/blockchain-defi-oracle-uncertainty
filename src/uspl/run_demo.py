from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from simulator import AccountConfig, SimulationConfig, compare_mechanisms


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

    metrics_df = pd.concat(all_metrics, ignore_index=True)
    metrics_df.to_csv(output_dir / "demo_metrics.csv", index=False)
    print(metrics_df.round(4).to_string(index=False))

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
        ("max_bad_debt", "Max bad debt"),
        ("total_user_loss", "Total user loss"),
        ("liquidation_delay", "Liquidation delay"),
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
    print(f"\nSaved: {output_dir / 'demo_metrics.csv'}")
    print(f"Saved: {output_dir / 'demo_paths.png'}")
    print(f"Saved: {output_dir / 'mechanism_metrics.png'}")


if __name__ == "__main__":
    main()
