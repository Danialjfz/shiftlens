# ShiftLens

Agentic workforce analytics: daily worker data (sensors + micro-surveys +
object-detection events) → agent-authored daily reports → a monthly dashboard
correlating wellbeing and conditions with productivity.

**The LLM phrases; it never decides.** All metrics, flags, correlations and
findings are deterministic Python; an optional local LLM (LM Studio) only
rewrites prose.

## Quickstart

```bash
# from this directory, using the shared venv
../.venv/bin/python -m shiftlens.cli demo      # simulate 30 days, write
                                               # daily reports + monthly.json
../.venv/bin/python -m shiftlens.cli serve     # dashboard on http://127.0.0.1:8200
```

See `DESIGN.md` for the full architecture contract, `docs/` for the report,
technical specification, slide deck and video script.
