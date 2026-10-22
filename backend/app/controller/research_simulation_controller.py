from fastapi import APIRouter, File, HTTPException, UploadFile

from app.database.mysql import list_history, save_simulation
from app.model.twin_model import SimulationRequest
from app.service.model_definition_service import (
    DEFAULT_MODEL_ID,
    delete_uploaded_model,
    list_models,
    parse_definition,
    save_uploaded_java,
)
from app.service.simulation_service import ReducedOrderSimulator

router = APIRouter(prefix="/api/research", tags=["research-simulation"])


@router.get("/models")
def models():
    return {"defaultModelId": DEFAULT_MODEL_ID, "models": list_models()}


@router.post("/models/upload")
async def upload_model(file: UploadFile = File(...)):
    try:
        data = await file.read()
        info = save_uploaded_java(file.filename or "uploaded.java", data)
        return {
            "message": "Java 建模文件已上传并完成静态解析。",
            "model": info,
            "definition": parse_definition(info["id"]),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"上传或解析失败: {exc}") from exc


@router.delete("/models/{model_id}")
def remove_model(model_id: str):
    try:
        delete_uploaded_model(model_id)
        return {"message": "已删除上传模型", "modelId": model_id}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/models/{model_id}/definition")
def model_definition(model_id: str):
    try:
        return parse_definition(model_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/simulate")
def simulate(req: SimulationRequest):
    try:
        engine = ReducedOrderSimulator(req.model_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = engine.run(req.negative_pressure_kpa, req.days)
    result["dbSaved"] = save_simulation(
        req.model_id,
        req.negative_pressure_kpa,
        req.days,
        result,
    )
    return result


@router.get("/history")
def history(limit: int = 20):
    return {"items": list_history(max(1, min(limit, 100)))}
