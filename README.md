# DeFi Oracle Uncertainty Liquidation MVP

This project supports the course report:

**基于预言机不确定性的 DeFi 抵押借贷分区清算机制设计与风险分析**

It contains a lightweight Python simulator, a Streamlit demo, and Solidity contract drafts for a simplified oracle-driven lending protocol.

## Project Structure

```text
src/uspl/
  simulator.py      # core simulation logic
  run_demo.py       # command-line demo and chart export

app/
  streamlit_app.py  # interactive visualization

contracts/
  MockOracle.sol
  SimpleLendingUSPL.sol
```

## Run The Python Demo

```bash
python3 src/uspl/run_demo.py
```

Outputs:

```text
outputs/demo_metrics.csv
outputs/demo_paths.png
```

## Run The Streamlit Demo

```bash
streamlit run app/streamlit_app.py
```

## Mechanisms Compared

- `fixed`: fixed-threshold liquidation based on point oracle price.
- `twap`: simple moving-average price filtering.
- `buffer`: conservative safety-buffer threshold.
- `uspl`: uncertainty-scaled partial liquidation.

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
    cap_t = clip(cap_max - gamma * U_t, cap_min, cap_max)
```

The simulator is intentionally stylized. It is designed for course demonstration, not for real trading or production DeFi deployment.

## Default Demo Parameters

The current defaults are chosen for course-report interpretability:

- debt: `1900 USDC`
- oracle delay: `3` steps
- base uncertainty width: `2%`
- max uncertainty width: `10%`
- liquidation cap range: `cap_min = 5%`, `cap_max = 50%`
- uncertainty penalty: `gamma = 1.0`

These defaults are not claimed to be optimal. They are used to make the main trade-off visible:

- TWAP can reduce false liquidation but may lag during rapid drawdowns.
- Safety buffers can reduce bad debt but may increase early liquidation.
- USPL can reduce false-liquidation loss in flash-crash-like uncertainty zones, while still having failure modes under sustained drawdowns.
