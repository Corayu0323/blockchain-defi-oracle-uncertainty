from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

import numpy as np
import pandas as pd


MechanismName = Literal["fixed", "twap", "buffer", "uspl"]
ScenarioName = Literal[
    "normal",
    "drawdown",
    "flash_crash",
    "real_normal",
    "real_drawdown",
    "counterfactual_oracle_shock",
]


class Zone(str, Enum):
    SAFE = "safe"
    UNCERTAIN = "uncertainty"
    LIQUIDATION = "liquidation"


@dataclass(frozen=True)
class AccountConfig:
    collateral_eth: float = 1.0
    debt_usdc: float = 1_900.0
    liquidation_threshold: float = 0.8
    liquidation_bonus: float = 0.05
    initial_price: float = 3_000.0


@dataclass(frozen=True)
class SimulationConfig:
    n_steps: int = 72
    seed: int = 7
    oracle_delay: int = 3
    base_uncertainty_width: float = 0.02
    uncertainty_width: float = 0.10
    twap_window: int = 6
    buffer_threshold: float = 1.04
    cap_min: float = 0.05
    cap_max: float = 0.50
    gamma: float = 2.0
    use_dynamic_uncertainty: bool = True
    deviation_sensitivity: float = 0.45
    volatility_sensitivity: float = 2.0
    use_adaptive_close_factor: bool = True
    false_loss_budget_rate: float = 0.005
    use_piecewise_close_factor: bool = True
    curve_low_uncertainty: float = 0.15
    curve_high_uncertainty: float = 0.20


@dataclass(frozen=True)
class SimulationResult:
    mechanism: str
    scenario: str
    path: pd.DataFrame
    metrics: dict[str, float]


def health_factor(
    collateral_eth: float,
    price: float,
    liquidation_threshold: float,
    debt_usdc: float,
) -> float:
    if debt_usdc <= 0:
        return np.inf
    return collateral_eth * price * liquidation_threshold / debt_usdc


def generate_market_price_path(
    scenario: ScenarioName,
    config: SimulationConfig,
    account: AccountConfig,
) -> np.ndarray:
    rng = np.random.default_rng(config.seed)
    prices = np.empty(config.n_steps, dtype=float)
    prices[0] = account.initial_price

    if scenario == "normal":
        returns = rng.normal(loc=0.0002, scale=0.006, size=config.n_steps - 1)
        for t, r in enumerate(returns, start=1):
            prices[t] = max(100.0, prices[t - 1] * (1.0 + r))

    elif scenario == "drawdown":
        returns = rng.normal(loc=-0.002, scale=0.01, size=config.n_steps - 1)
        shock_start = config.n_steps // 3
        shock_end = shock_start + 14
        returns[shock_start:shock_end] += -0.025
        for t, r in enumerate(returns, start=1):
            prices[t] = max(100.0, prices[t - 1] * (1.0 + r))

    elif scenario == "flash_crash":
        returns = rng.normal(loc=0.0, scale=0.006, size=config.n_steps - 1)
        for t, r in enumerate(returns, start=1):
            prices[t] = max(100.0, prices[t - 1] * (1.0 + r))
        crash_t = config.n_steps // 2
        prices[crash_t] *= 0.80
        prices[crash_t + 1] *= 0.88
        prices[crash_t + 2] = prices[crash_t - 1] * 0.98
        prices[crash_t + 3 :] = prices[crash_t - 1] * np.cumprod(
            1.0 + rng.normal(0.0003, 0.006, size=config.n_steps - crash_t - 3)
        )

    else:
        raise ValueError(f"Unknown scenario: {scenario}")

    return prices


def delayed_oracle_path(market_prices: np.ndarray, delay: int) -> np.ndarray:
    oracle = np.empty_like(market_prices)
    for t in range(len(market_prices)):
        oracle[t] = market_prices[max(0, t - delay)]
    return oracle


def twap_path(oracle_prices: np.ndarray, window: int) -> np.ndarray:
    series = pd.Series(oracle_prices)
    return series.rolling(window=window, min_periods=1).mean().to_numpy()


