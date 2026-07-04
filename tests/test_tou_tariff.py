"""
Tests for G11 Part A — Time-of-use (TOU) tariff support.

Covers:
- TOU vs flat tariff produce different annual_savings for the same gen/load.
- A period-heavy load (more consumption in the expensive period) values energy
  differently than the same total energy concentrated in the cheap period.
- TariffConfig validates that tou_periods.hours partition 0-23 exactly once.
- The shipped config/tariffs/2026_try.yaml loads with currency + tou_periods.
"""

import pytest

from gesfeas.finance.models import FinanceInput, TariffConfig, TOUPeriod
from gesfeas.finance.engine import run_pv_finance


@pytest.fixture
def base_tariff_kwargs():
    return dict(
        capex_per_kw=600.0,
        opex_per_kw_year=10.0,
        inflation_rate=2.5,
        discount_rate=8.0,
        lifetime=25,
        loan_term=10,
        loan_rate=5.0,
        debt_fraction=70.0,
        currency="TRY",
    )


@pytest.fixture
def tou_periods():
    # Two 12-hour periods: cheap "gunduz" (0-11) and expensive "puant" (12-23).
    return [
        TOUPeriod(name="gunduz", hours=list(range(0, 12)), buy_price_kwh=1.0, sell_price_kwh=0.5),
        TOUPeriod(name="puant", hours=list(range(12, 24)), buy_price_kwh=5.0, sell_price_kwh=0.5),
    ]


def _flat_series(hourly_by_hour_of_day):
    """Repeat a 24-value hour-of-day pattern across all 365 days -> 8760 values."""
    return hourly_by_hour_of_day * 365


def test_tou_vs_flat_produce_different_savings(base_tariff_kwargs, tou_periods):
    """G11: TOU and an equal-average flat tariff must value the same gen/load differently."""
    # Flat rate = simple average of the two TOU buy rates -> same "average price" story.
    tariff_tou = TariffConfig(**base_tariff_kwargs, buy_price_kwh=3.0, sell_price_kwh=0.5, tou_periods=tou_periods)
    tariff_flat = tariff_tou.model_copy(update={"tou_periods": None})

    gen = _flat_series([5.0] * 24)
    # Peak-heavy load: light during cheap "gunduz" hours, heavy during expensive "puant" hours.
    load = _flat_series([2.0] * 12 + [10.0] * 12)

    inp_tou = FinanceInput(system_size_kw=100.0, production_series=gen, consumption_series=load, tariff=tariff_tou)
    inp_flat = FinanceInput(system_size_kw=100.0, production_series=gen, consumption_series=load, tariff=tariff_flat)

    res_tou = run_pv_finance(inp_tou)
    res_flat = run_pv_finance(inp_flat)

    assert res_tou.annual_savings != pytest.approx(res_flat.annual_savings, rel=1e-3)


def test_period_heavy_load_changes_value_under_tou(base_tariff_kwargs, tou_periods):
    """G11: shifting the SAME total load between cheap and expensive TOU periods must
    change the valued savings — proves ur_ec_tou_mat/schedules are actually applied
    per-hour, not just as an average."""
    tariff_tou = TariffConfig(**base_tariff_kwargs, buy_price_kwh=3.0, sell_price_kwh=0.5, tou_periods=tou_periods)

    gen = _flat_series([5.0] * 24)
    peak_heavy_load = _flat_series([2.0] * 12 + [10.0] * 12)   # heavy in expensive "puant"
    day_heavy_load = _flat_series([10.0] * 12 + [2.0] * 12)     # heavy in cheap "gunduz" (same daily total)

    res_peak_heavy = run_pv_finance(
        FinanceInput(system_size_kw=100.0, production_series=gen, consumption_series=peak_heavy_load, tariff=tariff_tou)
    )
    res_day_heavy = run_pv_finance(
        FinanceInput(system_size_kw=100.0, production_series=gen, consumption_series=day_heavy_load, tariff=tariff_tou)
    )

    assert res_peak_heavy.annual_savings != pytest.approx(res_day_heavy.annual_savings, rel=1e-3)


def test_tou_periods_must_partition_0_23():
    """TariffConfig must reject tou_periods whose hours don't exactly cover 0-23 once."""
    with pytest.raises(ValueError):
        TariffConfig(
            capex_per_kw=600.0, opex_per_kw_year=10.0, inflation_rate=2.5, discount_rate=8.0,
            lifetime=25, loan_term=10, loan_rate=5.0, debt_fraction=70.0,
            buy_price_kwh=3.0, sell_price_kwh=0.5, currency="TRY",
            tou_periods=[
                TOUPeriod(name="gunduz", hours=list(range(0, 12)), buy_price_kwh=1.0, sell_price_kwh=0.5),
                # missing hours 12-23 -> invalid partition
            ],
        )


def test_try_config_loads_with_tou_and_currency():
    """The shipped TRY config must load with currency=TRY and a valid 3-period TOU schedule."""
    tariff = TariffConfig.from_yaml("config/tariffs/2026_try.yaml")
    assert tariff.currency == "TRY"
    assert tariff.tou_periods is not None
    assert len(tariff.tou_periods) == 3
    all_hours = sorted(h for p in tariff.tou_periods for h in p.hours)
    assert all_hours == list(range(24))
