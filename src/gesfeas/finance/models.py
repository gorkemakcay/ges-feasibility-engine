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
