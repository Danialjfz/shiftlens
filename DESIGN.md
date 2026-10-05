# ShiftLens — Design Contract (v2)

**One line:** An agentic workforce-analytics system: every day it ingests each
worker's sensor streams, micro-survey answers, and object-detection events,
writes an agent-authored daily report per worker; at month's end it correlates
wellbeing/conditions with productivity and serves a dashboard of findings.

**Guiding principle (same as our other agents): the LLM phrases; it never
decides.** All metrics, flags, correlations and findings are deterministic
Python. An optional LM Studio model (OpenAI-compatible, `SHIFTLENS_LMS_HOST`,
default `http://localhost:1234`, model `SHIFTLENS_LMS_MODEL` default
`bonsai-27b`) only rewrites the daily report's prose summary. Everything works
with the LLM offline (template fallback).

## Repo layout

```
ShiftLens/
  DESIGN.md  README.md  requirements.txt  .gitignore
  shiftlens/
    __init__.py
    sensors/__init__.py  sensors/simulate.py
    agent/__init__.py    agent/metrics.py  agent/report.py  agent/llm.py
    agents/__init__.py   agents/roles.py  agents/tools.py  agents/orchestrator.py
                         agents/verifier.py
    analytics/__init__.py analytics/monthly.py
    dashboard/__init__.py dashboard/server.py
    cli.py
  tests/test_smoke.py
  docs/report.tex  docs/spec.tex  docs/slides.tex  docs/video_script.md
  data/   (generated: workers.json, daily/YYYY-MM-DD.json)
  out/    (generated: daily_reports/YYYY-MM-DD/*.json+md, monthly.json)
```

Python 3.12. Deps: `fastapi`, `uvicorn` only (already in the shared venv at
`../.venv`). NO pandas/numpy — Pearson correlation via stdlib `statistics`.
Run everything as `../.venv/bin/python -m shiftlens.cli <cmd>` from ShiftLens/.

## Data schema — data/workers.json

```json
{"workers": [
  {"worker_id": "W01", "name": "Aria Kim", "role": "assembler",
   "shift": "day", "base_skill": 1.05}
]}
```

8 workers, roles from {assembler, packer, inspector, forklift-operator},
base_skill in [0.85, 1.20].

## Data schema — data/daily/YYYY-MM-DD.json (one file per day, 30 days, Sept 2026)

```json
{
  "date": "2026-09-01",
  "environment": {"noise_db": 78.2, "temperature_c": 26.1,
                  "air_quality_pm25": 12},
  "workers": [
    {
      "worker_id": "W01",
      "sensors": {"hr_avg": 78, "hr_max": 112, "steps": 8400,
                  "station_time_min": 402},
      "detections": {"ppe_ok_pct": 98.5, "phone_events": 1,
                     "idle_events": 3, "safety_zone_violations": 0},
      "survey": {"fatigue": 2, "mood": 4, "perceived_productivity": 4,
                 "blockers": ""},
      "output": {"units": 142, "defects": 2, "tasks_completed": 9}
    }
  ]
}
```

Simulator: `random.Random(42)`, 30 days starting 2026-09-01. Hidden causal
structure (analytics must rediscover these — do not hardcode findings):
- noise_db > 85 days → defect rate rises
- survey fatigue ↑ → units ↓, defects ↑
- temperature_c > 28 → ppe_ok_pct drops
- phone_events ↑ (more likely on low-mood days) → units ↓
- per-worker base_skill scales units; small daily noise everywhere

## Metrics (agent/metrics.py — pure functions)

- `fatigue_index = 0.6*(survey.fatigue/5) + 0.4*min(hr_avg/100, 1.2)/1.2`
- `focus_score = clamp(1 - 0.08*phone_events - 0.03*idle_events, 0, 1)`
- `safety_score = clamp(ppe_ok_pct/100 - 0.25*safety_zone_violations, 0, 1)`
- `productivity = units`, normalized per worker vs their own 30-day mean

## Daily report (agent/report.py) — out/daily_reports/DATE/WID.json + .md

```json
{"worker_id": "W01", "date": "2026-09-01",
 "metrics": {"fatigue_index": 0.643, "focus_score": 0.83,
             "safety_score": 0.985, "units": 145, "defects": 4},
 "flags": ["high_fatigue"],
 "summary": "<prose — LLM if available, else template>"}
```

Deterministic flag rules: `high_fatigue` fatigue_index ≥ 0.6;
`low_focus` focus_score < 0.7; `safety_risk` safety_score < 0.85;
`defect_spike` defects ≥ 2× worker mean. Summary ALWAYS lists numbers;
LLM only rephrases (prompt forbids inventing numbers).

## Monthly analytics (analytics/monthly.py) — out/monthly.json

```json
{"period": "2026-09",
 "team_daily": [{"date": "...", "units": 1042, "defects": 21,
                 "fatigue_avg": 2.6, "noise_db": 81.2}],
 "workers": [{"worker_id": "W01", "name": "...", "units_total": 4100,
              "defect_rate": 0.014, "fatigue_avg": 2.4,
              "focus_avg": 0.88, "safety_avg": 0.96}],
 "correlations": [{"x": "fatigue", "y": "units", "r": -0.61, "n": 240,
                   "insight": "Higher fatigue strongly tracks lower output"}],
 "findings": ["Days above 85 dB average 122% more defects per worker than quieter days (5.8 vs 2.6)", "..."]}
```

