"""Isolated integration checks for the AI safety decision prototype."""

import csv
import io
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
TEST_DB = tempfile.NamedTemporaryFile(prefix="cbm_ai_workbench_", suffix=".db", delete=False)
TEST_DB.close()
os.environ["CBM_SQLITE_PATH"] = TEST_DB.name

from app.database.mysql import _connect, init_database
from app.service.ai_workbench_service import (
    data_quality,
    detect_anomalies,
    forecast_well,
    generate_safe_candidates,
    import_monitor_csv,
    review_history,
    record_review,
)


class AIWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_database()

    def setUp(self):
        with _connect() as conn:
            conn.execute("DELETE FROM sensor_reading")
            conn.execute("DELETE FROM shadow_review")
            conn.commit()

    @staticmethod
    def csv_bytes(points=32):
        stream = io.StringIO()
        fields = ["recordedAt", "boreholeCode", "negativePressureKPa", "methanePct", "mixedFlowM3Min", "pureFlowM3Min", "pumpPowerKW", "lifecycleStage"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for tick in range(points):
            for well in range(1, 6):
                methane = 45.0 if tick == points - 1 and well == 2 else 82 + math.sin(tick / 5 + well)
                mixed = 4 + well * 0.1
                writer.writerow({
                    "recordedAt": f"2026-10-15T09:{tick // 2:02d}:{tick % 2 * 30:02d}+08:00",
                    "boreholeCode": f"W{well}", "negativePressureKPa": 22 + well * 0.2,
                    "methanePct": methane, "mixedFlowM3Min": mixed,
                    "pureFlowM3Min": mixed * methane / 100, "pumpPowerKW": 42,
                    "lifecycleStage": "采中",
                })
        return stream.getvalue().encode("utf-8")

    def test_csv_quality_forecast_and_anomaly(self):
        result = import_monitor_csv("monitor.csv", self.csv_bytes())
        self.assertEqual(result["insertedRows"], 160)
        quality = data_quality()
        self.assertEqual(quality["wellCount"], 5)
        self.assertEqual(quality["recordCount"], 160)
        forecast = forecast_well("W1", horizon=6)
        self.assertTrue(forecast["ok"])
        self.assertEqual(len(forecast["variables"]["methanePct"]["lowerBand"]), 6)
        result = detect_anomalies(120)
        self.assertTrue(any(row["boreholeCode"] == "W2" and row["field"] == "methanePct" for row in result["findings"]))

    def test_insufficient_history_is_reported(self):
        result = import_monitor_csv("short.csv", self.csv_bytes(points=2))
        self.assertEqual(result["insertedRows"], 10)
        forecast = forecast_well("W5", horizon=4)
        self.assertFalse(forecast["ok"])
        self.assertEqual(forecast["requiredCount"], 12)

    def test_candidate_constraints_and_shadow_review(self):
        result = generate_safe_candidates(
            [103518, 62249, 45265, 47045, 64469], "采中", 3, 20, 30, 120,
            15, 35, 60, 2, 80,
        )
        self.assertEqual(len(result["candidates"]), 3)
        for candidate in result["candidates"]:
            self.assertIn(len(candidate["boreholes"]), (3, 5))
            self.assertEqual(len(candidate["safetyChecks"]), 6)
            self.assertTrue(all("passed" in check for check in candidate["safetyChecks"]))
        selected = result["candidates"][0]
        review = record_review("plan", selected["schemeCode"], "accepted", "unit test", selected)
        self.assertEqual(review_history()["count"], 1)
        self.assertEqual(review["decision"], "accepted")


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        Path(TEST_DB.name).unlink(missing_ok=True)
