#!/usr/bin/env bash
set -euo pipefail

# Final verification script for government-style acceptance
# Runs the containerized quality gates + basic health checks.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "============================================"
echo "VERIFY ALL — Acceptance Gate"
echo "Repo: $ROOT_DIR"
echo "Time: $(date -Iseconds)"
echo "============================================"

fail() {
  echo ""
  echo "❌ FAILED: $1"
  exit 1
}

pass() {
  echo "✅ $1"
}

run_step() {
  local name="$1"
  shift
  local cmd=("$@")
  echo ""
  echo "--------------------------------------------"
  echo "STEP: $name"
  echo "CMD : ${cmd[*]}"
  echo "--------------------------------------------"
  if "${cmd[@]}"; then
    pass "$name"
  else
    fail "$name"
  fi
}

# 0) Preflight
command -v docker >/dev/null 2>&1 || fail "docker not found"
# Some environments use `docker compose` (plugin) rather than `docker-compose` (legacy)
docker compose version >/dev/null 2>&1 || fail "docker compose plugin not available"
pass "Preflight: docker + docker compose available"

# 1) Build + start (containerized)
run_step "docker compose up (build, detach)" docker compose up --build -d

# 2) Basic health checks (best-effort; don't fail if endpoints not exposed yet)
echo ""
echo "--------------------------------------------"
echo "STEP: Health checks (best-effort)"
echo "--------------------------------------------"
if command -v curl >/dev/null 2>&1; then
  set +e
  curl -fsS "http://localhost:8000/healthz" >/dev/null
  rc1=$?
  curl -fsS "http://localhost:8000/readyz" >/dev/null
  rc2=$?
  set -e
  if [[ $rc1 -eq 0 ]]; then pass "GET /healthz"; else echo "⚠️  WARN: /healthz not reachable"; fi
  if [[ $rc2 -eq 0 ]]; then pass "GET /readyz"; else echo "⚠️  WARN: /readyz not reachable"; fi
else
  echo "⚠️  WARN: curl not installed; skipping /healthz /readyz checks"
fi

# 3) Quality gates (prefer Makefile targets if present)
if [[ -f "Makefile" ]]; then
  run_step "make lint" make lint
  run_step "make typecheck" make typecheck
  run_step "make test" make test

  # e2e is optional; run only if target exists
  if make -n e2e >/dev/null 2>&1; then
    run_step "make e2e" make e2e
  else
    echo "⚠️  WARN: make e2e target not found; skipping"
  fi
else
  echo "⚠️  WARN: Makefile not found; falling back to docker compose run checks (limited)"
  # Fallback (adjust service name if needed)
  run_step "pytest (fallback)" docker compose -f infra/docker-compose.yml run --rm app pytest
fi

# 4) Show final status
echo ""
echo "============================================"
echo "✅ VERIFY ALL PASSED"
echo "Time: $(date -Iseconds)"
echo "============================================"

# Optional: print how to stop services
echo ""
echo "To stop services:"
echo "  docker compose down"