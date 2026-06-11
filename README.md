# DeFi Oracle Uncertainty Liquidation Research Prototype

This project supports the course report:

**预言机不确定性下 DeFi 抵押借贷清算机制的风险权衡与改进研究**

It contains a lightweight Python simulator, a Streamlit demo, and Solidity contract drafts for a simplified oracle-driven lending protocol.

## Project Structure

```text
src/uspl/
  simulator.py      # core simulation logic
  run_demo.py       # command-line demo and chart export
  real_data.py      # CoinGecko ETH/USD data loading and scenario construction
  run_real_data.py  # real-data experiment, calibration, and chart export

app/
  streamlit_app.py  # interactive visualization

contracts/
  MockOracle.sol
  SimpleLendingUSPL.sol
```

## Run The Real-Data Experiment

```bash
python3 src/uspl/run_real_data.py
```

The script downloads or reuses cached CoinGecko ETH/USD daily prices and builds:

- `real_normal`: real stable ETH/USD window
- `real_drawdown`: real ETH/USD drawdown window
- `counterfactual_oracle_shock`: real stable ETH/USD window with a counterfactual short oracle shock

Outputs:

```text
data/eth_usd_coingecko_daily.csv
outputs/real_data_windows.csv
outputs/real_adaptive_parameters.csv
outputs/real_adaptive_summary.csv
outputs/real_data_metrics.csv
outputs/real_aggregate_scores.csv
outputs/real_rolling_drawdown_windows.csv
outputs/real_rolling_drawdown_metrics.csv
outputs/real_rolling_drawdown_aggregate.csv
outputs/real_data_paths.png
outputs/real_mechanism_metrics.png
outputs/real_pareto_risk_frontier.png
outputs/real_aggregate_topsis_score.png
outputs/real_aggregate_mean_rank.png
```

## Run The Synthetic Demo

```bash
python3 src/uspl/run_demo.py
```

Outputs:

```text
outputs/demo_metrics.csv
outputs/aggregate_scores.csv
outputs/demo_paths.png
outputs/mechanism_metrics.png
outputs/pareto_risk_frontier.png
outputs/aggregate_topsis_score.png
outputs/aggregate_risk_score.png
```

## Run The Streamlit Demo

```bash
streamlit run app/streamlit_app.py
```

## Mechanisms Compared

- `fixed`: fixed-threshold liquidation based on point oracle price.
- `twap`: simple moving-average price filtering.
- `buffer`: conservative safety-buffer threshold.
- `uspl`: uncertainty-scaled partial liquidation with an adaptive close factor; the piecewise curve remains as a fallback for sensitivity analysis.

## USPL Rule

```text
P_t ∈ [P_low,t, P_high,t]
HF_min,t = health_factor(P_low,t)
HF_max,t = health_factor(P_high,t)

if HF_min,t > 1:
    safe zone
elif HF_max,t < 1:
    liquidation zone
else:
    uncertainty zone
    pi_t = interval-implied unsafe probability
    c_solv,t = minimum close factor for lower-bound solvency
    c_user,t = maximum close factor under false-liquidation budget
    cap_t = clip(pi_t * c_solv,t + (1 - pi_t) * c_user,t)
```

The simulator is intentionally stylized. It is designed for mechanism analysis and reproducible comparison, not for real trading or production DeFi deployment.

## Default Demo Parameters

The current defaults are chosen for course-report interpretability:

- debt: `1900 USDC`
- oracle delay: `3` steps
- base uncertainty width: `2%`
- max uncertainty width: `10%`
- liquidation cap range: `cap_min = 5%`, `cap_max = 50%`
- adaptive false-liquidation loss budget: `B = 0.005`
- piecewise curve thresholds: `q_low = 0.15`, `q_high = 0.20`

These defaults are not claimed to be optimal. They are used to make the main trade-off visible:

- TWAP can reduce false liquidation but may lag during rapid drawdowns.
- Safety buffers can reduce bad debt but may increase early liquidation.
- USPL can reduce false-liquidation loss in oracle-shock uncertainty zones while preserving enough liquidation intensity in sustained drawdowns.
- Evaluation uses constrained multi-objective comparison: solvency feasibility first, Pareto checks second, TOPSIS as a standard MCDM auxiliary ranking method, and equal-weight metric ranks only as a robustness check.
