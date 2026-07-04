import yaml
from pydantic import BaseModel, Field
from typing import List, Optional

class TariffConfig(BaseModel):
    capex_per_kw: float = Field(..., description="CAPEX per kW installed (USD)")
    opex_per_kw_year: float = Field(..., description="Annual OPEX per kW (USD/year)")
    inflation_rate: float = Field(..., description="Annual inflation rate (%)")
    discount_rate: float = Field(..., description="Nominal discount rate (%)")
    lifetime: int = Field(25, description="Project lifetime in years")
    loan_term: int = Field(10, description="Loan term in years")
    loan_rate: float = Field(5.0, description="Loan annual interest rate (%)")
    debt_fraction: float = Field(70.0, description="Debt fraction of CAPEX (%)")
    pv_degradation_rate: float = Field(0.5, description="Annual PV production degradation (%/year)")
    buy_price_kwh: float = Field(..., description="Grid electricity buy price (USD/kWh)")
    sell_price_kwh: float = Field(..., description="Electricity sell price to grid (USD/kWh)")

    @classmethod
    def from_yaml(cls, filepath: str) -> "TariffConfig":
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

class FinanceInput(BaseModel):
    system_size_kw: float
    production_series: List[float]
    consumption_series: Optional[List[float]] = None
    tariff: TariffConfig

class FinanceResult(BaseModel):
    capex: float
    annual_savings: float
    npv: float
    lcoe: float
    simple_payback: float
    discounted_payback: float


class BatteryConfig(BaseModel):
    """Battery storage configuration, loaded from YAML. Config-driven — no hardcoded values."""
    battery_capex_per_kwh: float = Field(..., description="Battery CAPEX (USD/kWh of capacity)")
    battery_capacity_kwh: float = Field(..., description="Total battery energy capacity (kWh)")
    battery_power_kw: float = Field(..., description="Max charge/discharge power (kW)")
    round_trip_efficiency: float = Field(..., ge=0.0, le=1.0, description="Round-trip efficiency (0-1)")
    battery_degradation_rate: float = Field(..., ge=0.0, le=1.0, description="Annual capacity degradation (fraction/year)")
    battery_replacement_year: int = Field(..., gt=0, description="Year when battery is replaced")
    battery_replacement_cost_per_kwh: float = Field(..., ge=0.0, description="Battery replacement cost (USD/kWh)")

    @classmethod
    def from_yaml(cls, filepath: str) -> "BatteryConfig":
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)


class BatteryFinanceInput(BaseModel):
    """Input for PV+Storage financial analysis."""
    system_size_kw: float
    production_series: List[float]          # 8760 hourly PV production (kWh)
    monthly_consumption: List[float]        # 12 monthly consumption totals (kWh)
    shift_pattern: str                      # ShiftPattern enum value (e.g. "single", "triple")
    tariff: TariffConfig
    battery: BatteryConfig


class BatteryFinanceResult(FinanceResult):
    """Financial results for PV+Storage scenario. Extends PV-only FinanceResult."""
    self_consumption_ratio: float = Field(..., description="Fraction of PV production self-consumed on-site")
    grid_export_ratio: float = Field(..., description="Fraction of PV production exported to grid")
    battery_cycles_year1: float = Field(..., description="Number of full battery cycles in year 1")
