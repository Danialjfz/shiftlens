# ShiftLens — Demo Video Script (full production script)

**Format:** screen recording + voiceover · **Length:** 90 seconds (30 s cut-down at the end)
**Recording:** English narration (matches report + deck). Read the **SAY** blocks
verbatim — every number in them matches the seeded run you will see on screen.

---

## 0. Pre-flight (do this BEFORE recording)

```bash
cd ~/Documents/Projects/Mahan/ShiftLens
../.venv/bin/python -m shiftlens.cli demo            # generates data/, out/, out/traces/
export PS1='$ '                                       # clean prompt
clear
```

- Terminal font 18–20 pt, full screen. Browser zoomed 125–150 %, bookmarks bar
  hidden. Pre-position both windows; record at 1920×1080.
- Paste commands (or ↑ from history) — never type live.
- `demo` investigates the first 3 flagged worker-days + the monthly review, so
  traces exist. If you want all 166 traces for cutaways: `demo --all-agents`.
- If LM Studio is not running, everything still works — that's scripted in
  (Scene 4). Traces will show `"llm_used": false`; don't hide it, it's a feature.

---

## THE 90-SECOND CUT

### Scene 1 — Hook (0:00–0:06)

**SCREEN:** Clean terminal, prompt at `ShiftLens/`. Nothing typed.

**SAY:**
> "ShiftLens is an agentic workforce-analytics system. Every shift tells a
> story — and we connect it to the numbers."

---

### Scene 2 — One command (0:06–0:19)

**SCREEN:** Paste and run:

```bash
../.venv/bin/python -m shiftlens.cli demo
```

Let it run. It simulates 30 days × 8 workers, writes 240 daily reports, computes
the monthly analytics, and prints the findings. Leave the findings on screen.

**SAY:**
> "One command: simulate a month for eight workers — wearable sensors,
> micro-surveys, and vision events — write a daily report for every worker,
> then correlate the whole month and print what matters."

---

### Scene 3 — The agent team (0:19–0:30)

**SCREEN:** Scroll to the tail of the demo output — the agentic trace summary:

```
Agentic pass (v2): investigating 3 of 166 flagged worker-days + monthly review
  2026-09-01/W01: task=investigation, tool calls=4, verifier=pass, revisions=0
```

Then run, and slow-scroll past the plan, evidence, and verifier block:

```bash
head -c 1500 out/traces/2026-09-01_W01.json
```

**SAY:**
> "Then a team of agents investigates the flagged days. A planner decides what
> to check, an investigator gathers evidence through tools, a drafter writes
> the note — and a verifier re-computes every single number before anything
> is published. Every step is traced."

---

### Scene 4 — One worker's day (0:30–0:43)

**SCREEN:**

```bash
cat out/daily_reports/2026-09-01/W01.md
```

Slow scroll: metrics table (fatigue_index **0.64**, focus_score **0.83**,
safety_score **0.98**, units **145**, defects **4**), flag `high_fatigue`,
the `## Investigation` section, then the summary.

**SAY:**
> "Here's one worker's day. Fatigue, focus and safety are fixed formulas, and
> the flags come from fixed thresholds — Aria's fatigue index crossed zero
> point six, so the day is flagged, and the agents explain why: elevated
> fatigue versus the team, and a recurring pattern. If the language model is
> offline, a template says the same numbers. The LLM phrases — it never
> decides."

---

### Scene 5 — Serve the dashboard (0:43–0:49)

**SCREEN:**

```bash
../.venv/bin/python -m shiftlens.cli serve
```

Note the printed port, then switch to the browser at `http://localhost:8200`
(if it printed a different port, use that one).

**SAY:**
> "The dashboard serves locally — vanilla JavaScript, no CDN — so it runs on
> a closed factory network."

---

### Scene 6 — Correlation scatter (0:49–0:59)

**SCREEN:** Scroll to the correlation explorer (fatigue ↔ units selected).
Hover two or three points, then rest the cursor on the dashed trend line.

**SAY:**
> "Two hundred and forty worker-days. Fatigue against output: r is minus zero
> point six one — higher fatigue strongly tracks lower output. It's plain
> Pearson correlation, computed from the standard library."

---

### Scene 7 — Team timeline (0:59–1:07)

**SCREEN:** Scroll to the team daily line chart (units vs average fatigue).
Point at one day where the lines pull apart.

**SAY:**
> "Day by day, the team timeline shows output dipping exactly where fatigue
> climbs."

---

### Scene 8 — Findings (1:07–1:16)

**SCREEN:** Scroll to the findings cards. Read the top card from the screen.

**SAY:**
> "Findings are threshold splits, computed from the data — never hardcoded.
> Days above eighty-five decibels average a hundred and twenty-two percent
> more defects per worker. Hot days drop PPE compliance by twelve percent."

---

### Scene 9 — Report browser (1:16–1:23)

**SCREEN:** In the daily-report browser: pick date **2026-09-01**, then worker
**W01 — Aria Kim**. The rendered report appears with its flag chip.

**SAY:**
> "And every day is browsable — pick a date, pick a worker, read the day the
> agents wrote."

---

### Scene 10 — Close (1:23–1:30)

**SCREEN:** Scroll back to the top of the dashboard; hold on the findings cards.

**SAY:**
> "ShiftLens. Deterministic where it counts, agentic where it helps — and every
> number is verified. Every shift tells a story. We connect it to the numbers."

---

## THE 30-SECOND CUT-DOWN

| # | Time | Screen | SAY (verbatim) |
|---|------|--------|----------------|
| 1 | 0:00–0:04 | Terminal at `ShiftLens/` | "ShiftLens — every shift tells a story; we connect it to the numbers." |
| 2 | 0:04–0:11 | `demo` runs; findings + agentic trace summaries print | "One command ingests a month for eight workers, writes a daily report per worker, and correlates the month — then a multi-agent team investigates the flagged days, with self-verification." |
| 3 | 0:11–0:18 | `cat out/daily_reports/2026-09-01/W01.md`, one slow scroll; flash `head -c 800 out/traces/2026-09-01_W01.json` | "Deterministic metrics, threshold flags — and every number an agent writes is re-computed by a verifier. The LLM only phrases. It never decides." |
| 4 | 0:18–0:25 | `serve` → dashboard: scatter with trend line → findings cards | "On the dashboard: fatigue versus output across two hundred forty worker-days, and findings computed from the data — never hardcoded." |
| 5 | 0:25–0:30 | Hold on the findings cards | "ShiftLens. Works offline, explains itself, and tells you why the month looked the way it did." |

---

## Recording tips

- **Dry run first.** The simulator is seeded (`random.Random(42)`), so numbers
  reproduce exactly — but if anything differs on the day, read the screen, not
  the script.
- **`clear` between shots**; keep the mouse still while narrating; move it only
  to point at the thing you're talking about.
- **Pace:** the SAY blocks run about 2.2 words/second — conversational, not
  rushed. If you run long, trim Scene 7's line (it doubles Scene 6's point).
- **Port check:** `serve` probes 8200–8209. Confirm the printed port before
  switching windows; if it isn't 8200, adjust the Scene 5 line.
- **Audio:** quiet room, notifications off. If one-take screen + voice keeps
  failing, record the voiceover separately and lay it over the screen capture.
- **If a judge asks "is this really agentic?"** — the answer is on disk:
  `out/traces/` holds the plan, the tool calls, the evidence, the verifier's
  verdict, and the revision count for every investigation.
