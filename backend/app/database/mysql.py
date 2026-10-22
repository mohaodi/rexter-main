from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_SQLITE_PATH = BASE_DIR / "data" / "cbm_twin.db"


def _engine() -> str:
    return os.getenv("CBM_DB_ENGINE", "sqlite").strip().lower()


@contextmanager
def _connect():
    if _engine() == "mysql":
        try:
            import pymysql
        except ImportError as exc:
            raise RuntimeError("MySQL 模式需要安装 pymysql") from exc
        conn = pymysql.connect(
            host=os.getenv("CBM_DB_HOST", "127.0.0.1"),
            port=int(os.getenv("CBM_DB_PORT", "3306")),
            user=os.getenv("CBM_DB_USER", "root"),
            password=os.getenv("CBM_DB_PASSWORD", ""),
            database=os.getenv("CBM_DB_NAME", "cbm_twin"),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    else:
        path = Path(os.getenv("CBM_SQLITE_PATH", str(DEFAULT_SQLITE_PATH))).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def _sql(text: str) -> str:
    return text.replace("%s", "?") if _engine() != "mysql" else text


def _execute(conn, text: str, params=()):
    cur = conn.cursor()
    cur.execute(_sql(text), params)
    return cur


def _rows(cur) -> list[dict]:
    return [dict(row) for row in cur.fetchall()]


def init_database() -> None:
    sqlite_schema = [
        """CREATE TABLE IF NOT EXISTS borehole (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL, spacing_m REAL NOT NULL, inclination_deg REAL NOT NULL,
            azimuth_deg REAL NOT NULL, length_m REAL NOT NULL, enabled INTEGER DEFAULT 1)""",
        """CREATE TABLE IF NOT EXISTS sensor_reading (
            id INTEGER PRIMARY KEY AUTOINCREMENT, recorded_at TEXT NOT NULL,
            borehole_code TEXT NOT NULL, source_type TEXT NOT NULL,
            negative_pressure_kpa REAL NOT NULL, methane_pct REAL NOT NULL,
            mixed_flow_m3_min REAL NOT NULL, pure_flow_m3_min REAL NOT NULL,
            reservoir_pressure_mpa REAL NOT NULL, temperature_c REAL NOT NULL,
            valve_open_pct REAL NOT NULL, pump_power_kw REAL NOT NULL,
            lifecycle_stage TEXT NOT NULL, quality_flag TEXT NOT NULL,
            FOREIGN KEY(borehole_code) REFERENCES borehole(code))""",
        "CREATE INDEX IF NOT EXISTS idx_sensor_time ON sensor_reading(recorded_at)",
        "CREATE INDEX IF NOT EXISTS idx_sensor_well_time ON sensor_reading(borehole_code, recorded_at)",
        """CREATE TABLE IF NOT EXISTS extraction_scheme (
            id INTEGER PRIMARY KEY AUTOINCREMENT, scheme_code TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL, lifecycle_stage TEXT NOT NULL, source_model TEXT NOT NULL,
            target_json TEXT NOT NULL, parameters_json TEXT NOT NULL, metrics_json TEXT NOT NULL,
            status TEXT NOT NULL, approved INTEGER DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS scheme_borehole (
            id INTEGER PRIMARY KEY AUTOINCREMENT, scheme_code TEXT NOT NULL,
            borehole_code TEXT NOT NULL, inclination_deg REAL NOT NULL, azimuth_deg REAL NOT NULL,
            spacing_m REAL NOT NULL, length_m REAL NOT NULL, extraction_pressure_kpa REAL NOT NULL,
            start_x REAL NOT NULL, start_y REAL NOT NULL, start_z REAL NOT NULL,
            end_x REAL NOT NULL, end_y REAL NOT NULL, end_z REAL NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS alarm_event (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
            borehole_code TEXT, level TEXT NOT NULL, alarm_type TEXT NOT NULL,
            message TEXT NOT NULL, status TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS control_advice (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
            lifecycle_stage TEXT NOT NULL, source TEXT NOT NULL, advice_json TEXT NOT NULL,
            safety_checked INTEGER NOT NULL, execution_status TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS assessment_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
            lifecycle_stage TEXT NOT NULL, score REAL NOT NULL,
            compliant INTEGER NOT NULL, details_json TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS simulation_task (
            id INTEGER PRIMARY KEY AUTOINCREMENT, model_id TEXT NOT NULL,
            negative_pressure_kpa REAL NOT NULL, days INTEGER NOT NULL,
            engine TEXT NOT NULL, result_json TEXT NOT NULL, create_time TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS shadow_review (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
            item_type TEXT NOT NULL, item_id TEXT NOT NULL, decision TEXT NOT NULL,
            comment TEXT NOT NULL, item_json TEXT NOT NULL)""",
    ]
    mysql_schema = [
        """CREATE TABLE IF NOT EXISTS borehole (
            id BIGINT PRIMARY KEY AUTO_INCREMENT, code VARCHAR(32) UNIQUE NOT NULL,
            name VARCHAR(128) NOT NULL, spacing_m DOUBLE NOT NULL, inclination_deg DOUBLE NOT NULL,
            azimuth_deg DOUBLE NOT NULL, length_m DOUBLE NOT NULL, enabled TINYINT DEFAULT 1)""",
        """CREATE TABLE IF NOT EXISTS sensor_reading (
            id BIGINT PRIMARY KEY AUTO_INCREMENT, recorded_at VARCHAR(64) NOT NULL,
            borehole_code VARCHAR(32) NOT NULL, source_type VARCHAR(32) NOT NULL,
            negative_pressure_kpa DOUBLE NOT NULL, methane_pct DOUBLE NOT NULL,
            mixed_flow_m3_min DOUBLE NOT NULL, pure_flow_m3_min DOUBLE NOT NULL,
            reservoir_pressure_mpa DOUBLE NOT NULL, temperature_c DOUBLE NOT NULL,
            valve_open_pct DOUBLE NOT NULL, pump_power_kw DOUBLE NOT NULL,
            lifecycle_stage VARCHAR(16) NOT NULL, quality_flag VARCHAR(32) NOT NULL,
            INDEX idx_sensor_time(recorded_at), INDEX idx_sensor_well_time(borehole_code, recorded_at))""",
        """CREATE TABLE IF NOT EXISTS extraction_scheme (
            id BIGINT PRIMARY KEY AUTO_INCREMENT, scheme_code VARCHAR(64) UNIQUE NOT NULL,
            created_at VARCHAR(64) NOT NULL, lifecycle_stage VARCHAR(16) NOT NULL,
            source_model VARCHAR(255) NOT NULL, target_json JSON NOT NULL,
            parameters_json JSON NOT NULL, metrics_json JSON NOT NULL,
            status VARCHAR(32) NOT NULL, approved TINYINT DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS scheme_borehole (
            id BIGINT PRIMARY KEY AUTO_INCREMENT, scheme_code VARCHAR(64) NOT NULL,
            borehole_code VARCHAR(32) NOT NULL, inclination_deg DOUBLE NOT NULL,
            azimuth_deg DOUBLE NOT NULL, spacing_m DOUBLE NOT NULL, length_m DOUBLE NOT NULL,
            extraction_pressure_kpa DOUBLE NOT NULL, start_x DOUBLE NOT NULL, start_y DOUBLE NOT NULL,
            start_z DOUBLE NOT NULL, end_x DOUBLE NOT NULL, end_y DOUBLE NOT NULL, end_z DOUBLE NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS alarm_event (
            id BIGINT PRIMARY KEY AUTO_INCREMENT, created_at VARCHAR(64) NOT NULL,
            borehole_code VARCHAR(32), level VARCHAR(16) NOT NULL, alarm_type VARCHAR(64) NOT NULL,
            message VARCHAR(500) NOT NULL, status VARCHAR(16) NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS control_advice (
            id BIGINT PRIMARY KEY AUTO_INCREMENT, created_at VARCHAR(64) NOT NULL,
            lifecycle_stage VARCHAR(16) NOT NULL, source VARCHAR(64) NOT NULL,
            advice_json JSON NOT NULL, safety_checked TINYINT NOT NULL,
            execution_status VARCHAR(32) NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS assessment_record (
            id BIGINT PRIMARY KEY AUTO_INCREMENT, created_at VARCHAR(64) NOT NULL,
            lifecycle_stage VARCHAR(16) NOT NULL, score DOUBLE NOT NULL,
            compliant TINYINT NOT NULL, details_json JSON NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS simulation_task (
            id BIGINT PRIMARY KEY AUTO_INCREMENT, model_id VARCHAR(128) NOT NULL,
            negative_pressure_kpa DOUBLE NOT NULL, days INT NOT NULL,
            engine VARCHAR(64) NOT NULL, result_json JSON NOT NULL, create_time VARCHAR(64) NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS shadow_review (
            id BIGINT PRIMARY KEY AUTO_INCREMENT, created_at VARCHAR(64) NOT NULL,
            item_type VARCHAR(32) NOT NULL, item_id VARCHAR(128) NOT NULL,
            decision VARCHAR(16) NOT NULL, comment VARCHAR(1000) NOT NULL,
            item_json JSON NOT NULL)""",
    ]
    with _connect() as conn:
        for stmt in mysql_schema if _engine() == "mysql" else sqlite_schema:
            _execute(conn, stmt)
        for i in range(1, 6):
            stmt = (
                """INSERT IGNORE INTO borehole
                (code,name,spacing_m,inclination_deg,azimuth_deg,length_m,enabled)
                VALUES (%s,%s,%s,%s,%s,%s,1)"""
                if _engine() == "mysql"
                else """INSERT OR IGNORE INTO borehole
                (code,name,spacing_m,inclination_deg,azimuth_deg,length_m,enabled)
                VALUES (%s,%s,%s,%s,%s,%s,1)"""
            )
            _execute(conn, stmt, (f"W{i}", f"抽采钻孔{i}", 30.0, 20.0, (i - 3) * 8.0, 120.0))
        conn.commit()


def database_status() -> dict:
    with _connect() as conn:
        count = dict(_execute(conn, "SELECT COUNT(*) AS count FROM sensor_reading").fetchone())["count"]
    return {
        "engine": _engine(),
        "database": os.getenv("CBM_DB_NAME", "cbm_twin") if _engine() == "mysql"
        else str(Path(os.getenv("CBM_SQLITE_PATH", str(DEFAULT_SQLITE_PATH))).resolve()),
        "connected": True,
        "sensorRows": int(count),
    }


def save_sensor_readings(items: Iterable[dict]) -> int:
    rows = list(items)
    if not rows:
        return 0
    stmt = """INSERT INTO sensor_reading
        (recorded_at,borehole_code,source_type,negative_pressure_kpa,methane_pct,
         mixed_flow_m3_min,pure_flow_m3_min,reservoir_pressure_mpa,temperature_c,
         valve_open_pct,pump_power_kw,lifecycle_stage,quality_flag)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    values = [(
        r["recordedAt"], r["boreholeCode"], r["sourceType"], r["negativePressureKPa"],
        r["methanePct"], r["mixedFlowM3Min"], r["pureFlowM3Min"], r["reservoirPressureMPa"],
        r["temperatureC"], r["valveOpenPct"], r["pumpPowerKW"], r["lifecycleStage"], r["qualityFlag"],
    ) for r in rows]
    with _connect() as conn:
        cur = conn.cursor()
        cur.executemany(_sql(stmt), values)
        conn.commit()
    return len(rows)


def latest_sensor_readings() -> list[dict]:
    query = """SELECT s.* FROM sensor_reading s JOIN (
        SELECT borehole_code, MAX(id) max_id FROM sensor_reading GROUP BY borehole_code
    ) x ON s.id=x.max_id ORDER BY s.borehole_code"""
    with _connect() as conn:
        return _rows(_execute(conn, query))


def sensor_history(limit: int = 300, borehole_code: str | None = None) -> list[dict]:
    with _connect() as conn:
        if borehole_code:
            cur = _execute(conn, "SELECT * FROM sensor_reading WHERE borehole_code=%s ORDER BY id DESC LIMIT %s", (borehole_code, limit))
        else:
            cur = _execute(conn, "SELECT * FROM sensor_reading ORDER BY id DESC LIMIT %s", (limit,))
        rows = _rows(cur)
    rows.reverse()
    return rows


def save_scheme(payload: dict) -> str:
    code = payload["schemeCode"]
    with _connect() as conn:
        head = (
            """INSERT INTO extraction_scheme
            (scheme_code,created_at,lifecycle_stage,source_model,target_json,parameters_json,metrics_json,status,approved)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0)
            ON DUPLICATE KEY UPDATE target_json=VALUES(target_json),parameters_json=VALUES(parameters_json),metrics_json=VALUES(metrics_json),status=VALUES(status)"""
            if _engine() == "mysql"
            else """INSERT INTO extraction_scheme
            (scheme_code,created_at,lifecycle_stage,source_model,target_json,parameters_json,metrics_json,status,approved)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0)
            ON CONFLICT(scheme_code) DO UPDATE SET target_json=excluded.target_json,parameters_json=excluded.parameters_json,metrics_json=excluded.metrics_json,status=excluded.status"""
        )
        _execute(conn, head, (
            code, payload["createdAt"], payload["lifecycleStage"], payload["sourceModel"],
            json.dumps(payload["targetPressuresPa"], ensure_ascii=False),
            json.dumps(payload["scheme"], ensure_ascii=False),
            json.dumps(payload["metrics"], ensure_ascii=False), payload["status"],
        ))
        _execute(conn, "DELETE FROM scheme_borehole WHERE scheme_code=%s", (code,))
        for b in payload["boreholes"]:
            _execute(conn, """INSERT INTO scheme_borehole
                (scheme_code,borehole_code,inclination_deg,azimuth_deg,spacing_m,length_m,extraction_pressure_kpa,
                 start_x,start_y,start_z,end_x,end_y,end_z)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (
                code, b["code"], b["inclinationDeg"], b["azimuthDeg"], b["spacingM"], b["lengthM"], b["extractionPressureKPa"],
                b["start"]["x"], b["start"]["y"], b["start"]["z"], b["end"]["x"], b["end"]["y"], b["end"]["z"],
            ))
        conn.commit()
    return code


