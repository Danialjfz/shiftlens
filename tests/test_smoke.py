"""ShiftLens end-to-end smoke test (DESIGN.md contract).

Runs the real CLI (`python -m shiftlens.cli demo`) in a subprocess with
SHIFTLENS_DATA_DIR / SHIFTLENS_OUT_DIR pointed at a temp dir, then asserts:
  * data/daily has 30 files, workers.json has 8 workers
  * monthly.json exists with exactly 7 correlations (n = 240)
  * planted signals show: fatigue-units r < -0.3 (plus noise/temp/phone)
  * daily reports exist for all 8 workers on day 1 (json + md)
  * summaries list the real numbers; simulation is byte-deterministic

Works under pytest, or as a plain script:  python tests/test_smoke.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run_cli(tmp: Path, *argv: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["SHIFTLENS_DATA_DIR"] = str(tmp / "data")
    env["SHIFTLENS_OUT_DIR"] = str(tmp / "out")
    proc = subprocess.run(
        [sys.executable, "-m", "shiftlens.cli", *argv],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, (
        f"CLI {argv} exited {proc.returncode}:\n{proc.stdout}\n{proc.stderr}")
    return proc


def test_metric_formulas():
    """Pure-function formulas exactly as specified in DESIGN.md."""
    sys.path.insert(0, str(REPO))
    from shiftlens.agent import metrics as m

    rec = {"survey": {"fatigue": 5}, "sensors": {"hr_avg": 120},
           "detections": {"phone_events": 5, "idle_events": 10,
                          "ppe_ok_pct": 90.0, "safety_zone_violations": 1}}
    assert abs(m.fatigue_index(rec) - 1.0) < 1e-9
    assert abs(m.focus_score(rec) - 0.3) < 1e-9
    assert abs(m.safety_score(rec) - 0.65) < 1e-9
    # clamping
    hi = {"detections": {"phone_events": 50, "idle_events": 50,
                         "ppe_ok_pct": 100.0, "safety_zone_violations": 0}}
    assert m.focus_score(hi) == 0.0
    assert m.safety_score(hi) == 1.0
    # pearson via stdlib
    assert abs(m.pearson_r([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9
    assert m.pearson_r([1, 1, 1], [2, 3, 4]) == 0.0  # zero variance
    assert m.productivity_normalized(150, 100) == 1.5


def test_demo_pipeline():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        proc = _run_cli(tmp, "demo")
        assert "Findings:" in proc.stdout

        # --- dataset ---
        daily = sorted((tmp / "data" / "daily").glob("*.json"))
        assert len(daily) == 30, f"expected 30 daily files, got {len(daily)}"
        workers = json.loads((tmp / "data" / "workers.json").read_text())["workers"]
        assert len(workers) == 8
        assert all(0.85 <= w["base_skill"] <= 1.20 for w in workers)
        first = json.loads(daily[0].read_text())
        assert first["date"] == "2026-09-01"
        assert len(first["workers"]) == 8
        assert {"date", "environment", "workers"} == set(first)

        # --- monthly analytics ---
        monthly = json.loads((tmp / "out" / "monthly.json").read_text())
        assert monthly["period"] == "2026-09"
        assert len(monthly["team_daily"]) == 30
        assert len(monthly["workers"]) == 8
        corrs = {(c["x"], c["y"]): c for c in monthly["correlations"]}
        assert len(monthly["correlations"]) == 7
        assert corrs[("fatigue", "units")]["n"] == 240  # 8 workers x 30 days
        # planted causal signals must be rediscovered by the analytics
        assert corrs[("fatigue", "units")]["r"] < -0.3
        assert corrs[("noise", "defects")]["r"] > 0.2
        assert corrs[("temperature", "ppe_ok_pct")]["r"] < -0.2
        assert corrs[("phone_events", "units")]["r"] < 0
        assert all(c["insight"] for c in monthly["correlations"])
        assert 3 <= len(monthly["findings"]) <= 5

        # --- daily reports for all 8 workers on day 1 ---
        day1 = tmp / "out" / "daily_reports" / "2026-09-01"
        json_reports = sorted(day1.glob("*.json"))
        assert len(json_reports) == 8
        assert len(list(day1.glob("*.md"))) == 8
        rep = json.loads(json_reports[0].read_text())
        assert {"worker_id", "date", "metrics", "flags", "summary"} <= set(rep)
        assert {"fatigue_index", "focus_score", "safety_score",
                "units", "defects"} == set(rep["metrics"])
        assert str(rep["metrics"]["units"]) in rep["summary"]

        # --- determinism: regenerate into a second dir, byte-identical ---
        tmp2 = tmp / "again"
        _run_cli(tmp2, "simulate")
        for name in ("workers.json", "daily/2026-09-01.json",
                     "daily/2026-09-15.json", "daily/2026-09-30.json"):
            assert ((tmp / "data" / name).read_bytes()
                    == (tmp2 / "data" / name).read_bytes()), name


if __name__ == "__main__":
    test_metric_formulas()
    print("ok - metric formulas")
    test_demo_pipeline()
    print("ok - demo pipeline (30 days, 8 workers, 7 correlations, reports)")
    print("SMOKE TEST PASSED")
