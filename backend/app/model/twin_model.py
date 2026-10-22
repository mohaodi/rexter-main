from typing import Literal
from pydantic import BaseModel, Field


class SimulationRequest(BaseModel):
    model_id: str = "BigDataFixed_120d_AutoInit"
    negative_pressure_kpa: float = Field(default=20.0, ge=0.0, le=95.0)
    days: int = Field(default=120, ge=1, le=120)
    mode: Literal["constant"] = "constant"
