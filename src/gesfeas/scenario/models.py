from pydantic import BaseModel
from gesfeas.finance.models import FinanceResult, BatteryFinanceResult
from gesfeas.regulation.models import RegulationResult

class ScenarioResult(BaseModel):
    pv_only: FinanceResult
    pv_storage: BatteryFinanceResult
    pv_only_compliance: RegulationResult
    pv_storage_compliance: RegulationResult
    recommendation: str
    recommendation_rationale: str
