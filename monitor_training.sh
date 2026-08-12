#!/usr/bin/env bash
set -u

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
STATUS_URL="$BASE_URL/api/training-control"
INTERVAL="${INTERVAL:-3}"

while true; do
  clear
  echo "============================================================"
  echo " RL AGENT — LIVE TRAINING MONITOR"
  echo "============================================================"
  date '+TIME: %Y-%m-%d %H:%M:%S'
  echo

  JSON="$(curl -sf --max-time 3 "$STATUS_URL" 2>/dev/null || true)"

  if [ -z "$JSON" ]; then
    echo "API             : OFFLINE"
    echo "Backend         : $BASE_URL"
    echo
    echo "Start the project with: ./run_local.sh"
    sleep "$INTERVAL"
    continue
  fi

  JSON="$JSON" python3 - <<'PY'
import json
import os
import subprocess

data = json.loads(os.environ["JSON"])
results = data.get("results") or {}
training = results.get("training") or {}
dataset = results.get("dataset") or {}
comparison = results.get("comparison") or {}
live = results.get("live_inference") or {}
model = results.get("model") or {}

def show(value, default="—"):
    return default if value is None else value

def integer(value):
    if value is None:
        return "—"
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)

print(f"STATUS          : {data.get('status', 'unknown')}")
print(f"MESSAGE         : {data.get('message', '—')}")
print(f"RUN ID          : {show(results.get('run_id') or training.get('run_id'))}")

print("\n------------------------------------------------------------")
print(" TRAINING")
print("------------------------------------------------------------")
print(f"MODEL           : {show(training.get('model_name'))}")
print(f"ALGORITHM       : {show(training.get('display_name') or training.get('algorithm'))}")
print(f"CANDIDATE       : {show(training.get('candidate_index'))} / {show(training.get('candidate_count'))}")
selected = training.get("selected_models") or []
print(f"SELECTED        : {', '.join(selected) if selected else '—'}")
print(f"EPOCH           : {show(training.get('actual_epochs'))} / {show(training.get('epochs'))}")
print(f"BEST EPOCH      : {show(training.get('best_epoch'))}")
print(f"UPDATES         : {integer(training.get('total_updates_used'))}")
print(f"UPDATES/EPOCH   : {show(training.get('updates_per_epoch'))}")
print(f"POLICY REWARD   : {show(training.get('policy_reward'))}")
print(f"VALIDATION      : {show(training.get('validation_score'))}")
print(f"REWARD EFF.     : {show(training.get('reward_efficiency'))}")
print(f"PATIENCE        : {show(training.get('patience_used'))} / {show(training.get('patience'))}")
print(f"STOP REASON     : {show(training.get('stopping_reason'), 'learning')}")

print("\n------------------------------------------------------------")
print(" DATASET")
print("------------------------------------------------------------")
print(f"TRAIN ROWS      : {integer(dataset.get('train_rows'))}")
print(f"VALIDATION ROWS : {integer(dataset.get('validation_rows'))}")
print(f"TEST ROWS       : {integer(dataset.get('test_rows'))}")
print(f"TRAIN INCIDENTS : {integer(dataset.get('train_incidents'))}")
print(f"VAL INCIDENTS   : {integer(dataset.get('validation_incidents'))}")
print(f"TEST INCIDENTS  : {integer(dataset.get('test_incidents'))}")
print(f"OVERLAP         : {show(dataset.get('incident_overlap'))}")

print("\n------------------------------------------------------------")
print(" TELEMETRY")
print("------------------------------------------------------------")
history = training.get("history") or []
print(f"PERSISTED EPOCHS : {len(history)}")
if history:
    first, last = history[0], history[-1]
    print(f"FIRST EPOCH      : {show(first.get('epoch'))}")
    print(f"LATEST EPOCH     : {show(last.get('epoch'))}")
    print(f"LATEST LOSS      : {show(last.get('loss'))}")
    print(f"LATEST REWARD    : {show(last.get('policy_reward'))}")
    print(f"LATEST VALIDATION: {show(last.get('validation_score'))}")

print("\n------------------------------------------------------------")
print(" LIVE 40-ALERT CYCLE")
print("------------------------------------------------------------")
print(f"CYCLE           : {show(live.get('cycle_id') or live.get('decision_cycle_id'))}")
print(f"CONSIDERED      : {integer(live.get('alerts_considered'))}")
print(f"PROCESSED       : {integer(live.get('alerts_processed'))}")
print(f"HUMAN REVIEW    : {integer(live.get('human_review_routed'))}")
actions = live.get("action_distribution") or {}
print("ACTIONS         :", " | ".join(f"{k}={v}" for k, v in actions.items()) if actions else "waiting")

print("\n------------------------------------------------------------")
print(" MODEL COMPARISON")
print("------------------------------------------------------------")
print(f"STATUS          : {show(comparison.get('status'))}")
best = comparison.get("best")
if isinstance(best, dict):
    print(f"BEST MODEL      : {show(best.get('display_name') or best.get('algorithm') or best.get('name'))}")
    print(f"BEST SCORE      : {show(best.get('validation_score'))}")
else:
    print("BEST MODEL      : —")
    print("BEST SCORE      : —")

print("\n------------------------------------------------------------")
print(" MODEL")
print("------------------------------------------------------------")
print(f"EXISTS          : {show(model.get('exists'))}")
print(f"SIZE            : {integer(model.get('size_bytes'))} bytes")
print(f"PATH            : {show(model.get('path'))}")

print("\n------------------------------------------------------------")
print(" PROCESS")
print("------------------------------------------------------------")
pid = data.get("pid")
if pid:
    try:
        process = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "pid=,%cpu=,%mem=,rss=,etime="],
            text=True,
        ).strip()
        print("PROCESS         :", process or "not found")
    except Exception as exc:
        print("PROCESS         :", f"unavailable ({exc})")
else:
    print("PROCESS         : —")

print("\nCTRL+C = stop monitoring only; it does NOT stop training")
PY

  sleep "$INTERVAL"
done
