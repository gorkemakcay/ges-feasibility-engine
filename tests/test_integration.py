import pytest
import math
import yaml
import pandas as pd
from pathlib import Path

from gesfeas.input.models import SiteParameters, Location, MountType, ShiftPattern, ConnectionType
from gesfeas.input.parser import parse_consumption_csv
from gesfeas.production.engine import run_production_model
from gesfeas.production.models import ProductionResult
from gesfeas.finance.engine import run_pv_finance
from gesfeas.finance.battery import run_pv_storage_finance
from gesfeas.finance.models import TariffConfig, BatteryConfig, FinanceResult, BatteryFinanceResult, FinanceInput, BatteryFinanceInput
from gesfeas.regulation.engine import evaluate_compliance
from gesfeas.regulation.models import RegulationConfig, RegulationResult
from gesfeas.scenario.engine import compare_scenarios
from gesfeas.scenario.models import ScenarioResult

ROOT_DIR = Path(__file__).parent.parent

def test_cross_module_integration():
    """
    Test the complete chain: parse CSV → run production → run PV-only finance → 
    run PV+Storage finance → run regulation check → run scenario comparison.
    Assert type correctness at each stage boundary and no NaN/null values leak.
    """
    csv_path = ROOT_DIR / "tests" / "fixtures" / "consumption_valid.csv"
    pvgis_path = ROOT_DIR / "tests" / "fixtures" / "pvgis_tmy_ankara.csv"
    tariff_path = ROOT_DIR / "config" / "tariffs" / "2026.yaml"
    battery_path = ROOT_DIR / "config" / "tariffs" / "battery_2026.yaml"
    rooftop_reg_path = ROOT_DIR / "config" / "regulation" / "rooftop.yaml"
    
    # 1. Parse CSV
    consumption_df = parse_consumption_csv(str(csv_path))
    assert isinstance(consumption_df, pd.DataFrame)
    assert not consumption_df.isnull().values.any()
    
    # Setup Site
    site = SiteParameters(
        location=Location(lat=39.92077, lon=32.85411),
        available_area_m2=1000.0,
        transformer_capacity_kva=400.0,
        mount_type=MountType.ROOFTOP,
        shift_pattern=ShiftPattern.SINGLE,
        connection_type=ConnectionType.ON_GRID
    )
    
    # 2. Run Production
    weather_df = pd.read_csv(str(pvgis_path), index_col=0, parse_dates=True)
    if weather_df.index.tz is None:
        weather_df.index = weather_df.index.tz_localize('UTC')
        
    production = run_production_model(site=site, weather_df=weather_df)
    assert isinstance(production, ProductionResult)
    assert not math.isnan(production.annual_energy_kwh)
    assert not math.isnan(production.capacity_factor)
    assert not any(math.isnan(x) for x in production.hourly_production_kwh)
    
    # Setup Configs
    tariff_config = TariffConfig.from_yaml(str(tariff_path))
    battery_config = BatteryConfig.from_yaml(str(battery_path))
    with open(rooftop_reg_path, "r", encoding="utf-8") as f:
        reg_data = yaml.safe_load(f)
    regulation_config = RegulationConfig(**reg_data)
    
    # 3. Run PV-only finance
    finance_input_pv = FinanceInput(
        system_size_kw=production.system_size_kwp,
        production_series=production.hourly_production_kwh,
        consumption_series=None,
        tariff=tariff_config
    )
    pv_only_result = run_pv_finance(finance_input_pv)
    assert isinstance(pv_only_result, FinanceResult)
    assert not math.isnan(pv_only_result.npv)
    assert not math.isnan(pv_only_result.lcoe)
    assert not math.isnan(pv_only_result.capex)
    
    # 4. Run PV+Storage finance
    pv_storage_input = BatteryFinanceInput(
        system_size_kw=production.system_size_kwp,
        production_series=production.hourly_production_kwh,
        monthly_consumption=consumption_df["consumption_kwh"].tolist(),
        shift_pattern=site.shift_pattern.value,
        tariff=tariff_config,
        battery=battery_config
    )
    pv_storage_result = run_pv_storage_finance(pv_storage_input)
    assert isinstance(pv_storage_result, BatteryFinanceResult)
    assert not math.isnan(pv_storage_result.npv)
    assert not math.isnan(pv_storage_result.self_consumption_ratio)
    
    # 5. Run regulation check
    # Need self consumption for compliance if netting requires it
    pv_only_compliance = evaluate_compliance(
        site=site,
        system_size_kw=production.system_size_kwp,
        self_consumption_ratio=1.0,  # Proxy for test
        regulation_config=regulation_config,
        is_hybrid_storage=False
    )
    assert isinstance(pv_only_compliance, RegulationResult)
    
    pv_storage_compliance = evaluate_compliance(
        site=site,
        system_size_kw=production.system_size_kwp,
        self_consumption_ratio=pv_storage_result.self_consumption_ratio,
        regulation_config=regulation_config,
        is_hybrid_storage=True
    )
    assert isinstance(pv_storage_compliance, RegulationResult)
    
    # 6. Run scenario comparison
    scenario_result = compare_scenarios(
        site=site,
        consumption_df=consumption_df,
        production=production,
        tariff_config=tariff_config,
        battery_config=battery_config,
        regulation_config=regulation_config
    )
    assert isinstance(scenario_result, ScenarioResult)
    assert scenario_result.pv_only is not None
    assert scenario_result.pv_storage is not None
    assert scenario_result.pv_only_compliance is not None
    assert scenario_result.pv_storage_compliance is not None
    assert not math.isnan(scenario_result.pv_only.npv)
    assert not math.isnan(scenario_result.pv_storage.npv)
