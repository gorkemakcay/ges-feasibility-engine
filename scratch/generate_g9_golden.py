import sys
import os
import shutil
import json
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gesfeas.input.models import SiteParameters, Location, MountType, ShiftPattern, ConnectionType
from gesfeas.input.parser import parse_consumption_csv
from gesfeas.production.engine import run_production_model
from gesfeas.finance.models import TariffConfig, BatteryConfig
from gesfeas.regulation.models import RegulationConfig
from gesfeas.scenario.engine import compare_scenarios

root_dir = Path(__file__).parent.parent

# Input files
csv_path = root_dir / "tests" / "fixtures" / "consumption_valid.csv"
pvgis_path = root_dir / "tests" / "fixtures" / "pvgis_tmy_ankara.csv"
tariff_path = root_dir / "config" / "tariffs" / "2026.yaml"
battery_path = root_dir / "config" / "tariffs" / "battery_2026.yaml"
rooftop_reg_path = root_dir / "config" / "regulation" / "rooftop.yaml"

# Load inputs
consumption_df = parse_consumption_csv(str(csv_path))
weather_df = pd.read_csv(str(pvgis_path), index_col=0, parse_dates=True)
if weather_df.index.tz is None:
    weather_df.index = weather_df.index.tz_localize('UTC')

import yaml

tariff_config = TariffConfig.from_yaml(str(tariff_path))
battery_config = BatteryConfig.from_yaml(str(battery_path))

with open(rooftop_reg_path, "r", encoding="utf-8") as f:
    reg_data = yaml.safe_load(f)
regulation_config = RegulationConfig(**reg_data)

# Site parameters
site = SiteParameters(
    location=Location(lat=39.92077, lon=32.85411),
    available_area_m2=1000.0,
    transformer_capacity_kva=400.0,
    mount_type=MountType.ROOFTOP,
    shift_pattern=ShiftPattern.SINGLE,
    connection_type=ConnectionType.ON_GRID
)

# Run production
production = run_production_model(site=site, weather_df=weather_df)

# Run scenario
result = compare_scenarios(
    site=site,
    consumption_df=consumption_df,
    production=production,
    tariff_config=tariff_config,
    battery_config=battery_config,
    regulation_config=regulation_config
)

# Write golden file
golden_dir = root_dir / "tests" / "golden"
golden_file = golden_dir / "g9_full_pipeline.json"

with open(golden_file, "w") as f:
    f.write(result.model_dump_json(indent=2))

# Copy regulation configs
shutil.copy(root_dir / "config" / "regulation" / "rooftop.yaml", golden_dir / "regulation_rooftop.yaml")
shutil.copy(root_dir / "config" / "regulation" / "ground_mount.yaml", golden_dir / "regulation_ground_mount.yaml")

print("Generated golden files successfully.")
