# ShiftLens — Demo Video Script

**Format:** screen recording + voiceover · **Length:** ~90 s (plus a 30 s cut-down below)
**Prereqs:** project implemented; all commands run from `ShiftLens/` with the shared
venv (`../.venv/bin/python -m shiftlens.cli <cmd>`). LM Studio is optional — the demo
works with the LLM offline (template prose, heuristic plans). `demo` ends with the
agentic pass (first 3 flagged worker-days + the monthly narrative) and prints per-task
trace summaries; traces land in `out/traces/`.

## Shot list — 90-second cut

| # | Time | On screen (exact actions) | Narration (voiceover) |
|---|------|---------------------------|------------------------|
| 1 | 0:00–0:06 | Clean terminal, prompt sitting at `ShiftLens/`. Nothing typed yet. | "ShiftLens is an agentic workforce-analytics system. Every shift tells a story — we connect it to the numbers." |
| 2 | 0:06–0:19 | Type `../.venv/bin/python -m shiftlens.cli demo`, press Enter. Let it run: it simulates 30 days × 8 workers, writes daily reports, computes monthly analytics, prints the findings summary. Leave the printed findings on screen. | "One command: simulate a month for eight workers — sensors, micro-surveys, vision events — write a daily report for every worker, then correlate the whole month and print the findings." |
| 3 | 0:19–0:29 | Scroll up to the tail of the `demo` output: the per-task trace summaries from the agentic pass (task, tool calls, verifier verdict). Then `head -c 1500 out/traces/2026-09-01_W01.json` — slow scroll past the plan, the evidence, and the verifier block. | "Then the agent team investigates the flagged days — plan, gather evidence through tools, draft — and a verifier re-computes every number before anything is published. Every step is traced." |
| 4 | 0:29–0:41 | `cat out/daily_reports/2026-09-01/W01.md` — slow scroll through the metrics table (fatigue_index 0.64, focus_score 0.83, safety_score 0.98, units 145, defects 4), the flag, and the prose summary. | "Here's one worker's day. Fatigue, focus and safety are fixed formulas; the flags come from fixed thresholds — Aria's fatigue index crossed 0.6, so the report flags high fatigue. The only thing an LLM writes is this prose — and if the model is offline, a template says the same numbers." |
| 5 | 0:41–0:48 | `../.venv/bin/python -m shiftlens.cli serve` — note the printed port. Switch to the browser at `http://localhost:8200`. | "The dashboard serves on port 8200 — vanilla JavaScript, no CDN, so it runs on a closed network." |
| 6 | 0:48–0:59 | Scroll to the correlation scatter with trend line (fatigue ↔ units). Hover a few points, then rest the cursor on the trend line. | "Two hundred forty worker-days. Fatigue against output: r around minus 0.6 — higher fatigue strongly tracks lower output. It's plain Pearson correlation from the standard library." |
| 7 | 0:59–1:08 | Scroll to the team daily line chart (units vs fatigue). Trace one day where the two lines pull apart. | "Day by day, the team timeline shows output dipping where fatigue climbs." |
| 8 | 1:08–1:17 | Scroll to the findings cards, then the per-worker bar chart. Read the top finding aloud from the screen (seeded demo: "Days above 85 dB average 122% more defects per worker than quieter days"). | "Findings are threshold splits computed from the data — never hardcoded. Days above 85 decibels average a hundred and twenty-two percent more defects per worker." |
| 9 | 1:17–1:24 | Report browser: pick date `2026-09-01` → pick worker `W01 — Aria Kim` → the rendered markdown report appears. | "And every day's report is browsable — pick a date, pick a worker, read the day." |
| 10 | 1:24–1:30 | Scroll back to the top of the dashboard; hold on the findings cards. | "ShiftLens. Every shift tells a story — we connect it to the numbers." |

## 30-second cut-down

| # | Time | On screen | Narration |
|---|------|-----------|-----------|
| 1 | 0:00–0:04 | Terminal at `ShiftLens/`. | "ShiftLens — every shift tells a story; we connect it to the numbers." |
| 2 | 0:04–0:11 | `../.venv/bin/python -m shiftlens.cli demo` runs; findings print, then the agentic trace summaries. | "One command ingests a month for eight workers, writes a daily report per worker, and correlates the month — then a multi-agent team investigates the flagged days, with self-verification." |
| 3 | 0:11–0:18 | `cat out/daily_reports/2026-09-01/W01.md` — one slow scroll; flash `head -c 800 out/traces/2026-09-01_W01.json` at the end. | "Deterministic metrics, threshold flags — every number an agent writes is re-computed by a verifier. The LLM only phrases. It never decides." |
| 4 | 0:18–0:25 | `serve`, then the dashboard: correlation scatter with trend line, then the findings cards. | "On the dashboard: fatigue versus output across 240 worker-days, and findings computed from the data — never hardcoded." |
| 5 | 0:25–0:30 | Hold on the findings cards. | "ShiftLens. Works offline, explains itself, and tells you why the month looked the way it did." |

## Recording tips

- **Font size:** terminal at 18–20 pt minimum (or ~150% zoom); browser zoomed to
  125–150%. People will watch this on laptops and phones.
- **Window layout:** full-screen terminal for the CLI shots, full-screen browser
  (bookmarks bar hidden) for the dashboard. Record at 1920×1080 and pre-position
  both windows before you start, so switching is one clean cut.
- **Dry run:** do one complete end-to-end dry run before recording. The simulator
  is seeded (`random.Random(42)`), so the numbers should be reproducible — but if
  a finding or value differs on the day, read what's on the screen, not the script.
- **Pre-flight:** run `demo` once before recording so `data/`, `out/` and
  `out/traces/` already exist and the recorded run is fast and predictable. `demo`
  investigates only the first 3 flagged worker-days (plus the monthly narrative) to
  stay fast — run `demo --all-agents` in pre-flight if you want every trace on disk
  for cutaways. `clear` the terminal between shots; a short prompt
  (`export PS1='$ '`) reduces on-screen noise.
- **Typing:** paste commands (or recall them from history with ↑) instead of
  typing live — typos kill takes.
- **Port check:** `serve` probes ports 8200–8209. Confirm the printed port before
  switching to the browser; if it isn't 8200, use the printed one and adjust the
  narration.
- **LLM optional:** if LM Studio isn't running, the reports show template prose and
  the agents run on heuristic plans (trace JSON shows `"llm_used": false`). That's a
  feature — deliver the "works offline" line exactly as scripted.
- **Cursor discipline:** keep the mouse still while narrating; move it only to
  point at the thing you're talking about.
- **Audio:** quiet room, notifications silenced. If one-take screen + voice keeps
  going wrong, record the voiceover separately and lay it over the screen capture.
