from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.service.scheme_prediction_service import (
    forward_scheme,
    model_status,
    predict_productivity,
    recommend_scheme,
)

router = APIRouter(prefix="/api/scheme", tags=["Scheme Prediction"])


class SchemeInverseRequest(BaseModel):
    pressuresPa: List[float] = Field(..., min_length=5, max_length=5)
    swarmSize: int = 48
    maxIter: int = 45
    seed: int = 42
    lifecycleStage: str = "采前"
    boreholeCount: int = Field(3, ge=1, le=9)
    inclinationDeg: float = Field(20.0, ge=5, le=45)
    spacingM: float = Field(30.0, ge=10, le=50)
    lengthM: float = Field(120.0, ge=40, le=260)


class SchemeForwardRequest(BaseModel):
    correctionCoefficient: float
    reservoirGasPressureMPa: float
    extractionPressureKPa: float
    permeabilityMd: float
    excavationDistanceM: float


class ProductivityRequest(BaseModel):
    startDay: int = 1501
    endDay: int = 1800
    modelType: str = "hybrid"


@router.get("/status")
def status():
    try:
        return model_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/recommend")
def recommend(req: SchemeInverseRequest):
    try:
        return recommend_scheme(
            req.pressuresPa,
            req.swarmSize,
            req.maxIter,
            req.seed,
            req.lifecycleStage,
            req.boreholeCount,
            req.inclinationDeg,
            req.spacingM,
            req.lengthM,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/forward")
def forward(req: SchemeForwardRequest):
    try:
        params = [
            req.correctionCoefficient,
            req.reservoirGasPressureMPa,
            req.extractionPressureKPa,
            req.permeabilityMd,
            req.excavationDistanceM,
        ]
        return forward_scheme(params)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/productivity")
def productivity(req: ProductivityRequest):
    try:
        return predict_productivity(req.startDay, req.endDay, req.modelType)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
