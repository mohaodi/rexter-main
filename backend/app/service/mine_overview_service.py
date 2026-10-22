from datetime import datetime


FACILITIES = [
    {"id": "main_shaft", "name": "主井", "category": "shaft", "status": "normal", "position": {"x": 0, "y": 0, "z": -4.5}, "description": "主提升井筒，承担煤岩运输与系统联络。"},
    {"id": "aux_shaft", "name": "副井", "category": "shaft", "status": "normal", "position": {"x": 4, "y": 0, "z": -4.5}, "description": "人员、材料运输及辅助进风井筒。"},
    {"id": "vent_shaft", "name": "回风井", "category": "ventilation", "status": "normal", "position": {"x": -7, "y": 0, "z": -4.5}, "description": "矿井回风通道及通风系统关键节点。"},
    {"id": "drainage_station", "name": "煤系气抽采站", "category": "cbm", "status": "normal", "position": {"x": 9, "y": 0, "z": 4}, "description": "煤系气负压抽采、分离计量与汇管节点。"},
    {"id": "monitor_center", "name": "智能监测中心", "category": "monitor", "status": "normal", "position": {"x": 10, "y": 0, "z": -1}, "description": "汇聚负压、浓度、流量、环境及设备运行数据。"},
    {"id": "power_station", "name": "变配电站", "category": "power", "status": "normal", "position": {"x": 6, "y": 0, "z": 6}, "description": "矿区地面设备供配电与状态监测节点。"},
    {"id": "roadway", "name": "运输及回风巷道", "category": "underground", "status": "normal", "position": {"x": 7, "y": -8.8, "z": -4.5}, "description": "井下运输、行人、进风及回风巷道网络。"},
    {
        "id": "five_well_zone",
        "name": "五钻孔抽采试验区",
        "category": "cbm-research",
        "status": "research",
        "position": {"x": 13.1, "y": -8.9, "z": -4.5},
        "description": "国自然项目五钻孔煤系气抽采科研区域。五条钻孔在水平面内平行布置，经井下汇管汇集后接入垂直抽采立管并延伸至地表井口。",
        "engineering": {
            "boreholeCount": 5,
            "boreholeOrientation": "水平 X 向（相对 V11 水平旋转 90°）",
            "spacing": "科研全局场景示意等间距；精细尺寸由五钻孔模型/Java模型定义",
            "connection": "五条水平钻孔 → 井下水平汇管 → 垂直抽采立管 → 地表井口",
            "detailMode": "点击科研区后隐藏试验区边界及其他矿井对象，仅保留抽采通道",
        },
    },
]


def overview_payload():
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "system": {
            "name": "煤系气矿井全局数字孪生",
            "status": "online",
            "sceneMode": "surface-underground-integrated",
            "researchLevel": "NSFC multi-scale digital twin",
        },
        "summary": {
            "surfaceFacilities": 6,
            "undergroundSystems": 4,
            "activeDrainageWells": 5,
            "alarms": 0,
        },
        "realtime": {
            "negativePressureKPa": 20.0,
            "methaneConcentrationPct": 86.4,
            "mixedFlowM3Min": 18.7,
            "returnAirMethanePct": 0.42,
        },
        "fiveWellTopology": {
            "horizontalBoreholes": 5,
            "collector": "underground horizontal manifold",
            "verticalRiser": True,
            "surfaceWellhead": True,
        },
        "facilities": FACILITIES,
    }


def facility_payload(facility_id: str):
    for item in FACILITIES:
        if item["id"] == facility_id:
            return item
    return None