Correlations across all (worker, day) pairs, n = workers × days, for pairs:
fatigue↔units, fatigue↔defects, noise↔defects, temperature↔ppe_ok_pct,
phone_events↔units, mood↔units, focus_score↔units. Findings generated from
threshold splits (e.g. mean defects on >85 dB days vs ≤85 dB days, percent
delta) — computed from data, never hardcoded.

## Dashboard (dashboard/server.py) — FastAPI, port 8200 (probe 8200-8209)

- `GET /` — single-page dashboard, vanilla JS + inline SVG charts (NO CDN —
  must work offline): correlation scatter w/ trend line, team daily line
  chart (units vs fatigue), per-worker bar chart, findings cards, daily-report
  browser (pick date → pick worker → rendered markdown report)
- `GET /api/monthly` — out/monthly.json (404 until generated)
- `GET /api/daily/{date}` — that day's reports
- `GET /api/dates` — list of report dates

## CLI (cli.py)

`simulate` (generate dataset) · `report [--date D]` (daily reports) ·
`monthly` (analytics) · `serve` (dashboard) · `demo` (simulate→report→monthly,
print findings summary)

## tests/test_smoke.py

End-to-end: run demo pipeline into a tmp data dir, assert monthly.json has 7
correlations with |r|>0 for the planted signals, daily reports exist for all
workers, dashboard module imports.

---

# Agentic layer (v2) — agents/ package

The v1 pipeline answers "what happened". The v2 agentic layer answers "why —
and are we sure?". A team of role agents works over the same deterministic
data through an explicit tool registry, with a verifier agent that re-checks
every numeric claim before anything is published. **The LLM still never
decides**: planning/drafting may use the LLM, but every number that reaches
output is either computed by a tool or verified against one. Fully offline:
with no LLM the same loop runs on heuristic plans and template drafts.

## Roster (agents/roles.py)

- **orchestrator** — runs the loop per task: plan → investigate (tool calls)
  → draft → verify → (revise once if rejected) → publish. Writes the trace.
- **planner** — given a task (a flagged worker-day, or the monthly review),
  emits an investigation plan: an ordered list of tool calls. LLM if
  available, else a deterministic heuristic plan (flag-driven rules below).
- **investigator** — executes tool calls, collects evidence items
  `{tool, args, result}` — pure executor, no prose.
- **drafter** — writes prose (investigation note / monthly narrative) from
  evidence only; prompt forbids numbers not present in the evidence.
- **verifier** — the critic. Extracts every numeric claim from the draft
  (regex for ints/decimals/percents), recomputes each against tool data,
  returns `{verdict: pass|fail, mismatches: [...]}`. On fail the orchestrator
  sends the draft back once with the mismatch list; if the revision still
  fails, the deterministic template text is used instead (trace records this).

## Tool registry (agents/tools.py)

`TOOLS = {name: {"fn": callable, "schema": str, "description": str}}` —
the only way agents read data. All read-only, all return JSON-able dicts:

- `get_worker_day(date, worker_id)` → raw record + computed metrics + flags
- `get_worker_history(worker_id, last_n=7)` → per-day metrics/units/defects
- `compare_to_team(date, metric)` → worker value vs team mean that day
- `get_environment_context(date)` → env readings + which thresholds crossed
  (noise>85, temp>28) + team defect/ppE deltas on those days
- `get_flag_rules()` → the deterministic flag rules (for the planner)
- `get_correlations()` / `get_findings()` → monthly analytics outputs
- `get_flagged_days(worker_id)` → all dates where the worker had any flag

Heuristic plan rules (offline planner): for each flag on the day, append
`get_worker_history(wid,7)` + `compare_to_team(date,<flag-relevant metric>)`;
if any env threshold crossed that day append `get_environment_context(date)`;
always end with `get_flagged_days(wid)` (recurrence check).

## Outputs (additive — v1 artifacts unchanged)

- Flagged daily reports gain an `"investigation"` block in the JSON + a
  markdown section: `{likely_drivers: [...], evidence: [...], note: str}`.
- `monthly.json` gains `"narrative"` (editor-written month review, verified)
  and `"agentic": {"traces": n, "verifier_pass_rate": x, "revisions": n}`.
- Traces: `out/traces/<date>_<WID>.json` per investigated worker-day and
  `out/traces/monthly.json`: `{task, plan: [tool calls], evidence: [...],
  draft, verifier: {...}, revisions: int, published: str, llm_used: bool}`.
  Traces are the judge-facing proof of agent behavior — never silently
  swallowed; `demo` prints a compact per-task trace summary to the terminal.

## CLI additions (cli.py)

- `agents [--date D]` — run the agentic pass only (investigations for all
  flagged worker-days on D/all dates + monthly narrative). Requires v1
  artifacts to exist; error with hint otherwise.
- `demo` — after monthly, automatically runs the agentic pass for the FIRST
  3 flagged worker-days (keeps demo fast) + the monthly narrative, printing
  trace summaries; `demo --all-agents` investigates every flagged day.

## tests (extend tests/test_smoke.py)

Additionally assert: traces exist for investigated days; every trace has
plan+evidence+verdict; `monthly.json` has a non-empty `narrative`;
verifier pass rate ≥ 0.5 (some drafts may legitimately need the template
fallback offline — that's part of the story, not a failure).
