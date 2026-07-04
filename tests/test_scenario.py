"""
Tests for G6 — Scenario comparison & decision logic.
"""

import pytest
import pandas as pd
from typing import List

from gesfeas.input.models import SiteParameters, Location, MountType, ShiftPattern, ConnectionType
from gesfeas.production.models import ProductionResult
from gesfeas.finance.models import TariffConfig, BatteryConfig
from gesfeas.regulation.models import RegulationConfig, NettingMode, GroundMountEligibility
from gesfeas.scenario.engine import compare_scenarios
from gesfeas.scenario.models import ScenarioResult

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
def base_regulation():
    return RegulationConfig(
        max_capacity_kw=1000.0,
        transformer_capacity_check_ratio=1.0,
        self_consumption_ratio_min=0.0,
        netting_mode=NettingMode.HOURLY,
        hybrid_storage_allowed=True,
        ground_mount_eligibility=None
    )

@pytest.fixture
def solar_production():
    """100 kW system producing ~150 000 kWh/yr with realistic solar curve."""
    annual_kwh = 150_000.0
    daily_shape = [
        0.00, 0.00, 0.00, 0.00, 0.00, 0.00,
        0.05, 0.15, 0.35, 0.55, 0.75, 0.90,
        1.00, 0.95, 0.80, 0.60, 0.40, 0.20,
        0.05, 0.00, 0.00, 0.00, 0.00, 0.00,
    ]
    daily_weight_sum = sum(daily_shape)
    daily_production = annual_kwh / 365.0

    production: List[float] = []
    for _ in range(365):
        for hour in range(24):
            production.append(daily_shape[hour] * daily_production / daily_weight_sum)
            
    return ProductionResult(
        annual_energy_kwh=annual_kwh,
        capacity_factor=annual_kwh / (100.0 * 8760),
        system_size_kwp=100.0,
        hourly_production_kwh=production
    )

@pytest.fixture
def site_base():
    return SiteParameters(
        location=Location(lat=39.92, lon=32.85),
        available_area_m2=1000.0,
        transformer_capacity_kva=400.0,
        mount_type=MountType.ROOFTOP,
        shift_pattern=ShiftPattern.SINGLE,
        connection_type=ConnectionType.ON_GRID
    )

@pytest.fixture
def consumption_df():
    """~100 000 kWh/yr evenly split across 12 months."""
    return pd.DataFrame({"month": list(range(1, 13)), "consumption_kwh": [100_000.0 / 12] * 12}).set_index("month")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_compare_scenarios_end_to_end(site_base, consumption_df, solar_production, base_tariff, base_battery, base_regulation):
    """End-to-end integration test using fixture data."""
    result = compare_scenarios(
        site=site_base,
        consumption_df=consumption_df,
        production=solar_production,
        tariff_config=base_tariff,
        battery_config=base_battery,
        regulation_config=base_regulation
    )
    
    assert isinstance(result, ScenarioResult)
    assert result.pv_only is not None
    assert result.pv_storage is not None
    assert result.pv_only_compliance.is_compliant is True
    assert result.pv_storage_compliance.is_compliant is True
    assert result.recommendation in ["PV-only", "PV+Storage"]
    assert len(result.recommendation_rationale) > 0


def test_hybrid_storage_not_allowed(site_base, consumption_df, solar_production, base_tariff, base_battery, base_regulation):
    """Test that when hybrid storage is not allowed by regulation, recommendation is PV-only."""
    # Disallow hybrid storage
    reg_config = base_regulation.model_copy(update={"hybrid_storage_allowed": False})
    
    # Make battery extremely cheap so NPV of PV+Storage is much better financially
    cheap_battery = base_battery.model_copy(update={"battery_capex_per_kwh": 10.0})
    
    result = compare_scenarios(
        site=site_base,
        consumption_df=consumption_df,
        production=solar_production,
        tariff_config=base_tariff,
        battery_config=cheap_battery,
        regulation_config=reg_config
    )
    
    # PV+Storage should be non-compliant
    assert result.pv_storage_compliance.is_compliant is False
    assert result.pv_only_compliance.is_compliant is True
    
    # Recommendation must be PV-only despite financial superiority
    assert result.recommendation == "PV-only"
    assert "not compliant" in result.recommendation_rationale