def uncertainty_width_path(
    oracle_prices: np.ndarray,
    config: SimulationConfig,
) -> np.ndarray:
    if not config.use_dynamic_uncertainty:
        return np.full_like(oracle_prices, config.uncertainty_width, dtype=float)

    oracle_series = pd.Series(oracle_prices)
    oracle_twap = oracle_series.rolling(
        window=config.twap_window,
        min_periods=1,
    ).mean()
    oracle_deviation = ((oracle_series - oracle_twap).abs() / oracle_series).fillna(0.0)
    oracle_volatility = oracle_series.pct_change().rolling(
        window=config.twap_window,
        min_periods=2,
    ).std().fillna(0.0)

    widths = (
        config.base_uncertainty_width
        + config.deviation_sensitivity * oracle_deviation
        + config.volatility_sensitivity * oracle_volatility
    )
    return widths.clip(
        lower=config.base_uncertainty_width,
        upper=config.uncertainty_width,
    ).to_numpy()


def uncertainty_scaled_close_cap(
    uncertainty_intensity: float,
    config: SimulationConfig,
) -> float:
    """Map oracle uncertainty into a capped close factor.

    The default implementation uses an auditable piecewise-linear curve. It
    preserves the old linear rule as a fallback, but the piecewise curve is a
    better approximation of an offline-calibrated close-factor table: medium
    uncertainty still allows meaningful liquidation, while high uncertainty
    sharply limits liquidation intensity.
    """
    if not config.use_piecewise_close_factor:
        return float(
            np.clip(
                config.cap_max - config.gamma * uncertainty_intensity,
                config.cap_min,
                config.cap_max,
            )
        )

    low = config.curve_low_uncertainty
    high = config.curve_high_uncertainty
    if high <= low:
        raise ValueError("curve_high_uncertainty must be greater than curve_low_uncertainty")

    high_uncertainty_cap = float(
        np.clip(
            config.cap_max - config.gamma * high,
            config.cap_min,
            config.cap_max,
        )
    )

    if uncertainty_intensity <= low:
        cap = config.cap_max
    elif uncertainty_intensity >= high:
        cap = high_uncertainty_cap
    else:
        slope = (config.cap_max - high_uncertainty_cap) / (high - low)
        cap = config.cap_max - slope * (uncertainty_intensity - low)

    return float(np.clip(cap, config.cap_min, config.cap_max))


def adaptive_close_factor_components(
    collateral_eth: float,
    debt_usdc: float,
    oracle_price: float,
    price_low: float,
    hf_min: float,
    hf_max: float,
    config: SimulationConfig,
    account: AccountConfig,
) -> dict[str, float]:
    """Closed-form close factor from solvency need and false-liquidation budget.

    The uncertainty-zone liquidation problem has two interpretable bounds:

    1. c_solv: minimum close factor that would restore HF_min to 1 after
       liquidation under the lower-bound oracle price.
    2. c_user: maximum close factor allowed by a false-liquidation loss budget.

    The risk probability pi is approximated by the share of the HF interval below
    the liquidation boundary under a uniform interval assumption. The final close
    factor interpolates between c_user and c_solv, so low-risk boundary states
    protect the borrower while high-risk states move toward solvency protection.
    """
    if debt_usdc <= 0:
        return {
            "unsafe_probability": 0.0,
            "solvency_close_cap": 0.0,
            "user_close_cap": 0.0,
            "adaptive_close_cap": 0.0,
        }

    hf_width = max(hf_max - hf_min, 1e-9)
    unsafe_probability = float(np.clip((1.0 - hf_min) / hf_width, 0.0, 1.0))

    lower_bound_collateral_value = (
        collateral_eth * price_low * account.liquidation_threshold
    )
    denominator = debt_usdc * (
        1.0
        - (1.0 + account.liquidation_bonus)
        * price_low
        * account.liquidation_threshold
        / max(oracle_price, 1e-9)
    )
    if denominator <= 0:
        solvency_close_cap = config.cap_max
    else:
        solvency_close_cap = (debt_usdc - lower_bound_collateral_value) / denominator
    solvency_close_cap = float(np.clip(solvency_close_cap, 0.0, config.cap_max))

    expected_false_state = max(1.0 - unsafe_probability, 1e-6)
    false_loss_budget = config.false_loss_budget_rate * debt_usdc
    user_close_cap = false_loss_budget / (
        expected_false_state * debt_usdc * account.liquidation_bonus
    )
    user_close_cap = float(np.clip(user_close_cap, config.cap_min, config.cap_max))

    cap = (
        unsafe_probability * solvency_close_cap
        + (1.0 - unsafe_probability) * user_close_cap
    )
    adaptive_close_cap = float(np.clip(cap, config.cap_min, config.cap_max))
    return {
        "unsafe_probability": unsafe_probability,
        "solvency_close_cap": solvency_close_cap,
        "user_close_cap": user_close_cap,
        "adaptive_close_cap": adaptive_close_cap,
    }


