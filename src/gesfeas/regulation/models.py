from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class NettingMode(str, Enum):
    HOURLY = "hourly"
    MONTHLY = "monthly"

class GroundMountEligibility(BaseModel):
    industrial_or_agricultural_use: bool = Field(True, description="Industrial or agricultural use flag")
    zoning_status_approved: bool = Field(True, description="Zoning status approved flag")
    eia_approved: bool = Field(True, description="EIA (ÇED) approved flag")

class RegulationConfig(BaseModel):
    max_capacity_kw: float = Field(..., description="Maximum allowed installed capacity in kW")
    transformer_capacity_check_ratio: float = Field(1.0, description="Max system size to transformer capacity ratio")
    self_consumption_ratio_min: float = Field(0.0, description="Minimum required self-consumption ratio (0-1)")
    netting_mode: NettingMode = Field(..., description="Netting mechanism: hourly or monthly")
    hybrid_storage_allowed: bool = Field(..., description="Whether PV+Storage is allowed")
    ground_mount_eligibility: Optional[GroundMountEligibility] = Field(None, description="Checklist for ground mount")

class RegulationResult(BaseModel):
    is_compliant: bool = Field(..., description="True if compliant, False otherwise")
    violations: List[str] = Field(default_factory=list, description="List of rule violations")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")
