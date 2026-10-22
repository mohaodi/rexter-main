
from fastapi import APIRouter

from app.model.twin_model import SimulationRequest
from app.service.twin_service import TwinEngine


router=APIRouter(
    prefix="/api/twin"
)


engine=TwinEngine()


@router.get("/geometry")
def geometry():

    return engine.geometry()



@router.post("/simulate")
def simulate(req:SimulationRequest):

    return {

        "params":req.model_dump(),

        "result":
        engine.simulate(
            req.negativePressure,
            req.days
        )

    }
