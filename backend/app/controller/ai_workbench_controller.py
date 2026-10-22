from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.service.ai_workbench_service import (
    adapter_status,
    data_quality,
    detect_anomalies,
    forecast_well,
    generate_safe_candidates,
    import_monitor_csv,
    record_review,
    review_history,
)

router = APIRouter(prefix="/api/ai", tags=["AI Decision Workbench"])


class ForecastRequest(BaseModel):
    boreholeCode: str = "W1"
    horizon: int = Field(6, ge=1, le=12)
    samples: int = Field(120, ge=12, le=500)


class AnomalyRequest(BaseModel):
    samples: int = Field(120, ge=12, le=500)


class CandidateRequest(BaseModel):
    pressuresPa: list[float] = Field(..., min_length=5, max_length=5)
    lifecycleStage: str = "采中"
    boreholeCount: int = Field(3, ge=1, le=9)
    inclinationDeg: float = Field(20, ge=5, le=45)
    spacingM: float = Field(30, ge=10, le=50)
    lengthM: float = Field(120, ge=40, le=260)
    pressureMinKPa: float = Field(15, ge=0, le=95)
    pressureMaxKPa: float = Field(35, ge=0, le=95)
    methaneMinPct: float = Field(60, ge=0, le=100)
    flowMinM3Min: float = Field(2, ge=0)
    minFitScorePct: float = Field(80, ge=0, le=100)


class ReviewRequest(BaseModel):
    itemType: Literal["forecast", "anomaly", "plan"]
    itemId: str = Field(..., min_length=1, max_length=128)
    decision: Literal["accepted", "rejected", "adjusted"]
    comment: str = Field("", max_length=1000)
    item: dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
def status():
    try:
        return adapter_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"数据接入状态读取失败: {exc}") from exc


@router.get("/quality")
def quality():
    try:
        return data_quality()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"数据质量检查失败: {exc}") from exc


@router.post("/data/import-csv")
async def import_csv(file: UploadFile = File(...)):
    try:
        payload = await file.read()
        return import_monitor_csv(file.filename or "monitor.csv", payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CSV导入失败: {exc}") from exc


@router.post("/forecast")
def forecast(req: ForecastRequest):
    try:
        return forecast_well(req.boreholeCode, req.horizon, req.samples)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"趋势预测失败: {exc}") from exc


@router.post("/anomalies")
def anomalies(req: AnomalyRequest):
    try:
        return detect_anomalies(req.samples)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"异常筛查失败: {exc}") from exc


@router.post("/plans")
def plans(req: CandidateRequest):
    try:
        return generate_safe_candidates(
            req.pressuresPa, req.lifecycleStage, req.boreholeCount,
            req.inclinationDeg, req.spacingM, req.lengthM,
            req.pressureMinKPa, req.pressureMaxKPa, req.methaneMinPct,
            req.flowMinM3Min, req.minFitScorePct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"安全约束方案筛选失败: {exc}") from exc


@router.post("/shadow-review")
def submit_review(req: ReviewRequest):
    try:
        return record_review(req.itemType, req.itemId, req.decision, req.comment, req.item)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"影子验证记录失败: {exc}") from exc


@router.get("/shadow-review")
def get_reviews(limit: int = 50):
    try:
        return review_history(limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"复核记录读取失败: {exc}") from exc
