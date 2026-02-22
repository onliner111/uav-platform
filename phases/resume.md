# Resume Protocol (Autonomous)

## Goal
Execute all phases sequentially with checkpointing and resume support.

## Inputs
- governance/AGENTS.md
- phases/index.md
- phases/state.md
- phases/resume.md
- phases/reporting.md
- logs/PROGRESS.md

## Procedure
1) Read phases/state.md and locate `current_phase`.
2) Execute phases in phases/index.md order starting from `current_phase`.
3) After each phase, run the Quality Gate:
   - make lint
   - make typecheck
   - make test
   - make e2e (if exists)
4) If phase passes:
   - set last_success_phase = that phase
   - advance current_phase to the next phase in phases/index.md
   - set status=READY (or DONE if no next phase)
5) If phase fails after max 3 fix cycles:
   - set last_failure_phase = that phase
   - set status=FAILED
   - write last_error (short)
   - STOP
6) After each phase (success or failure), follow phases/reporting.md to write reports in logs/.

## Output Policy
Minimal output only (per governance/AGENTS.md).
