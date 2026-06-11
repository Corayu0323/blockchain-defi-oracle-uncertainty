from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "uspl"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from simulator import AccountConfig, SimulationConfig, compare_mechanisms  # noqa: E402


st.set_page_config(page_title="USPL Liquidation Demo", layout="wide")

st.title("USPL DeFi Liquidation Demo")

with st.sidebar:
    scenario = st.selectbox("Price scenario", ["normal", "drawdown", "flash_crash"], index=1)
    oracle_delay = st.slider("Oracle delay", 0, 12, 3)
    base_uncertainty_width = st.slider("Base uncertainty width", 0.0, 0.10, 0.02, 0.005)
    uncertainty_width = st.slider("Max uncertainty width", 0.02, 0.20, 0.10, 0.005)
    gamma = st.slider("Fallback gamma", 0.0, 10.0, 2.0, 0.1)
    false_loss_budget_rate = st.slider("False loss budget B", 0.0, 0.03, 0.005, 0.001)
    cap_min = st.slider("cap_min", 0.0, 0.30, 0.05, 0.01)
    cap_max = st.slider("cap_max", 0.10, 1.00, 0.50, 0.05)
    curve_low_uncertainty = st.slider("q_low", 0.02, 0.30, 0.15, 0.01)
    curve_high_uncertainty = st.slider("q_high", 0.03, 0.40, 0.20, 0.01)
    debt_usdc = st.slider("Debt USDC", 500, 2600, 1900, 50)

if curve_high_uncertainty <= curve_low_uncertainty:
    curve_high_uncertainty = curve_low_uncertainty + 0.01

config = SimulationConfig(
    oracle_delay=oracle_delay,
    base_uncertainty_width=base_uncertainty_width,
    uncertainty_width=uncertainty_width,
    gamma=gamma,
    false_loss_budget_rate=false_loss_budget_rate,
    cap_min=cap_min,
    cap_max=cap_max,
    curve_low_uncertainty=curve_low_uncertainty,
    curve_high_uncertainty=curve_high_uncertainty,
)
account = AccountConfig(debt_usdc=float(debt_usdc))

metrics, paths = compare_mechanisms(scenario, config=config, account=account)

st.subheader("Mechanism Metrics")
st.dataframe(metrics.round(4), width="stretch")

uspl = paths["uspl"]

left, right = st.columns(2)

with left:
    st.subheader("Price And Oracle Interval")
    price_chart = uspl.set_index("step")[
        ["market_price", "oracle_price", "price_low", "price_high"]
    ]
    st.line_chart(price_chart)

with right:
    st.subheader("USPL Health Factor Interval")
    hf_chart = uspl.set_index("step")[["true_hf", "oracle_hf", "hf_min", "hf_max"]]
    st.line_chart(hf_chart)

st.subheader("USPL Zone And Liquidation Events")
zone_view = uspl[
    [
        "step",
        "zone",
        "close_cap",
        "true_hf",
        "hf_min",
        "hf_max",
        "liquidated",
        "repaid_usdc",
        "user_loss",
        "bad_debt",
    ]
]
st.dataframe(zone_view.round(4), width="stretch")

st.subheader("All Mechanism Paths")
combined = pd.concat(paths.values(), ignore_index=True)
st.dataframe(
    combined[
        [
            "step",
            "mechanism",
            "market_price",
            "oracle_price",
            "true_hf",
            "oracle_hf",
            "zone",
            "close_cap",
            "liquidated",
            "bad_debt",
            "user_loss",
        ]
    ].round(4),
    width="stretch",
)
