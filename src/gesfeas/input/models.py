from enum import Enum
from pydantic import BaseModel, Field

class MountType(str, Enum):
    ROOFTOP = "rooftop"
    GROUND = "ground"

class ShiftPattern(str, Enum):
    SINGLE = "single"
    DOUBLE = "double"
    TRIPLE = "triple"
    WEEKEND_CLOSED = "weekend_closed"

class ConnectionType(str, Enum):
    ON_GRID = "on_grid"
    SELF_CONSUMPTION_LIMITED = "self_consumption_limited"

class Location(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")

class SiteParameters(BaseModel):
    location: Location
    available_area_m2: float = Field(..., gt=0, description="Available roof or land area in square meters")
    transformer_capacity_kva: float = Field(..., gt=0, description="Transformer capacity in kVA")
    mount_type: MountType
    shift_pattern: ShiftPattern
    connection_type: ConnectionType
