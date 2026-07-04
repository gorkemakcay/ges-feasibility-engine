"""
Tests for G4 — Battery / PV+Storage scenario.

Covers:
- Golden-file regression test
- Shift-pattern impact test (single vs triple)
- Config-driven test (battery CAPEX change)
- Load-profile generation validation
- BatteryFinanceResult field completeness
"""

import datetime
import json
import math
import os
from typing import List

import pytest

from gesfeas.finance.models import (
    BatteryConfig,
    BatteryFinanceInput,
    BatteryFinanceResult,
    TariffConfig,
)
from gesfeas.finance.battery import (
    generate_hourly_load_profile,
    run_pv_storage_finance,
)
from gesfeas.input.models import ShiftPattern


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_solar_production(annual_kwh: float) -> List[float]:
    """Create a realistic solar-shaped 8760 production profile.

    Zero at night, sinusoidal peak at noon.  Same daily shape × 365 days.
    """
    # Hourly weights for a typical day (0 = midnight, 12 = noon)
    daily_shape = [
        0.00, 0.00, 0.00, 0.00, 0.00, 0.00,   # 00-05: night
        0.05, 0.15, 0.35, 0.55, 0.75, 0.90,    # 06-11: morning ramp
        1.00, 0.95, 0.80, 0.60, 0.40, 0.20,    # 12-17: afternoon decline
        0.05, 0.00, 0.00, 0.00, 0.00, 0.00,    # 18-23: evening / night
    ]
    daily_weight_sum = sum(daily_shape)
    daily_production = annual_kwh / 365.0

    production: List[float] = []
    for _ in range(365):
        for hour in range(24):
            production.append(
                daily_shape[hour] * daily_production / daily_weight_sum
            )
    return production


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_tariff():
    return TariffConfig(
        capex_per_kw=600.0,
        opex_per_kw_year=10.0,
        inflation_rate=2.5,
        discount_rate=8.0,
        lifetime=25,
        loan_term=10,
        loan_rate=5.0,
        debt_fraction=70.0,
        buy_price_kwh=0.12,
        sell_price_kwh=0.08,
    )


@pytest.fixture
def base_battery():
    return BatteryConfig(
        battery_capex_per_kwh=250.0,
        battery_capacity_kwh=200.0,
        battery_power_kw=50.0,
        round_trip_efficiency=0.90,
        battery_degradation_rate=0.02,
        battery_replacement_year=12,
        battery_replacement_cost_per_kwh=200.0,
    )


@pytest.fixture
def solar_production():
    """100 kW system producing ~150 000 kWh/yr with realistic solar curve."""
    return _make_solar_production(150_000.0)


@pytest.fixture
def monthly_consumption():
    """~100 000 kWh/yr evenly split across 12 months."""
    return [100_000.0 / 12] * 12


@pytest.fixture
def base_battery_input(base_tariff, base_battery, solar_production, monthly_consumption):
    """Standard PV+Storage input for golden-file test."""
    return BatteryFinanceInput(
        system_size_kw=100.0,
        production_series=solar_production,
        monthly_consumption=monthly_consumption,
        shift_pattern=ShiftPattern.SINGLE.value,
        tariff=base_tariff,
        battery=base_battery,
    )


# ---------------------------------------------------------------------------
# Golden-file test
# ---------------------------------------------------------------------------

def test_battery_golden_file(base_battery_input):
    """Pin PV+Storage outputs for a fixed reference case (g4_reference.json)."""
    result = run_pv_storage_finance(base_battery_input)

    golden_path = os.path.join(
        os.path.dirname(__file__), "golden", "g4_reference.json"
    )

    # Golden must exist and match — no self-healing auto-write (drift must fail loudly).
    assert os.path.exists(golden_path), (
        "g4_reference.json is missing. Regenerate it deliberately via "
        "scratch/regen_goldens_g10.py and review the change."
    )

    with open(golden_path, "r") as f:
        golden = json.load(f)

    assert result.capex == pytest.approx(golden["capex"], rel=1e-3)
    assert result.annual_savings == pytest.approx(golden["annual_savings"], rel=1e-3)
    assert result.npv == pytest.approx(golden["npv"], rel=1e-3)
    assert result.lcoe == pytest.approx(golden["lcoe"], rel=1e-2)
    assert result.simple_payback == pytest.approx(golden["simple_payback"], rel=1e-2)
    assert result.discounted_payback == pytest.approx(
        golden["discounted_payback"], rel=1e-2
    )
    assert result.self_consumption_ratio == pytest.approx(
        golden["self_consumption_ratio"], rel=1e-3
    )
    assert result.grid_export_ratio == pytest.approx(
        golden["grid_export_ratio"], rel=1e-3
    )
    assert result.battery_cycles_year1 == pytest.approx(
        golden["battery_cycles_year1"], rel=1e-2
    )


