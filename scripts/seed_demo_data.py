"""Generate clearly-labelled simulated monitoring data and persist it."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.database.mysql import init_database  # noqa: E402
from app.service.realtime_service import seed_history  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--points", type=int, default=144, help="每个钻孔生成多少个历史点")
parser.add_argument("--stage", choices=["采前", "采中", "采后"], default="采中")
args = parser.parse_args()
init_database()
print(seed_history(max(1, min(args.points, 10000)), args.stage))
