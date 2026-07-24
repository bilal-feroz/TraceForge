#!/usr/bin/env bash
set -euo pipefail

scenario="${1:-lock}"
profile="${2:-demo}"
case "$scenario" in
  lock|latency|control) ;;
  *) echo "scenario must be lock, latency, or control" >&2; exit 2 ;;
esac
case "$profile" in
  quick|demo|full) ;;
  *) echo "profile must be quick, demo, or full" >&2; exit 2 ;;
esac

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export TRACEFORGE_TRUSTED_LOCAL_MODE=true
cd "$repository_root"
uv run python scripts/bootstrap_demo_repo.py
uv run traceforge demo "$scenario" --profile "$profile"
