from pydantic import BaseModel
from typing import List

class ProductionResult(BaseModel):
    annual_energy_kwh: float
    capacity_factor: float
    system_size_kwp: float
    hourly_production_kwh: List[float]
