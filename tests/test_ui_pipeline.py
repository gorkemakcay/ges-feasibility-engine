import os
import yaml
import tempfile
import pandas as pd
from unittest.mock import patch

def test_app_main_import():
    # Smoke test: imports app/main.py without errors
    # To avoid Streamlit execution context errors when just importing, 
    # we patch sys.argv or just rely on the fact that streamlit scripts 
    # run from top to bottom.
    import app.main
    assert True

def test_ui_pipeline():
    # Integration test that programmatically calls the same pipeline the UI would call
    from gesfeas.input.parser import parse_consumption_csv
    from gesfeas.input.models import SiteParameters, Location, MountType, ShiftPattern, ConnectionType
    from gesfeas.production.engine import run_production_model
    from gesfeas.finance.models import TariffConfig, BatteryConfig
    from gesfeas.regulation.models import RegulationConfig
    from gesfeas.scenario.engine import compare_scenarios
    from gesfeas.report.generator import generate_full_report

    # 1. Input
    csv_path = "tests/fixtures/consumption_valid.csv"
    consumption_df = parse_consumption_csv(csv_path)

    site = SiteParameters(
        location=Location(lat=39.9, lon=32.8),
        available_area_m2=1000.0,
        transformer_capacity_kva=400.0,
        mount_type=MountType.ROOFTOP,
        shift_pattern=ShiftPattern.SINGLE,
        connection_type=ConnectionType.ON_GRID
    )

    # 2. Config
    tariff_config = TariffConfig.from_yaml("config/tariffs/2026.yaml")
    battery_config = BatteryConfig.from_yaml("config/tariffs/battery_2026.yaml")
    
    with open("config/regulation/rooftop.yaml", "r", encoding="utf-8") as f:
        reg_data = yaml.safe_load(f)
    reg_config = RegulationConfig(**reg_data)

    # 3. Production
    # Use mock or actual. The existing tests might hit PVGIS or use mock.
    # To make it robust offline, we can mock the fetch_pvgis_tmy if needed, 
    # but G8 says "assert the full pipeline succeeds end-to-end", so we can just run it.
    
    # We will use the weather_df fixture if we don't want to hit network, 
    # but run_production_model has an optional weather_df arg.
    # Let's see if we have an offline weather data
    import json
    
    weather_df = None
    try:
        weather_df = pd.read_csv("tests/fixtures/pvgis_tmy_ankara.csv", index_col=0, parse_dates=True)
    except Exception:
        pass
        
    production = run_production_model(site, system_size_kwp=100.0, weather_df=weather_df)

    # 4. Scenario Comparison
    scenario_result = compare_scenarios(
        site=site,
        consumption_df=consumption_df,
        production=production,
        tariff_config=tariff_config,
        battery_config=battery_config,
        regulation_config=reg_config,
        ground_mount_flags=None
    )
    
    # 5. Report
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        report_path = tmp.name
        
    try:
        generate_full_report(scenario_result, site, consumption_df, production, report_path)
        assert os.path.exists(report_path)
        assert os.path.getsize(report_path) > 0
    finally:
        if os.path.exists(report_path):
            os.unlink(report_path)
