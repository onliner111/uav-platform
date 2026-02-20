# Reporting Protocol (Required)

Codex MUST generate progress reports in `logs/`.

## On phase start (optional)
You MAY append a short entry to logs/PROGRESS.md:
- phase name
- start timestamp
- status: RUNNING

## On phase success (REQUIRED)
Create a per-phase report:

- File: logs/<phase-name>.report.md
- Content (keep concise):
  - Phase: <phase file name>
  - Status: SUCCESS
  - What was delivered (bullets)
  - How to verify (exact commands)
  - Demos (what to open / which endpoint)
  - Risks/Notes (<=5 bullets)
  - Key files changed (list paths only; no file plan)

Then update logs/PROGRESS.md:
- Mark phase as ✅
- Add link-style reference to the report filename (just the filename)

## On phase failure (REQUIRED)
Create a per-phase failure report:

- File: logs/<phase-name>.report.md
- Content:
  - Phase: <phase file name>
  - Status: FAILED
  - Failing command
  - Error excerpt (short)
  - Minimal human action (if any)
  - Retry instruction (run_all_phases.sh)

Then update logs/PROGRESS.md:
- Mark phase as ❌
- Add report filename

## Constraints
- Do not write long narratives.
- Do not include sensitive tokens.
- Do not output full diffs.