def list_schemes(limit: int = 20) -> list[dict]:
    with _connect() as conn:
        items = _rows(_execute(conn, "SELECT * FROM extraction_scheme ORDER BY id DESC LIMIT %s", (limit,)))
        for item in items:
            item["boreholes"] = _rows(_execute(conn, "SELECT * FROM scheme_borehole WHERE scheme_code=%s ORDER BY borehole_code", (item["scheme_code"],)))
    return items


def save_alarm(level: str, alarm_type: str, message: str, borehole_code: str | None = None) -> None:
    with _connect() as conn:
        _execute(conn, "INSERT INTO alarm_event (created_at,borehole_code,level,alarm_type,message,status) VALUES (%s,%s,%s,%s,%s,%s)",
                 (_now(), borehole_code, level, alarm_type, message, "open"))
        conn.commit()


def list_alarms(limit: int = 50) -> list[dict]:
    with _connect() as conn:
        return _rows(_execute(conn, "SELECT * FROM alarm_event ORDER BY id DESC LIMIT %s", (limit,)))


def save_control_advice(stage: str, advice: dict) -> None:
    with _connect() as conn:
        _execute(conn, """INSERT INTO control_advice
            (created_at,lifecycle_stage,source,advice_json,safety_checked,execution_status)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (_now(), stage, "rule-constrained-advisory", json.dumps(advice, ensure_ascii=False), 1, "advisory-only"))
        conn.commit()


def save_assessment(stage: str, score: float, compliant: bool, details: dict) -> None:
    with _connect() as conn:
        _execute(conn, """INSERT INTO assessment_record
            (created_at,lifecycle_stage,score,compliant,details_json) VALUES (%s,%s,%s,%s,%s)""",
            (_now(), stage, score, 1 if compliant else 0, json.dumps(details, ensure_ascii=False)))
        conn.commit()


def save_shadow_review(item_type: str, item_id: str, decision: str, comment: str, item: dict) -> dict:
    created_at = _now()
    with _connect() as conn:
        cur = _execute(conn, """INSERT INTO shadow_review
            (created_at,item_type,item_id,decision,comment,item_json)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (created_at, item_type, item_id, decision, comment, json.dumps(item, ensure_ascii=False)))
        review_id = cur.lastrowid
        conn.commit()
    return {
        "id": int(review_id), "createdAt": created_at, "itemType": item_type,
        "itemId": item_id, "decision": decision, "comment": comment,
    }


def list_shadow_reviews(limit: int = 50) -> list[dict]:
    with _connect() as conn:
        rows = _rows(_execute(conn, "SELECT * FROM shadow_review ORDER BY id DESC LIMIT %s", (limit,)))
    for row in rows:
        row["item_json"] = json.loads(row["item_json"])
    return rows


def save_simulation(model_id: str, negative_pressure_kpa: float, days: int, result: dict) -> bool:
    try:
        with _connect() as conn:
            _execute(conn, """INSERT INTO simulation_task
                (model_id,negative_pressure_kpa,days,engine,result_json,create_time)
                VALUES (%s,%s,%s,%s,%s,%s)""",
                (model_id, negative_pressure_kpa, days, result.get("engine", ""), json.dumps(result, ensure_ascii=False), _now()))
            conn.commit()
        return True
    except Exception:
        return False


def list_history(limit: int = 20):
    with _connect() as conn:
        return _rows(_execute(conn, """SELECT id,model_id,negative_pressure_kpa,days,engine,create_time
            FROM simulation_task ORDER BY id DESC LIMIT %s""", (limit,)))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
