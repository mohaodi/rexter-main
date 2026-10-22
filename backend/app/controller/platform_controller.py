from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.database.mysql import database_status, list_schemes
from app.service.realtime_service import (
    assessment,
    control_advice,
    diagnosis,
    generate_tick,
    history,
    seed_history,
    snapshot,
)

router = APIRouter(prefix="/api/platform", tags=["Full Lifecycle Platform"])


class TickRequest(BaseModel):
    lifecycleStage: str = "采中"


class SeedRequest(BaseModel):
    points: int = Field(72, ge=1, le=1000)
    lifecycleStage: str = "采中"


@router.get("/database/status")
def db_status():
    try:
        return database_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {exc}") from exc


@router.post("/realtime/tick")
def realtime_tick(req: TickRequest):
    return generate_tick(req.lifecycleStage)


@router.get("/realtime/snapshot")
def realtime_snapshot(stage: str = "采中"):
    return snapshot(stage)


@router.get("/realtime/history")
def realtime_history(borehole: str = "W1", limit: int = 120):
    return history(borehole, max(1, min(limit, 1000)))


@router.post("/realtime/seed")
def realtime_seed(req: SeedRequest):
    return seed_history(req.points, req.lifecycleStage)


@router.get("/diagnosis")
def get_diagnosis():
    return diagnosis()


@router.get("/assessment")
def get_assessment():
    return assessment()


@router.post("/control/advice")
def get_control_advice():
    return control_advice()


@router.get("/schemes")
def schemes(limit: int = 20):
    return {"items": list_schemes(max(1, min(limit, 100)))}