# ---------------------------------------------------------------------------
# Shift-pattern impact test
# ---------------------------------------------------------------------------

def test_shift_pattern_impact(base_tariff, base_battery, solar_production, monthly_consumption):
    """Single-shift vs triple-shift: self_consumption and NPV must differ.

    Triple-shift (24 h load) benefits more from storage because nighttime
    load can be served from battery charged during the day.
    """
    single_input = BatteryFinanceInput(
        system_size_kw=100.0,
        production_series=solar_production,
        monthly_consumption=monthly_consumption,
        shift_pattern=ShiftPattern.SINGLE.value,
        tariff=base_tariff,
        battery=base_battery,
    )
    triple_input = BatteryFinanceInput(
        system_size_kw=100.0,
        production_series=solar_production,
        monthly_consumption=monthly_consumption,
        shift_pattern=ShiftPattern.TRIPLE.value,
        tariff=base_tariff,
        battery=base_battery,
    )

    res_single = run_pv_storage_finance(single_input)
    res_triple = run_pv_storage_finance(triple_input)

    # Self-consumption ratios must differ meaningfully
    assert res_single.self_consumption_ratio != pytest.approx(
        res_triple.self_consumption_ratio, abs=0.01
    ), "Single and triple shift should have different self-consumption ratios"

    # NPVs must differ meaningfully
    assert res_single.npv != pytest.approx(
        res_triple.npv, abs=100.0
    ), "Single and triple shift should have different NPVs"

    # Battery should be more utilised under triple shift (nighttime demand)
    assert res_triple.battery_cycles_year1 > res_single.battery_cycles_year1, (
        "Triple shift should have more battery cycles (greater storage utilisation)"
    )


# ---------------------------------------------------------------------------
# Config-driven test
# ---------------------------------------------------------------------------

def test_config_driven_battery(base_battery_input):
    """Changing battery CAPEX in config changes financial outputs — no code change."""
    res_base = run_pv_storage_finance(base_battery_input)

    # Double battery CAPEX
    expensive_battery = base_battery_input.battery.model_copy(
        update={"battery_capex_per_kwh": 500.0}
    )
    expensive_input = base_battery_input.model_copy(
        update={"battery": expensive_battery}
    )
    res_expensive = run_pv_storage_finance(expensive_input)

    # Higher battery CAPEX → higher total CAPEX
    assert res_expensive.capex > res_base.capex

    # Same production + dispatch → same annual savings
    assert res_expensive.annual_savings == pytest.approx(
        res_base.annual_savings, rel=1e-6
    )

    # Higher CAPEX → lower NPV
    assert res_expensive.npv < res_base.npv

    # Higher CAPEX → longer payback
    assert res_expensive.simple_payback > res_base.simple_payback


# ---------------------------------------------------------------------------
# Load-profile generation tests
# ---------------------------------------------------------------------------

def test_load_profile_length():
    """Generated profile must have exactly 8760 entries."""
    monthly = [8000.0] * 12
    profile = generate_hourly_load_profile(monthly, ShiftPattern.SINGLE)
    assert len(profile) == 8760


def test_load_profile_monthly_sums():
    """Each month's hourly values must sum back to the original monthly total."""
    monthly = [
        8000.0, 7500.0, 8200.0, 8100.0, 8500.0, 9000.0,
        9500.0, 9200.0, 8800.0, 8300.0, 7800.0, 7600.0,
    ]
    profile = generate_hourly_load_profile(monthly, ShiftPattern.SINGLE)

    hour_idx = 0
    for m_idx in range(12):
        month = m_idx + 1
        if month == 12:
            days = (datetime.date(2027, 1, 1) - datetime.date(2026, 12, 1)).days
        else:
            days = (
                datetime.date(2026, month + 1, 1) - datetime.date(2026, month, 1)
            ).days
        hours_in_month = days * 24
        month_sum = sum(profile[hour_idx : hour_idx + hours_in_month])
        assert month_sum == pytest.approx(monthly[m_idx], rel=1e-6), (
            f"Month {month}: expected {monthly[m_idx]}, got {month_sum}"
        )
        hour_idx += hours_in_month


