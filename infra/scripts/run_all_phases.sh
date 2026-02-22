#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="phases/state.md"
PROGRESS_FILE="logs/PROGRESS.md"

# -------------------------------
# Preflight: Docker
# -------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker not found."
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "[ERROR] Docker daemon is not running. Start Docker Desktop first."
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] docker compose not available."
  exit 1
fi

# -------------------------------
# Ensure state exists
# -------------------------------
if [[ ! -f "$STATE_FILE" ]]; then
  echo "[ERROR] Missing $STATE_FILE"
  exit 1
fi
mkdir -p logs

get_field() {
  local key="$1"
  grep -E "^- ${key}:" "$STATE_FILE" | sed -E "s/^- ${key}:[[:space:]]*//" || true
}

print_progress_tail() {
  if [[ -f "$PROGRESS_FILE" ]]; then
    echo ""
    echo "--------------------------------------------"
    echo "Progress (tail): $PROGRESS_FILE"
    echo "--------------------------------------------"
    tail -n 20 "$PROGRESS_FILE" || true
    echo "--------------------------------------------"
  fi
}

tag_for_phase() {
  # Input example: phase-06-reporting.md
  local phase_file="$1"
  if [[ -z "$phase_file" || "$phase_file" == "(none)" ]]; then
    return 0
  fi

  # Extract phase number from "phase-XX-..."
  # Works for phase-01, phase-02, ...
  local num
  num="$(echo "$phase_file" | sed -nE 's/^phase-([0-9]+)-.*$/\1/p')"
  if [[ -z "$num" ]]; then
    return 0
  fi

  # Turn "01" -> "0.1", "06" -> "0.6"
  # If you ever go beyond 09, adjust scheme.
  local minor="${num#0}"           # strip leading 0
  local tag="v0.${minor}-phase${num}"

  if git rev-parse "$tag" >/dev/null 2>&1; then
    echo "[INFO] Tag already exists: $tag"
  else
    git tag -a "$tag" -m "Milestone: $phase_file"
    echo "[INFO] Created tag: $tag"
  fi
}

final_done_tag() {
  local tag="v1.0-done"
  if git rev-parse "$tag" >/dev/null 2>&1; then
    echo "[INFO] Final tag already exists: $tag"
  else
    git tag -a "$tag" -m "All phases completed (DONE)"
    echo "[INFO] Created final tag: $tag"
  fi
}

# Read state BEFORE run
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

if [[ "$status" == "FAILED" ]]; then
  echo ""
  echo "⚠️  Last execution FAILED."
  echo "Failed Phase: ${last_failure}"
  echo "Error Summary: ${last_error}"
  print_progress_tail
  echo ""
  echo "Retry with:"
  echo "  ./infra/scripts/run_all_phases.sh"
  exit 0
fi

# -------------------------------
# Run Codex only if not DONE
# -------------------------------
if [[ "$status" != "DONE" ]]; then
  echo "[INFO] Starting / Resuming autonomous execution..."
  codex --full-auto \
"Read governance/AGENTS.md, phases/index.md, phases/state.md, phases/resume.md, phases/reporting.md, logs/PROGRESS.md.
Resume execution from phases/state.md current_phase and execute remaining phases sequentially in autonomous mode
with checkpoint updates, reporting generation, and strict Quality Gate enforcement."
else
  echo "[INFO] Status is DONE. Will not run Codex. Will commit/tag if needed."
fi

# Re-read state AFTER run (may have changed)
current_phase="$(get_field current_phase | tr -d '\r')"
last_success="$(get_field last_success_phase | tr -d '\r')"
status="$(get_field status | tr -d '\r')"

print_progress_tail

# -------------------------------
# Auto-commit if anything changed
# -------------------------------
if [[ -n "$(git status --porcelain)" ]]; then
  git add .
  git commit -m "Autonomous update (state=${status}, last_success=${last_success})"
  echo "[INFO] Auto-committed changes."
else
  echo "[INFO] No changes to commit."
fi

# -------------------------------
# Auto-tag milestone(s)
# -------------------------------
# Tag the latest success phase (milestone tag)
tag_for_phase "$(basename "${last_success:-}")"

# If DONE, also create final tag
if [[ "$status" == "DONE" ]]; then
  final_done_tag
fi

echo ""
echo "[INFO] Done. To push tags to GitHub:"
echo "  git push --follow-tags"
echo "or:"
echo "  git push origin --tags"
