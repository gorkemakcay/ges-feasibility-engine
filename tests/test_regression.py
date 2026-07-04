import pytest
import os
import json
import yaml
import pandas as pd
from pathlib import Path
from math import isclose

from gesfeas.input.models import SiteParameters, Location, MountType, ShiftPattern, ConnectionType
from gesfeas.input.parser import parse_consumption_csv
from gesfeas.production.engine import run_production_model
from gesfeas.finance.models import TariffConfig, BatteryConfig
from gesfeas.regulation.models import RegulationConfig
from gesfeas.scenario.engine import compare_scenarios
from gesfeas.scenario.models import ScenarioResult

ROOT_DIR = Path(__file__).parent.parent
GOLDEN_DIR = ROOT_DIR / "tests" / "golden"
FIXTURES_DIR = ROOT_DIR / "tests" / "fixtures"
CONFIG_DIR = ROOT_DIR / "config"

def test_g9_full_pipeline_regression():
    # Load inputs
    csv_path = FIXTURES_DIR / "consumption_valid.csv"
    pvgis_path = FIXTURES_DIR / "pvgis_tmy_ankara.csv"
    tariff_path = CONFIG_DIR / "tariffs" / "2026.yaml"
    battery_path = CONFIG_DIR / "tariffs" / "battery_2026.yaml"
    rooftop_reg_path = CONFIG_DIR / "regulation" / "rooftop.yaml"

    consumption_df = parse_consumption_csv(str(csv_path))
    weather_df = pd.read_csv(str(pvgis_path), index_col=0, parse_dates=True)
    if weather_df.index.tz is None:
        weather_df.index = weather_df.index.tz_localize('UTC')

    tariff_config = TariffConfig.from_yaml(str(tariff_path))
    battery_config = BatteryConfig.from_yaml(str(battery_path))
    
    with open(rooftop_reg_path, "r", encoding="utf-8") as f:
        reg_data = yaml.safe_load(f)
    regulation_config = RegulationConfig(**reg_data)

    site = SiteParameters(
        location=Location(lat=39.92077, lon=32.85411),
        available_area_m2=1000.0,
        transformer_capacity_kva=400.0,
        mount_type=MountType.ROOFTOP,
        shift_pattern=ShiftPattern.SINGLE,
        connection_type=ConnectionType.ON_GRID
    )

    # Run
    production = run_production_model(site=site, weather_df=weather_df)
    result = compare_scenarios(
        site=site,
        consumption_df=consumption_df,
        production=production,
        tariff_config=tariff_config,
        battery_config=battery_config,
        regulation_config=regulation_config
    )

    # Compare with golden
    golden_file = GOLDEN_DIR / "g9_full_pipeline.json"
    with open(golden_file, "r") as f:
        golden_data = json.load(f)
    
    # Assert numeric outputs match within tolerance
    assert result.recommendation == golden_data["recommendation"]
    
    # PV-only assertions
    assert isclose(result.pv_only.capex, golden_data["pv_only"]["capex"], rel_tol=1e-4)
    assert isclose(result.pv_only.npv, golden_data["pv_only"]["npv"], rel_tol=1e-4)
    assert isclose(result.pv_only.lcoe, golden_data["pv_only"]["lcoe"], rel_tol=1e-4)
    
    # PV+Storage assertions
    assert isclose(result.pv_storage.capex, golden_data["pv_storage"]["capex"], rel_tol=1e-4)
    assert isclose(result.pv_storage.npv, golden_data["pv_storage"]["npv"], rel_tol=1e-4)
    assert isclose(result.pv_storage.self_consumption_ratio, golden_data["pv_storage"]["self_consumption_ratio"], rel_tol=1e-4)
    
    # Compliance
    assert result.pv_only_compliance.is_compliant == golden_data["pv_only_compliance"]["is_compliant"]
    assert result.pv_storage_compliance.is_compliant == golden_data["pv_storage_compliance"]["is_compliant"]

def test_regulation_config_regression_rooftop():
    current_path = CONFIG_DIR / "regulation" / "rooftop.yaml"
    golden_path = GOLDEN_DIR / "regulation_rooftop.yaml"
    
    with open(current_path, "r", encoding="utf-8") as f:
        current_data = yaml.safe_load(f)
    with open(golden_path, "r", encoding="utf-8") as f:
        golden_data = yaml.safe_load(f)
        
    assert current_data == golden_data, "Rooftop regulation config drifted from golden snapshot!"

def test_regulation_config_regression_ground_mount():
    current_path = CONFIG_DIR / "regulation" / "ground_mount.yaml"
    golden_path = GOLDEN_DIR / "regulation_ground_mount.yaml"
    
    with open(current_path, "r", encoding="utf-8") as f:
        current_data = yaml.safe_load(f)
    with open(golden_path, "r", encoding="utf-8") as f:
        golden_data = yaml.safe_load(f)
        
    assert current_data == golden_data, "Ground mount regulation config drifted from golden snapshot!"
