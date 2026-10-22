from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.controller.api import router as api_router
from app.controller.research_simulation_controller import router as research_router
from app.controller.twin_controller import router as twin_router
from app.controller.mine_overview_controller import router as mine_router
from app.controller.scheme_prediction_controller import router as scheme_router
from app.controller.platform_controller import router as platform_router
from app.controller.ai_workbench_controller import router as ai_workbench_router
from app.database.mysql import init_database

app = FastAPI(
    title="CBM Digital Twin V14 - Full Lifecycle Platform",
    description="煤系气全生命周期国自然科研数字孪生平台：矿井全局孪生、Java物理模型解析与仿真、Attention-LSTM+PSO方案预测优选、产能演化预测。",
    version="14.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(twin_router)
app.include_router(research_router)
app.include_router(mine_router)
app.include_router(scheme_router)
app.include_router(platform_router)
app.include_router(ai_workbench_router)


@app.on_event("startup")
def startup():
    init_database()


@app.get("/")
def root():
    return {
        "system": "CBM Digital Twin V14 - NSFC Full Lifecycle Platform",
        "status": "running",
        "research_modules": ["全局孪生", "模拟实时监测", "方案优选", "智能调控建议", "智能诊断", "达标评判", "物理仿真", "数据库"],
        "docs": "/docs",
    }
