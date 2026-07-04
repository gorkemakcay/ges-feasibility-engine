import pytest
import math
import pandas as pd
from pathlib import Path

from gesfeas.input.models import SiteParameters, Location, MountType, ShiftPattern, ConnectionType
from gesfeas.finance.engine import run_pv_finance
from gesfeas.finance.battery import run_pv_storage_finance
from gesfeas.finance.models import TariffConfig, BatteryConfig, FinanceInput, BatteryFinanceInput
from gesfeas.production.engine import run_production_model
from gesfeas.production.models import ProductionResult
from gesfeas.regulation.models import RegulationConfig, NettingMode

ROOT_DIR = Path(__file__).parent.parent

@pytest.fixture
def base_tariff():
    return TariffConfig.from_yaml(str(ROOT_DIR / "config" / "tariffs" / "2026.yaml"))

@pytest.fixture
def base_battery():
    return BatteryConfig.from_yaml(str(ROOT_DIR / "config" / "tariffs" / "battery_2026.yaml"))

@pytest.fixture
def base_site():
    return SiteParameters(
        location=Location(lat=39.92077, lon=32.85411),
        available_area_m2=1000.0,
        transformer_capacity_kva=400.0,
        mount_type=MountType.ROOFTOP,
        shift_pattern=ShiftPattern.SINGLE,
        connection_type=ConnectionType.ON_GRID
    )

@pytest.fixture
def ankara_weather():
    pvgis_path = ROOT_DIR / "tests" / "fixtures" / "pvgis_tmy_ankara.csv"
    weather_df = pd.read_csv(str(pvgis_path), index_col=0, parse_dates=True)
    if weather_df.index.tz is None:
        weather_df.index = weather_df.index.tz_localize('UTC')
    return weather_df

def test_sanity_doubling_system_size(base_tariff):
    input_100 = FinanceInput(
        system_size_kw=100.0,
        production_series=[150000.0/8760]*8760,
        consumption_series=None,
        tariff=base_tariff
    )
    res_100 = run_pv_finance(input_100)
    
    input_200 = FinanceInput(
        system_size_kw=200.0,
        production_series=[300000.0/8760]*8760,
        consumption_series=None,
        tariff=base_tariff
    )
    res_200 = run_pv_finance(input_200)
    
    # CAPEX should exactly double if per_kw logic is linear
    assert math.isclose(res_200.capex, res_100.capex * 2, rel_tol=1e-4)

def test_sanity_zero_consumption(base_site, base_tariff, base_battery, ankara_weather):
    # Setup zero consumption
    zero_consumption_df = pd.DataFrame({
        "month": list(range(1, 13)),
        "consumption_kwh": [0.0] * 12
    }).set_index("month")
    
    production = run_production_model(site=base_site, weather_df=ankara_weather)
    
    pv_storage_input = BatteryFinanceInput(
        system_size_kw=production.system_size_kwp,
        production_series=production.hourly_production_kwh,
        monthly_consumption=[0.0]*12,
        shift_pattern=base_site.shift_pattern.value,
        tariff=base_tariff,
        battery=base_battery
    )
    pv_storage_result = run_pv_storage_finance(pv_storage_input)
    
    # Self consumption ratio must be near 0 if there is 0 consumption (only initial battery charge counts)
    assert math.isclose(pv_storage_result.self_consumption_ratio, 0.0, abs_tol=1e-3)
    # The battery should never discharge because load is always 0
    assert pv_storage_result.battery_cycles_year1 == 0.0

def test_sanity_negative_npv(base_tariff):
    # Set absurdly high CAPEX
    high_capex_tariff = base_tariff.model_copy(update={"capex_per_kw": 50000.0})
    fin_input = FinanceInput(
        system_size_kw=100.0,
        production_series=[150000.0/8760]*8760,
        consumption_series=None,
        tariff=high_capex_tariff
    )
    res = run_pv_finance(fin_input)
    
    assert res.npv < 0
    # Payback should be constrained to lifetime (e.g. 25 years) or very high
    assert res.simple_payback >= base_tariff.lifetime
    assert res.discounted_payback >= base_tariff.lifetime

def test_sanity_higher_irradiance(base_site, ankara_weather):
    prod_ankara = run_production_model(site=base_site, weather_df=ankara_weather)
    
    # Artificially boost irradiance columns by 20%
    high_irr_weather = ankara_weather.copy()
    for col in ["ghi", "dni", "dhi"]:
        if col in high_irr_weather.columns:
            high_irr_weather[col] *= 1.2
            
    prod_high = run_production_model(site=base_site, weather_df=high_irr_weather)
    
    assert prod_high.annual_energy_kwh > prod_ankara.annual_energy_kwh
    assert prod_high.capacity_factor > prod_ankara.capacity_factor
