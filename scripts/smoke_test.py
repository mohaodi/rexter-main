"""Minimal backend smoke test without starting an HTTP server."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database.mysql import database_status, init_database  # noqa: E402
from app.service.realtime_service import assessment, control_advice, diagnosis, generate_tick  # noqa: E402
from app.service.scheme_prediction_service import recommend_scheme  # noqa: E402

init_database()
assert len(generate_tick("采中")["items"]) == 5
assert database_status()["connected"]
assert "findings" in diagnosis()
assert len(assessment()["checks"]) == 4
assert len(control_advice()["commands"]) == 5
result = recommend_scheme([103518, 62249, 45265, 47045, 64469], 12, 5, 42, "采前", 3, 20, 30, 120)
assert len(result["boreholes"]) == 3
assert result["engineeringConstraints"]["safetyCheck"]
print("CBM V14 smoke test passed")
