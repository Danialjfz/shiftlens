"""ShiftLens dashboard — FastAPI + uvicorn (DESIGN.md contract).

Endpoints
---------
GET /                    single-page dashboard (inline HTML, vanilla JS +
                         inline SVG charts, zero external assets — offline-safe)
GET /api/monthly         out/monthly.json (404 JSON error + hint until generated)
GET /api/daily/{date}    {"date": ..., "reports": [...]} from
                         out/daily_reports/DATE/*.json
GET /api/dates           sorted list of dates that have reports
GET /api/scatter?x=&y=   raw (x, y) worker-day points for a correlation pair,
                         read from data/daily/*.json — powers the scatter chart
                         (monthly.json stores only r/n/insight, not the points)

Paths resolve from the project root (parents[2] of this file) regardless of the
current working directory; SHIFTLENS_OUT_DIR / SHIFTLENS_DATA_DIR override.

Run:  ../.venv/bin/python -m shiftlens.cli serve
Port: first free port in 8200-8209, bound to 127.0.0.1.
"""
from __future__ import annotations

import json
import os
import re
import socket
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from shiftlens.agent.metrics import fatigue_index, focus_score, pearson_r, safety_score

# ---------------------------------------------------------------------------
# Paths — project root is parents[2] of this file (shiftlens/dashboard/server.py)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(os.environ.get("SHIFTLENS_OUT_DIR", str(PROJECT_ROOT / "out")))
DATA_DIR = Path(os.environ.get("SHIFTLENS_DATA_DIR", str(PROJECT_ROOT / "data")))

DEMO_HINT = ("run `../.venv/bin/python -m shiftlens.cli demo` "
             "from the ShiftLens/ directory to generate data")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

app = FastAPI(title="ShiftLens", version="0.1.0")

# ---------------------------------------------------------------------------
# Scatter variables — names used by monthly.json correlations, plus aliases.
# Each extractor takes (worker_record, environment) from data/daily/DATE.json.
# ---------------------------------------------------------------------------
_SCATTER_VARS = {
    # survey
    "fatigue": lambda w, e: w["survey"]["fatigue"],
    "mood": lambda w, e: w["survey"]["mood"],
    "perceived_productivity": lambda w, e: w["survey"]["perceived_productivity"],
    # output
    "units": lambda w, e: w["output"]["units"],
    "defects": lambda w, e: w["output"]["defects"],
    "tasks_completed": lambda w, e: w["output"]["tasks_completed"],
    # environment
    "noise": lambda w, e: e["noise_db"],
    "noise_db": lambda w, e: e["noise_db"],
    "temperature": lambda w, e: e["temperature_c"],
    "temperature_c": lambda w, e: e["temperature_c"],
    "air_quality_pm25": lambda w, e: e["air_quality_pm25"],
    # detections
    "ppe_ok_pct": lambda w, e: w["detections"]["ppe_ok_pct"],
    "phone_events": lambda w, e: w["detections"]["phone_events"],
    "idle_events": lambda w, e: w["detections"]["idle_events"],
    "safety_zone_violations": lambda w, e: w["detections"]["safety_zone_violations"],
    # sensors
    "hr_avg": lambda w, e: w["sensors"]["hr_avg"],
    "hr_max": lambda w, e: w["sensors"]["hr_max"],
    "steps": lambda w, e: w["sensors"]["steps"],
    "station_time_min": lambda w, e: w["sensors"]["station_time_min"],
    # derived metrics (formulas from agent/metrics.py — the single source of truth)
    "fatigue_index": lambda w, e: fatigue_index(w),
    "focus_score": lambda w, e: focus_score(w),
    "safety_score": lambda w, e: safety_score(w),
}


def _error(status: int, message: str, hint: str | None = None) -> JSONResponse:
    body: dict = {"error": message}
    if hint:
        body["hint"] = hint
    return JSONResponse(status_code=status, content=body)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.get("/api/monthly")
