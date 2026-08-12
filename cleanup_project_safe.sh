#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$ROOT/backups/cleanup_$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_DIR="$ROOT/reports/cleanup_master"
LOG="$REPORT_DIR/cleanup.log"
APPLY=0
FORCE=0

usage() {
  cat <<'EOF'
RL AGENT — SAFE PROJECT CLEANER

Default mode is AUDIT ONLY. No source code is deleted.

Usage:
  ./cleanup_project_safe.sh              # audit + dry-run
  ./cleanup_project_safe.sh --apply      # perform safe cleanup
  ./cleanup_project_safe.sh --force --apply

Safety guarantees:
- Never deletes backend/app/* or frontend/src/* merely because a file looks old.
- Never deletes .git, .venv, node_modules, datasets, models, checkpoints, or runtime code.
- Creates a backup manifest and git patch before changes.
- Refuses source cleanup when backend/frontend source is already uncommitted unless --force is supplied.
- Runs Python syntax, FastAPI import, frontend build, and active RL/live-path imports after cleanup.
- Source-code consolidation is reported separately and is NOT auto-deleted.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --force) FORCE=1 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; usage; exit 2 ;;
  esac
done

mkdir -p "$BACKUP_DIR" "$REPORT_DIR"
: > "$LOG"
exec > >(tee -a "$LOG") 2>&1

say() { printf '\n==> %s\n' "$1"; }
warn() { printf '[WARN] %s\n' "$1"; }
ok() { printf '[OK] %s\n' "$1"; }

cd "$ROOT"

say "PROJECT SAFETY CHECK"
printf 'Repository : %s\n' "$ROOT"
printf 'Commit     : %s\n' "$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
printf 'Branch     : %s\n' "$(git branch --show-current 2>/dev/null || echo unknown)"
printf 'Mode       : %s\n' "$([ "$APPLY" -eq 1 ] && echo APPLY || echo AUDIT-ONLY)"

say "BACKUP CURRENT STATE"
git status --short > "$BACKUP_DIR/git_status_before.txt" || true
git diff > "$BACKUP_DIR/working_tree.patch" || true
git diff --cached > "$BACKUP_DIR/index.patch" || true
git ls-files -s > "$BACKUP_DIR/index.txt" || true

if [ "$FORCE" -eq 0 ]; then
  if git status --porcelain | grep -Eq '^[ MARCUD?]{1,2} (backend/|frontend/src/)'; then
    warn "Uncommitted backend/frontend source changes detected. Refusing automatic source cleanup."
    warn "Use --force only after you have backed up your work."
    exit 1
  fi
fi

say "SAFE GENERATED-CONTENT CLEANUP CANDIDATES"
SAFE_DELETE=()

while IFS= read -r f; do
  [ -n "$f" ] && SAFE_DELETE+=("$f")
done < <(find reports -maxdepth 2 -type f \( -name 'full_redundancy_audit.txt' -o -path 'reports/redundancy_parts/*' -o -path 'reports/cleanup_stage_01/*' \) 2>/dev/null | sort)

for f in \
  FINAL_STABILIZE_PROJECT.py \
  watch_training.sh \
  create_personal_repo.sh \
  audit_redundant_code.sh \
  audit_redundancy_full.sh; do
  [ -f "$f" ] && SAFE_DELETE+=("$f")
done

PROTECTED=(
  run_local.sh
  monitor_training.sh
  cleanup_project_safe.sh
  backend
  frontend
  data
  models
  requirements.txt
  package.json
)

for f in "${SAFE_DELETE[@]}"; do
  protected=0
  for p in "${PROTECTED[@]}"; do
    [ "$f" = "$p" ] && protected=1
  done
  if [ "$protected" -eq 1 ]; then
    warn "Protected: $f"
  else
    printf '[CANDIDATE] %s\n' "$f"
  fi
done

say "SOURCE-CODE REDUNDANCY ANALYSIS (NO AUTO DELETE)"
python3 - <<'PY' | tee "$REPORT_DIR/source_redundancy_candidates.txt"
from pathlib import Path
import ast
from collections import defaultdict

root = Path("backend/app")
classes = defaultdict(list)
functions = defaultdict(list)

for p in root.rglob("*.py"):
    if any(x in p.parts for x in ("__pycache__", ".venv")):
        continue
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"PARSE_ERROR {p}: {exc}")
        continue
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef):
            classes[n.name].append(str(p))
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[n.name].append(str(p))

print("DUPLICATE CLASS NAMES")
for name, paths in sorted(classes.items()):
    if len(paths) > 1:
        print(name)
        for p in paths:
            print(f"  {p}")

print("\nDUPLICATE FUNCTION NAMES")
for name, paths in sorted(functions.items()):
    if len(paths) > 1:
        print(name)
        for p in paths:
            print(f"  {p}")
PY

say "KNOWN ENVIRONMENT CONSOLIDATION CHECK"
if [ -f backend/app/rl_agent/triage_env.py ] && [ -f backend/app/environment/triage_env.py ]; then
  printf '[REVIEW] Two triage modules exist.\n'
  printf '  active environment: backend/app/environment/triage_env.py\n'
  printf '  legacy data helper : backend/app/rl_agent/triage_env.py\n'
  printf '  The legacy helper is NOT deleted automatically.\n'
  printf '  Live inference currently imports ACTIONS/FEATURES from it; refactor first.\n'
fi

say "SAFE DELETE EXECUTION"
if [ "$APPLY" -eq 0 ]; then
  echo "AUDIT-ONLY: nothing will be deleted."
else
  for f in "${SAFE_DELETE[@]}"; do
    protected=0
    for p in "${PROTECTED[@]}"; do
      [ "$f" = "$p" ] && protected=1
    done
    if [ "$protected" -eq 1 ]; then
      continue
    fi
    if [ -e "$f" ]; then
      mkdir -p "$BACKUP_DIR/files/$(dirname "$f")"
      cp -a "$f" "$BACKUP_DIR/files/$f"
      rm -rf -- "$f"
      printf '[DELETED] %s\n' "$f"
    fi
  done
fi

say "VALIDATION"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then PYTHON_BIN="python3"; fi

"$PYTHON_BIN" -m py_compile \
  backend/app/services/authoritative_training_control.py \
  backend/app/rl_agent/sequential_experiment.py \
  backend/app/rl_agent/trainer.py \
  backend/app/services/live_inference_service.py
ok "Python syntax"

PYTHONPATH="$ROOT/backend" "$PYTHON_BIN" -c 'import main; print("[OK] FastAPI import")'
ok "FastAPI import"

if [ -d frontend ] && [ -f frontend/package.json ]; then
  (cd frontend && npm run build)
  ok "Frontend build"
fi

PYTHONPATH="$ROOT/backend" "$PYTHON_BIN" - <<'PY'
from app.environment.triage_env import RealTriageEnv, FEATURE_COLUMNS
from app.services.live_inference_service import get_inference_status
from app.rl_agent.offline_algorithms import algorithm_metadata
print('[OK] Active environment import')
print('[OK] Feature contract:', len(FEATURE_COLUMNS), 'features')
print('[OK] Live inference import')
for name in ('double_dqn', 'cql', 'iql', 'bcq'):
    algorithm_metadata(name)
    print('[OK]', name)
PY

say "POST-CLEANUP SAFETY SUMMARY"
cat "$BACKUP_DIR/git_status_before.txt" || true
printf '\nBackup: %s\n' "$BACKUP_DIR"
printf 'Report : %s\n' "$REPORT_DIR/source_redundancy_candidates.txt"

if [ "$APPLY" -eq 1 ]; then
  say "CLEANUP COMPLETED"
  echo "Only explicitly safe/generated artifacts were removed."
  echo "Application source was not deleted automatically."
else
  say "AUDIT COMPLETED"
  echo "Run with --apply only after reviewing the candidate list."
fi
