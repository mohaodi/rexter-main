from fastapi import APIRouter, HTTPException

from app.service.mine_overview_service import overview_payload, facility_payload

router = APIRouter(prefix="/api/mine", tags=["Mine Global Digital Twin"])


@router.get("/overview")
def get_mine_overview():
    return overview_payload()


@router.get("/facilities/{facility_id}")
def get_facility(facility_id: str):
    data = facility_payload(facility_id)
    if not data:
        raise HTTPException(status_code=404, detail="facility not found")
    return data