def test_load_profile_shift_shapes():
    """Single-shift profile should have larger day/night load ratio than triple."""
    monthly = [10000.0] * 12
    profile_single = generate_hourly_load_profile(monthly, ShiftPattern.SINGLE)
    profile_triple = generate_hourly_load_profile(monthly, ShiftPattern.TRIPLE)

    # Compare ratio of daytime (h 10) vs nighttime (h 2) load on first day
    ratio_single = profile_single[10] / max(profile_single[2], 1e-9)
    ratio_triple = profile_triple[10] / max(profile_triple[2], 1e-9)

    # Single shift must have a much larger day/night ratio
    assert ratio_single > ratio_triple * 2, (
        f"Single ratio ({ratio_single:.2f}) should be >> triple ratio ({ratio_triple:.2f})"
    )


# ---------------------------------------------------------------------------
# Result model completeness
# ---------------------------------------------------------------------------

def test_battery_result_has_all_fields(base_battery_input):
    """BatteryFinanceResult must contain all required metrics with valid ranges."""
    result = run_pv_storage_finance(base_battery_input)

    # Core finance fields (from FinanceResult)
    assert isinstance(result.capex, float)
    assert isinstance(result.annual_savings, float)
    assert isinstance(result.npv, float)
    assert isinstance(result.lcoe, float)
    assert isinstance(result.simple_payback, float)
    assert isinstance(result.discounted_payback, float)

    # Battery-specific fields
    assert isinstance(result.self_consumption_ratio, float)
    assert isinstance(result.grid_export_ratio, float)
    assert isinstance(result.battery_cycles_year1, float)

    # Range sanity checks
    assert 0.0 <= result.self_consumption_ratio <= 1.0
    assert 0.0 <= result.grid_export_ratio <= 1.0
    assert result.self_consumption_ratio + result.grid_export_ratio == pytest.approx(
        1.0, abs=0.01
    )
    assert result.battery_cycles_year1 >= 0.0
    assert result.capex > 0
    assert result.annual_savings > 0


def test_battery_result_is_subclass():
    """BatteryFinanceResult should extend FinanceResult."""
    from gesfeas.finance.models import FinanceResult
    assert issubclass(BatteryFinanceResult, FinanceResult)


# ---------------------------------------------------------------------------
# G10: battery value flows through the financials via the metered net series
# ---------------------------------------------------------------------------

def test_battery_value_flows_through(base_tariff, base_battery, solar_production):
    """PV+Storage must beat PV-only on annual bill savings for a night-heavy load.

    The dispatch feeds its post-dispatch metered output (effective_gen) into
    Utilityrate5 instead of the raw load, so storage that shifts daytime PV
    (otherwise exported at the low sell price) to nighttime load (offsetting the
    high buy price) increases the valued savings.
    """
    from gesfeas.finance.battery import generate_hourly_load_profile
    from gesfeas.finance.engine import run_pv_finance
    from gesfeas.finance.models import FinanceInput

    monthly = [100_000.0 / 12] * 12

    storage = run_pv_storage_finance(
        BatteryFinanceInput(
            system_size_kw=100.0,
            production_series=solar_production,
            monthly_consumption=monthly,
            shift_pattern=ShiftPattern.TRIPLE.value,  # 24h / night-heavy load
            tariff=base_tariff,
            battery=base_battery,
        )
    )

    # PV-only baseline on the SAME hourly load the dispatch used.
    hourly_load = generate_hourly_load_profile(monthly, ShiftPattern.TRIPLE)
    pv_only = run_pv_finance(
        FinanceInput(
            system_size_kw=100.0,
            production_series=solar_production,
            consumption_series=hourly_load,
            tariff=base_tariff,
        )
    )

    # Battery shifts export→self-consumption, raising the valued annual savings.
    assert storage.annual_savings > pv_only.annual_savings