def test_triple_shift_recommends_pv_only(site_base, consumption_df, solar_production, base_tariff, base_battery, base_regulation):
    """Test that for a high self-consumption facility (triple shift), PV-only may be recommended."""
    site_triple = site_base.model_copy(update={"shift_pattern": ShiftPattern.TRIPLE})
    
    # Make battery expensive to ensure PV-only is better
    exp_battery = base_battery.model_copy(update={"battery_capex_per_kwh": 500.0, "battery_replacement_cost_per_kwh": 500.0})
    
    result = compare_scenarios(
        site=site_triple,
        consumption_df=consumption_df,
        production=solar_production,
        tariff_config=base_tariff,
        battery_config=exp_battery,
        regulation_config=base_regulation
    )
    
    # PV-only should have a better NPV because storage is expensive and not strictly needed for self-consumption
    assert result.pv_only.npv >= result.pv_storage.npv
    assert result.recommendation == "PV-only"


def test_single_shift_recommends_pv_storage(site_base, consumption_df, solar_production, base_tariff, base_battery, base_regulation):
    """Test that for a single-shift facility, PV+Storage is recommended if battery is reasonably priced."""
    site_single = site_base.model_copy(update={"shift_pattern": ShiftPattern.SINGLE})
    
    # Make grid buy price high, sell price very low (high value for storage)
    # Make battery cheap
    tariff = base_tariff.model_copy(update={"buy_price_kwh": 0.20, "sell_price_kwh": 0.02})
    cheap_battery = base_battery.model_copy(update={"battery_capex_per_kwh": 50.0, "battery_replacement_cost_per_kwh": 50.0})
    
    result = compare_scenarios(
        site=site_single,
        consumption_df=consumption_df,
        production=solar_production,
        tariff_config=tariff,
        battery_config=cheap_battery,
        regulation_config=base_regulation
    )
    
    # PV+Storage should have a better NPV due to cheap battery and high buy/sell spread
    assert result.pv_storage.npv > result.pv_only.npv
    assert result.recommendation == "PV+Storage"


def test_netting_mode_wired_from_regulation_to_finance(
    site_base, consumption_df, solar_production, base_tariff, base_battery, base_regulation
):
    """G11 Part B: compare_scenarios must thread regulation_config.netting_mode into the
    finance calls. Pre-G11, scenario/engine.py called run_pv_finance/run_pv_storage_finance
    without netting_mode, so the regulatory regime (RegulationConfig.netting_mode) was a
    no-op — this test fails against that bug and passes once it's wired.

    Uses a night-heavy load (TRIPLE shift) against day-only solar production so hourly net
    billing (per-timestep) and monthly net metering (rollover) value the same production
    differently — see the equivalent finance-level test, test_netting_mode_affects_savings.
    """
    site_triple = site_base.model_copy(update={"shift_pattern": ShiftPattern.TRIPLE})

    reg_hourly = base_regulation.model_copy(update={"netting_mode": NettingMode.HOURLY})
    reg_monthly = base_regulation.model_copy(update={"netting_mode": NettingMode.MONTHLY})

    result_hourly = compare_scenarios(
        site=site_triple, consumption_df=consumption_df, production=solar_production,
        tariff_config=base_tariff, battery_config=base_battery, regulation_config=reg_hourly,
    )
    result_monthly = compare_scenarios(
        site=site_triple, consumption_df=consumption_df, production=solar_production,
        tariff_config=base_tariff, battery_config=base_battery, regulation_config=reg_monthly,
    )

    assert result_hourly.pv_only.annual_savings != pytest.approx(
        result_monthly.pv_only.annual_savings, rel=1e-3
    )
    # Monthly net metering credits daytime exports against nighttime imports at the
    # retail buy rate, so it must be >= per-timestep hourly net billing.
    assert result_monthly.pv_only.annual_savings >= result_hourly.pv_only.annual_savings

