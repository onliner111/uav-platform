#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="phases/state.md"
PROGRESS_FILE="logs/PROGRESS.md"

# ------------------------------------------------------------
# Preflight: Docker
# ------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker not found."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "[ERROR] Docker daemon is not running."
  echo "Start Docker Desktop first."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] docker compose not available."
  exit 1
fi

# ------------------------------------------------------------
# Check state file
# ------------------------------------------------------------
if [[ ! -f "$STATE_FILE" ]]; then
  echo "[ERROR] Missing $STATE_FILE"
  exit 1
fi

mkdir -p logs

get_field() {
  local key="$1"
  grep -E "^- ${key}:" "$STATE_FILE" | sed -E "s/^- ${key}:[[:space:]]*//" || true
}

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

if [[ "$status" == "DONE" ]]; then
  echo "[INFO] All phases already completed."
  exit 0
fi

if [[ "$status" == "FAILED" ]]; then
  echo ""
  echo "⚠️  Last execution FAILED."
  echo "Failed Phase: $last_failure"
  echo ""
  echo "Error Summary:"
  echo "$last_error"
  echo ""
  echo "Run again to retry:"
  echo "./infra/scripts/run_all_phases.sh"
  exit 0
fi

echo "[INFO] Starting / Resuming autonomous execution..."
echo ""

# ------------------------------------------------------------
# 🔥 FULL AUTO MODE
# ------------------------------------------------------------
codex --full-auto \
"Read AGENTS.md, phases/index.md, phases/state.md, phases/resume.md, phases/reporting.md, logs/PROGRESS.md.
Resume execution from phases/state.md current_phase and execute remaining phases sequentially in autonomous mode
with checkpoint updates, reporting generation, and strict Quality Gate enforcement."

# ------------------------------------------------------------
# Auto Git Commit (only if changes exist)
# ------------------------------------------------------------
if [[ -n $(git status --porcelain) ]]; then
  git add .
  git commit -m "Phase progress: ${current_phase} auto-update"
  echo "[INFO] Changes committed for ${current_phase}"
else
  echo "[INFO] No changes to commit."
fi

echo ""
echo "[INFO] Run finished."
echo "If not DONE, re-run:"
echo "./infra/scripts/run_all_phases.sh"