from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


def add_box(ax, xy, width, height, text, facecolor="#f7f9fb", edgecolor="#44546a"):
    box = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.018,rounding_size=0.018",
        linewidth=1.2,
        edgecolor=edgecolor,
        facecolor=facecolor,
    )
    ax.add_patch(box)
    ax.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=10,
        color="#1f2933",
        linespacing=1.25,
    )


def add_arrow(ax, start, end, color="#44546a"):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=14,
        linewidth=1.2,
        color=color,
        shrinkA=4,
        shrinkB=4,
    )
    ax.add_patch(arrow)


def main() -> None:
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "uspl_framework.png"

    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    colors = {
        "source": "#eef5ff",
        "mechanism": "#f4fbf6",
        "action": "#fff7ed",
        "header": "#263238",
    }

    ax.text(
        0.17,
        0.92,
        "Oracle uncertainty sources",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        color=colors["header"],
    )
    ax.text(
        0.50,
        0.92,
        "USPL mechanism",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        color=colors["header"],
    )
    ax.text(
        0.83,
        0.92,
        "Liquidation actions and outcomes",
        ha="center",
        va="center",
        fontsize=12,
        fontweight="bold",
        color=colors["header"],
    )

    add_box(ax, (0.06, 0.70), 0.22, 0.11, "Oracle staleness", colors["source"])
    add_box(ax, (0.06, 0.54), 0.22, 0.11, "Oracle-market\nprice deviation", colors["source"])
    add_box(ax, (0.06, 0.38), 0.22, 0.11, "Recent oracle\nvolatility", colors["source"])

    add_box(
        ax,
        (0.39, 0.68),
        0.23,
        0.12,
        "Price interval\n$P_t \\in [P_{low,t}, P_{high,t}]$",
        colors["mechanism"],
    )
    add_box(
        ax,
        (0.39, 0.50),
        0.23,
        0.12,
        "Health Factor interval\n$[HF_{min,t}, HF_{max,t}]$",
        colors["mechanism"],
    )
    add_box(
        ax,
        (0.39, 0.32),
        0.23,
        0.12,
        "Uncertainty intensity\n$U_t = width / P_{oracle,t}$",
        colors["mechanism"],
    )

    add_box(ax, (0.72, 0.72), 0.23, 0.10, "Safe zone\nNo liquidation", colors["action"])
    add_box(
        ax,
        (0.72, 0.54),
        0.23,
        0.10,
        "Uncertainty zone\n$cap_t = f(\\pi_t,c_{solv},c_{user})$",
        colors["action"],
    )
    add_box(
        ax,
        (0.72, 0.36),
        0.23,
        0.10,
        "Liquidation zone\nNormal liquidation",
        colors["action"],
    )
    add_box(
        ax,
        (0.72, 0.13),
        0.23,
        0.12,
        "Evaluation metrics\nbad debt / false liquidation\nuser loss / delay",
        "#f9fafb",
    )

    for y in (0.755, 0.595, 0.435):
        add_arrow(ax, (0.28, y), (0.39, 0.74))

    add_arrow(ax, (0.505, 0.68), (0.505, 0.62))
    add_arrow(ax, (0.505, 0.50), (0.505, 0.44))
    add_arrow(ax, (0.62, 0.74), (0.72, 0.77))
    add_arrow(ax, (0.62, 0.56), (0.72, 0.59))
    add_arrow(ax, (0.62, 0.38), (0.72, 0.41))

    ax.text(
        0.50,
        0.05,
        "Figure: Oracle uncertainty is propagated into a Health Factor interval and then into liquidation intensity.",
        ha="center",
        va="center",
        fontsize=9,
        color="#4b5563",
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    fig.savefig(out_dir / "uspl_framework.svg", bbox_inches="tight")
    print(out_path)


if __name__ == "__main__":
    main()