def api_monthly():
    path = OUT_DIR / "monthly.json"
    if not path.is_file():
        return _error(404, "monthly.json not found — monthly analytics "
                           "have not been generated yet", DEMO_HINT)
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/dates")
def api_dates() -> list[str]:
    base = OUT_DIR / "daily_reports"
    if not base.is_dir():
        return []
    return sorted(
        d.name for d in base.iterdir()
        if d.is_dir() and _DATE_RE.match(d.name) and any(d.glob("*.json"))
    )


@app.get("/api/daily/{date}")
def api_daily(date: str):
    if not _DATE_RE.match(date):
        return _error(404, f"invalid date {date!r} (expected YYYY-MM-DD)")
    day_dir = OUT_DIR / "daily_reports" / date
    reports: list[dict] = []
    if day_dir.is_dir():
        for p in sorted(day_dir.glob("*.json")):
            try:
                reports.append(json.loads(p.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue  # skip corrupt file rather than failing the whole day
    if not reports:
        return _error(404, f"no daily reports found for {date}",
                      f"run `../.venv/bin/python -m shiftlens.cli report --date {date}` "
                      f"(or the full demo: {DEMO_HINT})")
    return {"date": date, "reports": reports}


@app.get("/api/scatter")
def api_scatter(x: str, y: str):
    if x not in _SCATTER_VARS or y not in _SCATTER_VARS:
        return _error(400, f"unknown variable (x={x!r}, y={y!r})",
                      "supported: " + ", ".join(sorted(_SCATTER_VARS)))
    base = DATA_DIR / "daily"
    if not base.is_dir():
        return _error(404, "dataset not found (data/daily/)", DEMO_HINT)
    fx, fy = _SCATTER_VARS[x], _SCATTER_VARS[y]
    points: list[list[float]] = []
    for f in sorted(base.glob("*.json")):
        try:
            day = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        env = day.get("environment", {})
        for w in day.get("workers", []):
            try:
                points.append([round(float(fx(w, env)), 4),
                               round(float(fy(w, env)), 4)])
            except (KeyError, TypeError, ValueError):
                continue
    if not points:
        return _error(404, "no worker-day observations in data/daily/", DEMO_HINT)
    r = pearson_r([p[0] for p in points], [p[1] for p in points])
    return {"x": x, "y": y, "n": len(points), "r": round(r, 4), "points": points}


# ---------------------------------------------------------------------------
# Port probing + entry point
# ---------------------------------------------------------------------------
def _find_free_port(lo: int = 8200, hi: int = 8209) -> int:
    """First port in [lo, hi] on 127.0.0.1 with nothing listening."""
    for port in range(lo, hi + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"no free port in {lo}-{hi}; close something and retry")


def main() -> None:
    """Entry point used by `shiftlens.cli serve` (no required arguments)."""
    import uvicorn

    port = _find_free_port()
    print(f"ShiftLens dashboard → http://127.0.0.1:{port}")
    print(f"  monthly: {OUT_DIR / 'monthly.json'}")
    print(f"  reports: {OUT_DIR / 'daily_reports'}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


# ---------------------------------------------------------------------------
# Single-page dashboard — inline HTML/CSS/JS, no CDN, no external assets.
# ---------------------------------------------------------------------------
INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ShiftLens — Workforce Analytics</title>
<style>
:root {
  --bg: #0a0e14; --panel: #10161e; --panel2: #141c26; --border: #1f2b3a;
  --text: #d9e3ee; --muted: #7e92a6; --accent: #4fa3ff; --teal: #2dd4bf;
  --amber: #f5a623; --grid: #1a2531; --chip: #1a2534;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg); color: var(--text);
  font: 14px/1.55 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
header.top {
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 16px 28px; border-bottom: 1px solid var(--border);
  background: linear-gradient(180deg, #0d1420 0%, var(--bg) 100%);
  position: sticky; top: 0; z-index: 5;
}
.brand { display: flex; align-items: center; gap: 12px; }
.brand h1 { font-size: 19px; font-weight: 650; letter-spacing: .2px; }
.brand h1 span { color: var(--accent); }
.brand .tag { color: var(--muted); font-size: 12.5px; margin-top: 1px; }
.pill {
  background: var(--chip); border: 1px solid var(--border); color: var(--muted);
  border-radius: 999px; padding: 5px 14px; font-size: 12.5px; white-space: nowrap;
}
.pill b { color: var(--text); font-weight: 600; }
main { max-width: 1240px; margin: 0 auto; padding: 22px 24px 60px; }
#banner {
  display: none; background: #2a1a12; border: 1px solid #5a3a1a; color: #f5c98a;
  border-radius: 10px; padding: 12px 16px; margin-bottom: 18px; font-size: 13px;
}
#banner code { background: rgba(255,255,255,.08); padding: 1px 6px; border-radius: 5px; }
#kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 18px; }
.kpi { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 14px 16px; }
.kpi .k-label { color: var(--muted); font-size: 11.5px; text-transform: uppercase; letter-spacing: .7px; }
.kpi .k-value { font-size: 22px; font-weight: 650; margin-top: 4px; font-variant-numeric: tabular-nums; }
.kpi .k-sub { color: var(--muted); font-size: 11.5px; margin-top: 2px; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 980px) { .grid { grid-template-columns: 1fr; } }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 18px 20px; min-width: 0; }
.card.wide { grid-column: 1 / -1; }
.card h2 { font-size: 14.5px; font-weight: 650; letter-spacing: .2px; }
.card .sub { color: var(--muted); font-size: 12px; margin-top: 2px; }
.card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
select, .seg button {
  background: var(--panel2); color: var(--text); border: 1px solid var(--border);
  border-radius: 8px; padding: 6px 10px; font-size: 12.5px; outline: none; font-family: inherit;
}
select:focus, .seg button:focus { border-color: var(--accent); }
select { max-width: 240px; }
.seg { display: inline-flex; }
.seg button { border-radius: 0; cursor: pointer; color: var(--muted); }
.seg button:first-child { border-radius: 8px 0 0 8px; }
.seg button:last-child { border-radius: 0 8px 8px 0; border-left: none; }
.seg button.active { background: #1b2c40; color: var(--accent); border-color: #2b4a6e; }
svg { display: block; width: 100%; height: auto; }
.meta { color: var(--muted); font-size: 12.5px; margin-top: 8px; }
.meta b.r { color: var(--teal); font-size: 13.5px; }
.legend { display: flex; gap: 16px; font-size: 12px; color: var(--muted); align-items: center; }
.legend .sw { display: inline-block; width: 18px; height: 3px; border-radius: 2px; margin-right: 6px; vertical-align: middle; }
.findings { display: flex; flex-direction: column; gap: 10px; }
.finding {
  display: flex; gap: 12px; background: var(--panel2); border: 1px solid var(--border);
  border-radius: 10px; padding: 12px 14px; font-size: 13px; align-items: flex-start;
}
.fnum {
  flex: none; width: 24px; height: 24px; border-radius: 7px; background: #17293d;
  color: var(--accent); font-weight: 700; font-size: 12px;
  display: flex; align-items: center; justify-content: center; margin-top: 1px;
}
.report-controls { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 12px; }
.report-controls label { color: var(--muted); font-size: 12px; display: flex; flex-direction: column; gap: 4px; }
.flagchip {
  display: inline-block; background: #3a2318; color: var(--amber); border: 1px solid #6b4423;
  font-size: 11.5px; border-radius: 999px; padding: 2px 10px; margin: 0 6px 8px 0; font-weight: 600;
}
.flagchip.ok { background: #12281f; color: var(--teal); border-color: #1f4a3e; }
.md { font-size: 13.5px; }
.md h1, .md h2, .md h3 { margin: 14px 0 6px; font-weight: 650; }
.md h1 { font-size: 17px; }
.md h2 { font-size: 15px; }
.md h3 { font-size: 12px; color: var(--accent); text-transform: uppercase; letter-spacing: .7px; }
.md h1:first-child, .md h2:first-child, .md h3:first-child { margin-top: 0; }
.md p { margin: 6px 0; color: #c3cfdb; }
.md ul { margin: 6px 0 6px 20px; color: #c3cfdb; }
.md li { margin: 3px 0; }
.md strong { color: var(--text); }
.md code { background: var(--chip); padding: 1px 5px; border-radius: 4px; font-size: 12px; }
.report-body { background: var(--panel2); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; min-height: 120px; }
.empty { color: var(--muted); font-size: 13px; padding: 18px 4px; }
footer { color: #54687c; font-size: 11.5px; text-align: center; margin-top: 28px; }
</style>
</head>
<body>
<header class="top">
  <div class="brand">
    <svg width="30" height="30" viewBox="0 0 32 32" fill="none" aria-hidden="true">
      <circle cx="14" cy="14" r="9" stroke="#4fa3ff" stroke-width="2.5"/>
      <line x1="20.5" y1="20.5" x2="28" y2="28" stroke="#2dd4bf" stroke-width="3" stroke-linecap="round"/>
      <polyline points="8,16 11.5,11 14.5,14 19,8" stroke="#dbe4ee" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <div>
      <h1>Shift<span>Lens</span></h1>
      <div class="tag">Agentic workforce analytics — wellbeing &times; productivity</div>
    </div>
  </div>
  <div class="pill">Period&nbsp;<b id="period">—</b></div>
</header>
<main>
  <div id="banner"></div>
  <section id="kpis"></section>
  <div class="grid">
    <section class="card">
      <div class="card-head">
        <div><h2>Correlation explorer</h2><div class="sub">All worker-day observations with least-squares trend</div></div>
        <select id="corrSelect" aria-label="Correlation pair"></select>
      </div>
      <svg id="scatterSvg" viewBox="0 0 680 380" role="img"></svg>
      <div class="meta" id="scatterMeta"></div>
    </section>
    <section class="card">
      <div class="card-head">
        <div><h2>Team daily output vs fatigue</h2><div class="sub">Shift totals per day</div></div>
        <div class="legend">
          <span><span class="sw" style="background:#4fa3ff"></span>Units (left)</span>
          <span><span class="sw" style="background:#2dd4bf"></span>Avg fatigue (right)</span>
        </div>
      </div>
      <svg id="teamSvg" viewBox="0 0 680 340" role="img"></svg>
    </section>
    <section class="card">
      <div class="card-head">
        <div><h2>Per-worker totals</h2><div class="sub" id="workerSub">30-day units produced</div></div>
        <div class="seg" id="workerSeg">
          <button data-key="units_total" class="active">Units</button><button data-key="defect_rate">Defect rate</button>
        </div>
      </div>
      <svg id="workerSvg" viewBox="0 0 680 330" role="img"></svg>
    </section>
    <section class="card">
      <div class="card-head"><div><h2>Findings</h2><div class="sub">Deterministic, computed from the month&rsquo;s data</div></div></div>
      <div class="findings" id="findings"></div>
    </section>
    <section class="card wide">
      <div class="card-head"><div><h2>Daily report browser</h2><div class="sub">Agent-authored per-worker daily reports</div></div></div>
      <div class="report-controls">
        <label>Date<select id="dateSelect"></select></label>
        <label>Worker<select id="workerSelect"></select></label>
      </div>
      <div id="flagRow"></div>
      <div class="report-body md" id="reportBody"><div class="empty">Loading&hellip;</div></div>
    </section>
  </div>
  <footer>ShiftLens &middot; deterministic metrics, agent-phrased reports &middot; offline, zero-CDN dashboard</footer>
</main>
<script>
"use strict";
const NS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);
const state = { monthly: null, reports: [], names: {} };

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
                  .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

async function fetchJSON(url) {
  const r = await fetch(url);
  let body = null;
  try { body = await r.json(); } catch (e) { /* non-JSON error body */ }
  if (!r.ok) {
    const err = new Error((body && (body.error || body.detail)) || ("HTTP " + r.status));
    err.hint = body && body.hint;
    throw err;
  }
  return body;
}

/* ---------- svg helpers ---------- */
function el(tag, attrs) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
}
function txt(x, y, s, attrs) {
  const t = el("text", Object.assign({ x: x, y: y, fill: "#7e92a6", "font-size": 11 }, attrs || {}));
  t.textContent = s;
  return t;
}
function fmt(v) {
  const a = Math.abs(v);
  if (a >= 1000) return Math.round(v).toLocaleString("en-US");
  if (a >= 100) return v.toFixed(0);
  if (a >= 10) return v.toFixed(1);
  return v.toFixed(2);
}
function niceTicks(min, max, count) {
  count = count || 5;
  if (!(max > min)) max = min + 1;
  const raw = (max - min) / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm >= 5 ? 5 : norm >= 2 ? 2 : 1) * mag;
  const lo = Math.floor(min / step) * step;
  const hi = Math.ceil(max / step) * step;
  const vals = [];
  for (let v = lo; v <= hi + step * 1e-9; v += step) vals.push(+v.toFixed(6));
  return { lo: lo, hi: hi, vals: vals };
}

/* ---------- chart 1: correlation scatter + least-squares trend ---------- */
function drawScatter(points, corr) {
  const svg = $("scatterSvg");
  const meta = $("scatterMeta");
  svg.innerHTML = "";
  if (!points.length) {
    svg.appendChild(txt(340, 190, "no data", { "text-anchor": "middle" }));
    return;
  }
  const W = 680, H = 380, P = { l: 60, r: 18, t: 14, b: 46 };
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  const xt = niceTicks(Math.min.apply(null, xs), Math.max.apply(null, xs), 6);
  const yt = niceTicks(Math.min.apply(null, ys), Math.max.apply(null, ys), 5);
  const X = v => P.l + (v - xt.lo) / (xt.hi - xt.lo) * iw;
  const Y = v => P.t + ih - (v - yt.lo) / (yt.hi - yt.lo) * ih;

  xt.vals.forEach(v => {
    svg.appendChild(el("line", { x1: X(v), y1: P.t, x2: X(v), y2: P.t + ih, stroke: "#1a2531" }));
    svg.appendChild(txt(X(v), P.t + ih + 18, fmt(v), { "text-anchor": "middle" }));
  });
  yt.vals.forEach(v => {
    svg.appendChild(el("line", { x1: P.l, y1: Y(v), x2: P.l + iw, y2: Y(v), stroke: "#1a2531" }));
    svg.appendChild(txt(P.l - 8, Y(v) + 4, fmt(v), { "text-anchor": "end" }));
  });
  svg.appendChild(txt(P.l + iw / 2, H - 6, corr.x, { "text-anchor": "middle", fill: "#9db2c6", "font-size": 12 }));
  svg.appendChild(txt(14, P.t + ih / 2, corr.y, { "text-anchor": "middle", fill: "#9db2c6", "font-size": 12,
    transform: "rotate(-90 14 " + (P.t + ih / 2) + ")" }));

  points.forEach(pt => {
    svg.appendChild(el("circle", { cx: X(pt[0]), cy: Y(pt[1]), r: 2.6, fill: "#4fa3ff", "fill-opacity": 0.45 }));
  });

  // least-squares regression line
  const n = points.length;
  const mx = xs.reduce((s, v) => s + v, 0) / n;
  const my = ys.reduce((s, v) => s + v, 0) / n;
  let sxy = 0, sxx = 0;
  for (let i = 0; i < n; i++) { sxy += (xs[i] - mx) * (ys[i] - my); sxx += (xs[i] - mx) * (xs[i] - mx); }
  const slope = sxy / (sxx || 1e-9);
  const b0 = my - slope * mx;
  svg.appendChild(el("line", {
    x1: X(xt.lo), y1: Y(b0 + slope * xt.lo), x2: X(xt.hi), y2: Y(b0 + slope * xt.hi),
    stroke: "#2dd4bf", "stroke-width": 2.2, "stroke-dasharray": "7 5", "stroke-linecap": "round"
  }));

  meta.innerHTML = "Pearson <b class='r'>r = " + Number(corr.r).toFixed(2) + "</b> &middot; n = " + corr.n +
    (corr.insight ? " &mdash; " + esc(corr.insight) : "");
}

/* ---------- chart 2: team daily line chart, units vs fatigue_avg ---------- */
function drawTeamDaily(td) {
  const svg = $("teamSvg");
  svg.innerHTML = "";
  if (!td || !td.length) {
    svg.appendChild(txt(340, 170, "no data", { "text-anchor": "middle" }));
    return;
  }
  const W = 680, H = 340, P = { l: 56, r: 52, t: 16, b: 42 };
  const iw = W - P.l - P.r, ih = H - P.t - P.b;
  const n = td.length;
  const ut = niceTicks(Math.min.apply(null, td.map(d => d.units)), Math.max.apply(null, td.map(d => d.units)), 5);
  const ft = niceTicks(Math.min.apply(null, td.map(d => d.fatigue_avg)), Math.max.apply(null, td.map(d => d.fatigue_avg)), 5);
  const X = i => P.l + (n === 1 ? iw / 2 : i / (n - 1) * iw);
  const YU = v => P.t + ih - (v - ut.lo) / (ut.hi - ut.lo) * ih;
  const YF = v => P.t + ih - (v - ft.lo) / (ft.hi - ft.lo) * ih;

  ut.vals.forEach(v => {
    svg.appendChild(el("line", { x1: P.l, y1: YU(v), x2: P.l + iw, y2: YU(v), stroke: "#1a2531" }));
    svg.appendChild(txt(P.l - 8, YU(v) + 4, fmt(v), { "text-anchor": "end", fill: "#4fa3ff" }));
  });
  ft.vals.forEach(v => {
    svg.appendChild(txt(P.l + iw + 8, YF(v) + 4, fmt(v), { "text-anchor": "start", fill: "#2dd4bf" }));
  });
  const step = Math.ceil(n / 7);
  td.forEach((d, i) => {
    if (i % step === 0 || i === n - 1)
      svg.appendChild(txt(X(i), P.t + ih + 18, d.date.slice(5), { "text-anchor": "middle" }));
  });

  svg.appendChild(el("polyline", {
    points: td.map((d, i) => X(i) + "," + YU(d.units)).join(" "),
    fill: "none", stroke: "#4fa3ff", "stroke-width": 2.2, "stroke-linejoin": "round" }));
  svg.appendChild(el("polyline", {
    points: td.map((d, i) => X(i) + "," + YF(d.fatigue_avg)).join(" "),
    fill: "none", stroke: "#2dd4bf", "stroke-width": 2.2, "stroke-linejoin": "round" }));
  td.forEach((d, i) => {
    svg.appendChild(el("circle", { cx: X(i), cy: YU(d.units), r: 2.4, fill: "#4fa3ff" }));
    svg.appendChild(el("circle", { cx: X(i), cy: YF(d.fatigue_avg), r: 2.4, fill: "#2dd4bf" }));
  });
}

/* ---------- chart 3: per-worker bars (units_total / defect_rate) ---------- */
function drawWorkers(workers, key) {
  const svg = $("workerSvg");
  svg.innerHTML = "";
  if (!workers || !workers.length) {
    svg.appendChild(txt(340, 160, "no data", { "text-anchor": "middle" }));
    return;
  }
  const rowH = 38, top = 8, labelW = 132, valW = 66, W = 680;
  const H = top + workers.length * rowH + 8;
  svg.setAttribute("viewBox", "0 0 680 " + H);
  const bw = W - labelW - valW - 16;
  const max = Math.max.apply(null, workers.map(w => w[key])) || 1;
  const color = key === "defect_rate" ? "#f5a623" : "#4fa3ff";

  workers.forEach((w, i) => {
    const y = top + i * rowH;
    const v = w[key];
    const wpx = Math.max(2, v / max * bw);
    const label = w.worker_id + " " + (w.name || "").split(" ")[0];
    const valTxt = key === "defect_rate" ? (v * 100).toFixed(1) + "%" : v.toLocaleString("en-US");
    svg.appendChild(txt(labelW - 10, y + rowH / 2 + 4, label, { "text-anchor": "end", fill: "#c3cfdb", "font-size": 12 }));
    svg.appendChild(el("rect", { x: labelW, y: y + 6, width: bw, height: rowH - 12, rx: 5, fill: "#151d27" }));
    svg.appendChild(el("rect", { x: labelW, y: y + 6, width: wpx, height: rowH - 12, rx: 5, fill: color, "fill-opacity": 0.85 }));
    svg.appendChild(txt(labelW + wpx + 8, y + rowH / 2 + 4, valTxt, { "font-size": 12, fill: "#9db2c6" }));
  });
  $("workerSub").textContent = key === "defect_rate"
    ? "Defects per unit produced (lower is better)" : "30-day units produced";
}

/* ---------- KPI cards + findings cards ---------- */
function renderKPIs(m) {
  const units = m.team_daily.reduce((s, d) => s + d.units, 0);
  const defects = m.team_daily.reduce((s, d) => s + d.defects, 0);
  const fat = m.team_daily.reduce((s, d) => s + d.fatigue_avg, 0) / m.team_daily.length;
  const noise = m.team_daily.reduce((s, d) => s + d.noise_db, 0) / m.team_daily.length;
  const kpis = [
    ["Days analysed", m.team_daily.length, m.period],
    ["Team units", units.toLocaleString("en-US"), "total output"],
    ["Team defects", defects.toLocaleString("en-US"), (100 * defects / Math.max(1, units)).toFixed(1) + "% of units"],
    ["Avg fatigue", fat.toFixed(2), "survey 1\u20135"],
    ["Avg noise", noise.toFixed(1) + " dB", "plant floor"],
    ["Workers", m.workers.length, "reporting daily"]
  ];
  $("kpis").innerHTML = kpis.map(k =>
    '<div class="kpi"><div class="k-label">' + esc(k[0]) + '</div>' +
    '<div class="k-value">' + esc(k[1]) + '</div>' +
    '<div class="k-sub">' + esc(k[2]) + "</div></div>").join("");
}

function renderFindings(fs) {
  const c = $("findings");
  if (!fs || !fs.length) { c.innerHTML = '<div class="empty">No findings.</div>'; return; }
  c.innerHTML = fs.map((f, i) =>
    '<div class="finding"><div class="fnum">' + (i + 1) + "</div><div>" + esc(f) + "</div></div>").join("");
}
/* ---------- mini markdown renderer (headers, bold, italic, code, lists) ---------- */
function md(src) {
  const inline = s => esc(s)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
  let html = "", inList = false;
  const closeList = () => { if (inList) { html += "</ul>"; inList = false; } };
  src.split("\n").forEach(raw => {
    const t = raw.trim();
    let m;
    if ((m = t.match(/^###\s+(.*)/))) { closeList(); html += "<h3>" + inline(m[1]) + "</h3>"; }
    else if ((m = t.match(/^##\s+(.*)/))) { closeList(); html += "<h2>" + inline(m[1]) + "</h2>"; }
    else if ((m = t.match(/^#\s+(.*)/))) { closeList(); html += "<h1>" + inline(m[1]) + "</h1>"; }
    else if ((m = t.match(/^[-*]\s+(.*)/))) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += "<li>" + inline(m[1]) + "</li>";
    }
    else if (t === "") { closeList(); }
    else { closeList(); html += "<p>" + inline(t) + "</p>"; }
  });
  closeList();
  return html;
}

/* ---------- daily report browser ---------- */
async function loadDates() {
  const body = $("reportBody");
  try {
    const dates = await fetchJSON("/api/dates");
    const sel = $("dateSelect");
    sel.innerHTML = dates.map(d => '<option value="' + esc(d) + '">' + esc(d) + "</option>").join("");
    if (dates.length) {
      sel.value = dates[dates.length - 1];
      await loadDay(sel.value);
    } else {
      body.innerHTML = '<div class="empty">No daily reports yet. Run the demo pipeline to generate them.</div>';
    }
  } catch (e) {
    body.innerHTML = '<div class="empty">Could not load report dates: ' + esc(e.message) + "</div>";
  }
}

async function loadDay(date) {
  const body = $("reportBody");
  body.innerHTML = '<div class="empty">Loading ' + esc(date) + "&hellip;</div>";
  try {
    const d = await fetchJSON("/api/daily/" + encodeURIComponent(date));
    state.reports = d.reports;
    const sel = $("workerSelect");
    sel.innerHTML = d.reports.map(r => {
      const nm = state.names[r.worker_id];
      const label = r.worker_id + (nm ? " \u00b7 " + nm : "");
      return '<option value="' + esc(r.worker_id) + '">' + esc(label) + "</option>";
    }).join("");
    renderReport();
  } catch (e) {
    state.reports = [];
    $("workerSelect").innerHTML = "";
    $("flagRow").innerHTML = "";
    body.innerHTML = '<div class="empty">' + esc(e.message) +
      (e.hint ? " &mdash; " + esc(e.hint) : "") + "</div>";
  }
}

function renderReport() {
  const wid = $("workerSelect").value;
  const rep = state.reports.find(r => r.worker_id === wid);
  if (!rep) { $("reportBody").innerHTML = '<div class="empty">No report selected.</div>'; return; }
  const m = rep.metrics || {};
  const name = state.names[wid] || wid;
  const flags = rep.flags || [];
  $("flagRow").innerHTML = flags.length
    ? flags.map(f => '<span class="flagchip">' + esc(f) + "</span>").join("")
    : '<span class="flagchip ok">no flags</span>';
  const src = [
    "## " + name + " \u2014 " + rep.date,
    "**Units:** " + m.units + "  \u00b7  **Defects:** " + m.defects,
    "**Fatigue index:** " + m.fatigue_index + "  \u00b7  **Focus score:** " +
      m.focus_score + "  \u00b7  **Safety score:** " + m.safety_score,
    "### Flags"
  ].concat(flags.length ? flags.map(f => "- " + f) : ["- none"])
   .concat(["### Summary", rep.summary || "(no summary)"])
   .join("\n");
  $("reportBody").innerHTML = md(src);
}

/* ---------- wiring + boot ---------- */
async function selectCorr() {
  const c = state.monthly.correlations[+$("corrSelect").value];
  const svg = $("scatterSvg");
  svg.innerHTML = "";
  svg.appendChild(txt(340, 190, "loading\u2026", { "text-anchor": "middle" }));
  $("scatterMeta").textContent = "";
  try {
    const d = await fetchJSON("/api/scatter?x=" + encodeURIComponent(c.x) +
                              "&y=" + encodeURIComponent(c.y));
    drawScatter(d.points, c);
  } catch (e) {
    svg.innerHTML = "";
    svg.appendChild(txt(340, 190, "scatter unavailable: " + e.message, { "text-anchor": "middle" }));
    $("scatterMeta").innerHTML = "Pearson <b class='r'>r = " + Number(c.r).toFixed(2) +
      "</b> &middot; n = " + c.n + (c.insight ? " &mdash; " + esc(c.insight) : "");
  }
}

function wireEvents() {
  $("corrSelect").addEventListener("change", selectCorr);
  $("workerSeg").addEventListener("click", ev => {
    const b = ev.target.closest("button");
    if (!b || !state.monthly) return;
    $("workerSeg").querySelectorAll("button").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    drawWorkers(state.monthly.workers, b.dataset.key);
  });
  $("dateSelect").addEventListener("change", () => loadDay($("dateSelect").value));
  $("workerSelect").addEventListener("change", renderReport);
}

async function boot() {
  wireEvents();
  try {
    const m = await fetchJSON("/api/monthly");
    state.monthly = m;
    m.workers.forEach(w => { state.names[w.worker_id] = w.name; });
    $("period").textContent = m.period;
    renderKPIs(m);
    $("corrSelect").innerHTML = m.correlations.map((c, i) =>
      '<option value="' + i + '">' + esc(c.x + " \u2194 " + c.y) + "</option>").join("");
    await selectCorr();
    drawTeamDaily(m.team_daily);
    drawWorkers(m.workers, "units_total");
    renderFindings(m.findings);
  } catch (e) {
    const b = $("banner");
    b.style.display = "block";
    b.innerHTML = "<b>Monthly analytics not available.</b> " + esc(e.message) +
      (e.hint ? "<br>Hint: " + esc(e.hint) : "");
  }
  await loadDates();
}
boot();
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
