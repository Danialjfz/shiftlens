# ShiftLens

Agentic workforce analytics: daily worker data (sensors + micro-surveys +
object-detection events) → agent-authored daily reports → a monthly dashboard
correlating wellbeing and conditions with productivity.

**The LLM phrases; it never decides.** All metrics, flags, correlations and
findings are deterministic Python; an optional local LLM (LM Studio) only
rewrites prose. New in v2: a **multi-agent layer** — a five-role agent team
that investigates flagged worker-days and drafts the monthly narrative through
a read-only tool registry, with a verifier agent that re-computes every
numeric claim before anything is published. Fully offline-capable.

## Quickstart

```bash
# from this directory, using the shared venv
../.venv/bin/python -m shiftlens.cli demo      # simulate 30 days, write daily
                                               # reports + monthly.json, then run
                                               # the agentic pass (first 3 flagged
                                               # days + monthly narrative) and
                                               # print findings + trace summaries
../.venv/bin/python -m shiftlens.cli serve     # dashboard on http://127.0.0.1:8200
```

See `DESIGN.md` for the full architecture contract, `docs/` for the report,
technical specification, slide deck and video script.

## Usage

```bash
../.venv/bin/python -m shiftlens.cli simulate           # generate the dataset
../.venv/bin/python -m shiftlens.cli report [--date D]  # daily reports (metrics + flags + summary)
../.venv/bin/python -m shiftlens.cli monthly            # monthly analytics (correlations + findings)
../.venv/bin/python -m shiftlens.cli agents [--date D]  # agentic pass only: investigate flagged
                                                        # worker-days + write the monthly narrative
                                                        # (needs v1 artifacts; errors with a hint otherwise)
../.venv/bin/python -m shiftlens.cli demo               # whole pipeline + agentic pass on the
                                                        # first 3 flagged days (keeps the demo fast)
../.venv/bin/python -m shiftlens.cli demo --all-agents  # investigate every flagged day
../.venv/bin/python -m shiftlens.cli serve              # dashboard (FastAPI, port 8200, probes 8200-8209)
```

## Agentic workflow (v2)

The v1 pipeline answers *what happened*. The agentic layer
(`shiftlens/agents/` — roles, tools, orchestrator, verifier) answers *why —
and are we sure?*. A team of role agents works over the same deterministic
data; the LLM may plan and draft, but every number that reaches output is
either computed by a tool or verified against one. With no LLM, the same loop
runs on heuristic plans and template drafts.

### Roster

```
        task: a flagged worker-day, or the monthly review
                           │
                           ▼
                    ┌─────────────┐
                    │ orchestrator│  runs the loop, writes the trace
                    └──────┬──────┘
          ┌───────────┬────┴─────┬────────────┐
          ▼           ▼          ▼            ▼
      ┌────────┐ ┌────────────┐ ┌────────┐ ┌──────────┐
      │planner │ │investigator│ │drafter │ │ verifier │
      │ordered │ │executes    │ │prose   │ │the critic:│
      │tool-   │ │tool calls, │ │from    │ │recomputes│
      │call    │ │collects    │ │evidence│ │every     │
      │plan    │ │evidence    │ │only    │ │number    │
      └───┬────┘ └─────┬──────┘ └───┬────┘ └────┬─────┘
          └────────────┴── tool registry ───────┘
            get_worker_day · get_worker_history · compare_to_team
            get_environment_context · get_flag_rules · get_correlations
            get_findings · get_flagged_days
```

### The loop

For each task, the orchestrator runs **plan → investigate → draft → verify →
(revise once if rejected) → publish**:

1. **plan** — the planner turns the task into an ordered list of tool calls
   (LLM if available, else deterministic flag-driven heuristics: per flag,
   worker history + team comparison; environment context if a threshold
   crossed; always a recurrence check).
2. **investigate** — the investigator executes the calls and collects
   `{tool, args, result}` evidence items. Pure executor, no prose.
3. **draft** — the drafter writes the investigation note (or the monthly
   narrative) from the evidence only; the prompt forbids numbers that are
   not in the evidence.
4. **verify** — the verifier extracts every numeric claim from the draft
   (ints, decimals, percents) and re-computes each against tool data.
5. **revise** — on a failed verdict, the draft goes back once with the
   mismatch list.
6. **publish** — verified text is written out and traced.

### Tool registry

`agents/tools.py` — `TOOLS = {name: {"fn", "schema", "description"}}` — is the
only way agents read data. All eight tools are read-only and return JSON-able
dicts:

- `get_worker_day(date, worker_id)` — raw record + computed metrics + flags
- `get_worker_history(worker_id, last_n=7)` — per-day metrics/units/defects
- `compare_to_team(date, metric)` — worker value vs team mean that day
- `get_environment_context(date)` — env readings, crossed thresholds
  (noise > 85 dB, temperature > 28 °C), team deltas on those days
- `get_flag_rules()` — the deterministic flag rules (for the planner)
- `get_correlations()` / `get_findings()` — monthly analytics outputs
- `get_flagged_days(worker_id)` — every date the worker raised any flag

### The verifier: why the numbers can be trusted

The verifier is the trust mechanism. It extracts every numeric claim from a
draft, re-computes each value against tool data, and returns a pass/fail
verdict with a mismatch list. A failed draft gets exactly one revision; if it
still fails, the deterministic template text is published instead and the
trace records the fallback — honest degradation, never a silently wrong
number. The check runs identically with the LLM offline.

### Traces and outputs

Every task leaves a JSON trace — e.g. `out/traces/2026-09-01_W01.json` for a
worker-day investigation, `out/traces/monthly.json` for the monthly review —
capturing the task, plan, evidence, draft, verifier verdict, revision count,
published text, and whether the LLM was used. `demo` prints a compact
per-task trace summary; the smoke test asserts every trace has a plan,
evidence, and a verdict.

Outputs are additive (v1 artifacts unchanged): flagged daily reports gain an
`investigation` block (`likely_drivers`, `evidence`, `note`), and
`out/monthly.json` gains a verified `narrative` plus an `agentic` stats block
(`traces`, `verifier_pass_rate`, `revisions`). On the seeded reference run
the narrative is written over real findings — e.g. fatigue ↔ units at
r = −0.61 (n = 240) and "Days above 85 dB average 122% more defects per
worker than quieter days (5.8 vs 2.6)".
