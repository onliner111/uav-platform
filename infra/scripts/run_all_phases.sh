#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="phases/state.md"
PROGRESS_FILE="logs/PROGRESS.md"

if [[ ! -f "$STATE_FILE" ]]; then
  echo "[ERROR] Missing $STATE_FILE"
  exit 1
fi

# Helpers
get_field() {
  local key="$1"
  # grabs everything after "key:"
  grep -E "^- ${key}:" "$STATE_FILE" | sed -E "s/^- ${key}:[[:space:]]*//" || true
}

print_progress_tail() {
  if [[ -f "$PROGRESS_FILE" ]]; then
    echo ""
    echo "--------------------------------------------"
    echo "Progress (tail): $PROGRESS_FILE"
    echo "--------------------------------------------"
    tail -n 30 "$PROGRESS_FILE" || true
    echo "--------------------------------------------"
  else
    echo ""
    echo "[INFO] No $PROGRESS_FILE yet."
  fi
}

# Read state
current_phase="$(get_field current_phase | tr -d '\r')"
last_success="$(get_field last_success_phase | tr -d '\r')"
last_failure="$(get_field last_failure_phase | tr -d '\r')"
status="$(get_field status | tr -d '\r')"
last_error="$(get_field last_error | tr -d '\r')"

echo "--------------------------------------------"
echo "Phase State:"
echo "  current_phase      : ${current_phase:-"(none)"}"
echo "  last_success_phase : ${last_success:-"(none)"}"
echo "  last_failure_phase : ${last_failure:-"(none)"}"
echo "  status             : ${status:-"(none)"}"
echo "--------------------------------------------"

# Ensure logs folder exists (for reporting)
mkdir -p logs

if [[ "${status:-}" == "DONE" ]]; then
  echo "[INFO] All phases completed successfully."
  print_progress_tail
  exit 0
fi

if [[ "${status:-}" == "FAILED" ]]; then
  echo ""
  echo "⚠️  Last execution FAILED."
  echo "Failed Phase: ${last_failure:-"(unknown)"}"
  echo ""

  # Try to locate failure report
  # Convention from phases/reporting.md: logs/<phase-name>.report.md
  report_file=""
  if [[ -n "${last_failure:-}" && "${last_failure}" != "(none)" ]]; then
    base="$(basename "$last_failure")"
    candidate="logs/${base}.report.md"
    if [[ -f "$candidate" ]]; then
      report_file="$candidate"
    fi
  fi

  if [[ -n "$report_file" ]]; then
    echo "Failure report: $report_file"
    echo "--------------------------------------------"
    # Print the first 120 lines (avoid dumping too much)
    sed -n '1,120p' "$report_file" || true
    echo "--------------------------------------------"
  else
    echo "[WARN] Failure report not found yet."
  fi

  if [[ -n "${last_error:-}" && "${last_error}" != "(none)" ]]; then
    echo ""
    echo "Error Summary (from state.md):"
    echo "${last_error}"
  fi

  print_progress_tail

  echo ""
  echo "Next actions:"
  echo "  - To retry (resume from current_phase): ./infra/scripts/run_all_phases.sh"
  echo "  - To inspect reports: ls -la logs/"
  exit 0
fi

echo "[INFO] Starting / Resuming autonomous execution..."
echo ""

# Run codex in resume + reporting mode
codex run "Read AGENTS.md, phases/index.md, phases/state.md, phases/resume.md, phases/reporting.md, logs/PROGRESS.md. Resume execution from phases/state.md current_phase and execute remaining phases sequentially in autonomous mode with checkpoint + reporting updates."

# After Codex run, print latest progress
print_progress_tail

echo ""
echo "[INFO] Run completed. If not DONE, re-run the script to continue/resume."
echo "  ./infra/scripts/run_all_phases.sh"