def adaptive_uncertainty_close_cap(
    collateral_eth: float,
    debt_usdc: float,
    oracle_price: float,
    price_low: float,
    hf_min: float,
    hf_max: float,
    config: SimulationConfig,
    account: AccountConfig,
) -> float:
    return adaptive_close_factor_components(
        collateral_eth,
        debt_usdc,
        oracle_price,
        price_low,
        hf_min,
        hf_max,
        config,
        account,
    )["adaptive_close_cap"]


def simulate(
    scenario: ScenarioName,
    mechanism: MechanismName,
    config: SimulationConfig | None = None,
    account: AccountConfig | None = None,
    market_prices: np.ndarray | None = None,
    raw_oracle_prices: np.ndarray | None = None,
) -> SimulationResult:
    config = config or SimulationConfig()
    account = account or AccountConfig()

    if market_prices is None:
        market = generate_market_price_path(scenario, config, account)
    else:
        market = np.asarray(market_prices, dtype=float)
        if len(market) == 0:
            raise ValueError("market_prices must not be empty")

    if raw_oracle_prices is None:
        raw_oracle = delayed_oracle_path(market, config.oracle_delay)
    else:
        raw_oracle = np.asarray(raw_oracle_prices, dtype=float)
        if len(raw_oracle) != len(market):
            raise ValueError("raw_oracle_prices must have the same length as market_prices")

    oracle = twap_path(raw_oracle, config.twap_window) if mechanism == "twap" else raw_oracle
    uncertainty_widths = uncertainty_width_path(raw_oracle, config)

    collateral = account.collateral_eth
    debt = account.debt_usdc
    liquidation_events = []
    rows = []
    first_true_unsafe_step: int | None = None
    first_liquidation_step: int | None = None

    for t, (market_price, oracle_price) in enumerate(zip(market, oracle)):
        current_uncertainty_width = uncertainty_widths[t]
        true_hf = health_factor(
            collateral, market_price, account.liquidation_threshold, debt
        )
        oracle_hf = health_factor(
            collateral, oracle_price, account.liquidation_threshold, debt
        )

        if first_true_unsafe_step is None and true_hf < 1:
            first_true_unsafe_step = t

        price_low = oracle_price * (1.0 - current_uncertainty_width)
        price_high = oracle_price * (1.0 + current_uncertainty_width)
        hf_min = health_factor(
            collateral, price_low, account.liquidation_threshold, debt
        )
        hf_max = health_factor(
            collateral, price_high, account.liquidation_threshold, debt
        )
        uncertainty_intensity = (price_high - price_low) / max(oracle_price, 1e-9)

        zone = Zone.SAFE
        close_cap = 0.0
        should_liquidate = False
        adaptive_components = {
            "unsafe_probability": np.nan,
            "solvency_close_cap": np.nan,
            "user_close_cap": np.nan,
            "adaptive_close_cap": np.nan,
        }

        if mechanism == "fixed" or mechanism == "twap":
            should_liquidate = oracle_hf < 1
            close_cap = config.cap_max if should_liquidate else 0.0
            zone = Zone.LIQUIDATION if should_liquidate else Zone.SAFE

        elif mechanism == "buffer":
            should_liquidate = oracle_hf < config.buffer_threshold
            close_cap = config.cap_max if should_liquidate else 0.0
            zone = Zone.LIQUIDATION if should_liquidate else Zone.SAFE

        elif mechanism == "uspl":
            if hf_min > 1:
                zone = Zone.SAFE
                close_cap = 0.0
            elif hf_max < 1:
                zone = Zone.LIQUIDATION
                close_cap = config.cap_max
            else:
                zone = Zone.UNCERTAIN
                if config.use_adaptive_close_factor:
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
                    close_cap = adaptive_components["adaptive_close_cap"]
                else:
                    close_cap = uncertainty_scaled_close_cap(
                        uncertainty_intensity,
                        config,
                    )
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
                first_liquidation_step = t
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
            false_liquidation = true_hf >= 1
            false_liquidation_loss = user_loss if false_liquidation else 0.0
            liquidation_events.append(t)

        bad_debt = max(0.0, debt - collateral * market_price)

        rows.append(
            {
                "step": t,
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
                "uncertainty_intensity": uncertainty_intensity,
                "uncertainty_width": current_uncertainty_width,
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
    bad_debt_steps = int((path["bad_debt"] > 0).sum())
    liquidation_timing = (
        float(first_liquidation_step - first_true_unsafe_step)
        if first_true_unsafe_step is not None and first_liquidation_step is not None
        else np.nan
    )
    liquidation_delay = (
        max(0.0, liquidation_timing) if not np.isnan(liquidation_timing) else np.nan
    )
    early_liquidation_lead = (
        max(0.0, -liquidation_timing) if not np.isnan(liquidation_timing) else 0.0
    )

    positive_bad_debt = path.loc[path["bad_debt"] > 0, "bad_debt"]
    positive_bad_debt_sorted = positive_bad_debt.sort_values(ascending=False)
    es_count = max(1, int(np.ceil(0.05 * len(path))))
    bad_debt_es95 = (
        float(positive_bad_debt_sorted.head(es_count).mean())
        if len(positive_bad_debt_sorted)
        else 0.0
    )

    metrics = {
        "bad_debt_rate": bad_debt_steps / len(path),
        "max_bad_debt": float(path["bad_debt"].max()),
        "bad_debt_es95": bad_debt_es95,
        "avg_bad_debt": float(positive_bad_debt.mean()) if len(positive_bad_debt) else 0.0,
        "false_liquidation_count": int(path["false_liquidation"].sum()),
        "false_liquidation_loss": float(path["false_liquidation_loss"].sum()),
        "total_user_loss": float(path["user_loss"].sum()),
        "liquidation_count": int(path["liquidated"].sum()),
        "liquidation_timing": liquidation_timing,
        "liquidation_delay": liquidation_delay,
        "early_liquidation_lead": early_liquidation_lead,
        "ending_collateral_eth": float(path["collateral_eth"].iloc[-1]),
        "ending_debt_usdc": float(path["debt_usdc"].iloc[-1]),
    }

    return SimulationResult(
        mechanism=mechanism,
        scenario=scenario,
        path=path,
        metrics=metrics,
    )


def compare_mechanisms(
    scenario: ScenarioName,
    config: SimulationConfig | None = None,
    account: AccountConfig | None = None,
    market_prices: np.ndarray | None = None,
    raw_oracle_prices: np.ndarray | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    mechanisms: list[MechanismName] = ["fixed", "twap", "buffer", "uspl"]
    results = [
        simulate(
            scenario,
            mechanism,
            config,
            account,
            market_prices=market_prices,
            raw_oracle_prices=raw_oracle_prices,
        )
        for mechanism in mechanisms
    ]
    metrics = pd.DataFrame(
        [{"scenario": r.scenario, "mechanism": r.mechanism, **r.metrics} for r in results]
    )
    paths = {r.mechanism: r.path for r in results}
    return metrics, paths
