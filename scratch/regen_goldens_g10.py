"""Regenerate G3, G4, G9 golden files after the G10 PySAM migration.

Mirrors the exact fixtures used by the golden tests so the pinned snapshots
match the new PySAM Cashloan + Utilityrate5 outputs.
"""
import json
import os
import sys
from pathlib import Path
from typing import List

import pandas as pd
import yaml

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gesfeas.finance.models import TariffConfig, BatteryConfig, FinanceInput, BatteryFinanceInput
from gesfeas.finance.engine import run_pv_finance
from gesfeas.finance.battery import run_pv_storage_finance
from gesfeas.input.models import SiteParameters, Location, MountType, ShiftPattern, ConnectionType
from gesfeas.input.parser import parse_consumption_csv
from gesfeas.production.engine import run_production_model
from gesfeas.regulation.models import RegulationConfig
from gesfeas.scenario.engine import compare_scenarios

GOLDEN = ROOT / "tests" / "golden"
FIX = ROOT / "tests" / "fixtures"
CFG = ROOT / "config"


def base_tariff() -> TariffConfig:
    return TariffConfig(
        capex_per_kw=600.0, opex_per_kw_year=10.0, inflation_rate=2.5,
        discount_rate=8.0, lifetime=25, loan_term=10, loan_rate=5.0,
        debt_fraction=70.0, buy_price_kwh=0.12, sell_price_kwh=0.08,
    )


def make_solar_production(annual_kwh: float) -> List[float]:
    daily_shape = [
        0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.05, 0.15, 0.35, 0.55, 0.75, 0.90,
        1.00, 0.95, 0.80, 0.60, 0.40, 0.20, 0.05, 0.00, 0.00, 0.00, 0.00, 0.00,
    ]
    dws = sum(daily_shape)
    daily = annual_kwh / 365.0
    out: List[float] = []
    for _ in range(365):
        for h in range(24):
            out.append(daily_shape[h] * daily / dws)
    return out


def regen_g3():
    inp = FinanceInput(
        system_size_kw=100.0,
        production_series=[150000.0 / 8760] * 8760,
        consumption_series=[100000.0 / 8760] * 8760,
        tariff=base_tariff(),
    )
    res = run_pv_finance(inp)
    (GOLDEN / "g3_reference.json").write_text(res.model_dump_json(indent=4))
    print("g3:", res.model_dump())


def regen_g4():
    battery = BatteryConfig(
        battery_capex_per_kwh=250.0, battery_capacity_kwh=200.0, battery_power_kw=50.0,
        round_trip_efficiency=0.90, battery_degradation_rate=0.02,
        battery_replacement_year=12, battery_replacement_cost_per_kwh=200.0,
    )
    inp = BatteryFinanceInput(
        system_size_kw=100.0,
        production_series=make_solar_production(150_000.0),
        monthly_consumption=[100_000.0 / 12] * 12,
        shift_pattern=ShiftPattern.SINGLE.value,
        tariff=base_tariff(),
        battery=battery,
    )
    res = run_pv_storage_finance(inp)
    (GOLDEN / "g4_reference.json").write_text(res.model_dump_json(indent=4))
    print("g4:", res.model_dump())


def regen_g9():
    consumption_df = parse_consumption_csv(str(FIX / "consumption_valid.csv"))
    weather_df = pd.read_csv(str(FIX / "pvgis_tmy_ankara.csv"), index_col=0, parse_dates=True)
    if weather_df.index.tz is None:
        weather_df.index = weather_df.index.tz_localize("UTC")
    tariff = TariffConfig.from_yaml(str(CFG / "tariffs" / "2026.yaml"))
    battery = BatteryConfig.from_yaml(str(CFG / "tariffs" / "battery_2026.yaml"))
    with open(CFG / "regulation" / "rooftop.yaml", encoding="utf-8") as f:
        reg = RegulationConfig(**yaml.safe_load(f))
    site = SiteParameters(
        location=Location(lat=39.92077, lon=32.85411),
        available_area_m2=1000.0, transformer_capacity_kva=400.0,
        mount_type=MountType.ROOFTOP, shift_pattern=ShiftPattern.SINGLE,
        connection_type=ConnectionType.ON_GRID,
    )
    production = run_production_model(site=site, weather_df=weather_df)
    result = compare_scenarios(
        site=site, consumption_df=consumption_df, production=production,
        tariff_config=tariff, battery_config=battery, regulation_config=reg,
    )
    (GOLDEN / "g9_full_pipeline.json").write_text(result.model_dump_json(indent=4))
    print("g9 recommendation:", result.recommendation)
    print("g9 pv_only npv:", result.pv_only.npv, "pv_storage npv:", result.pv_storage.npv)


if __name__ == "__main__":
    regen_g3()
    regen_g4()
    regen_g9()
    print("\nGoldens regenerated.")
