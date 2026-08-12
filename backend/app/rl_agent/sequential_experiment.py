from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from app.services.live_cycle_service import start_new_live_cycle
from app.services.live_inference_service import run_live_inference
from app.services.model_versioning import ensure_model_version

from .evaluator import evaluate
from .real_pipeline import (
    COMPARISON_PATH,
    EXPERIMENTS_DIR,
    MODEL_PATH,
    MODELS,
    TEST_METRICS_PATH,
    TRAIN_METRICS_PATH,
    _experiment_configs,
    _score,
    _write_comparison,
    build_incident_split,
)
from .trainer import train
from .triage_env import FEATURES


def _int_env(name: str, default: int) -> int:
    import os
    return int(os.getenv(name, str(default)))


def _float_env(name: str, default: float) -> float:
    import os
    return float(os.getenv(name, str(default)))


def _write_live_candidate_metrics(config: dict[str, Any], result: dict[str, Any], index: int, count: int) -> None:
    payload = {
        "config": {
            **config,
            "candidate_index": index,
            "candidate_count": count,
            "features": FEATURES,
            "synthetic_data": False,
            "real_data": True,
            "early_stopping": True,
            "experiment_mode": "sequential_model_then_live_cycle",
        },
        "metrics": result.get("metrics", []),
        "best_epoch": result.get("best_epoch"),
        "actual_epochs": result.get("actual_epochs"),
        "total_updates_used": result.get("total_updates_used"),
        "updates_per_epoch": result.get("updates_per_epoch"),
        "max_total_updates": result.get("max_total_updates"),
    }
    TRAIN_METRICS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    import os

    print("=" * 78)
    print("SEQUENTIAL MODEL -> FRESH 40-ALERT LIVE EVALUATION")
    print("=" * 78)

    train_csv, validation_csv, test_csv = build_incident_split()
    max_epochs = _int_env("REAL_RL_MAX_EPOCHS", 4000)
    min_epochs = _int_env("REAL_RL_MIN_EPOCHS", 50)
    patience = _int_env("REAL_RL_PATIENCE", 30)
    min_delta = _float_env("REAL_RL_MIN_DELTA", 1e-3)
    seed = _int_env("REAL_RL_SEED", 42)
    target_update = _int_env("REAL_RL_TARGET_UPDATE", 1)

    configs = _experiment_configs()
    comparison_records: list[dict[str, Any]] = []
    _write_comparison([], None, "running")

    for index, config in enumerate(configs, start=1):
        name = str(config.get("name") or f"candidate_{index}")
        learning_rate = float(config.get("learning_rate", 1e-3))
        gamma = float(config.get("gamma", 0.95))
        batch_size = int(config.get("batch_size", 512))
        candidate_path = EXPERIMENTS_DIR / f"{name}.pt"

        print("\n" + "=" * 78)
        print(f"MODEL {index}/{len(configs)}: {name}")
        print("=" * 78)

        def on_progress(row: dict[str, Any]) -> None:
            _write_live_candidate_metrics(
                {
                    "model_name": name,
                    "learning_rate": learning_rate,
                    "gamma": gamma,
                    "batch_size": batch_size,
                    "max_epochs": max_epochs,
                    "min_epochs": min_epochs,
                    "patience": patience,
                    "min_delta": min_delta,
                },
                {"metrics": [row], "actual_epochs": row.get("epoch"), "best_epoch": row.get("best_epoch"), "total_updates_used": row.get("total_updates"), "updates_per_epoch": row.get("updates_per_epoch"), "max_total_updates": max_epochs * max(1, int(row.get("updates_per_epoch") or 0))},
                index,
                len(configs),
            )

        model, result = train(
            train_csv=train_csv,
            validation_csv=validation_csv,
            epochs=max_epochs,
            min_epochs=min_epochs,
            patience=patience,
            min_delta=min_delta,
            batch_size=batch_size,
            learning_rate=learning_rate,
            gamma=gamma,
            target_update=target_update,
            seed=seed + index - 1,
            checkpoint_path=str(candidate_path),
            progress_callback=on_progress,
        )

        candidate_config = {
            "model_name": name,
            "learning_rate": learning_rate,
            "gamma": gamma,
            "batch_size": batch_size,
            "max_epochs": max_epochs,
            "min_epochs": min_epochs,
            "patience": patience,
            "min_delta": min_delta,
        }
        _write_live_candidate_metrics(candidate_config, result, index, len(configs))

        best_validation = result.get("best_validation") or {}
        candidate = {
            "name": name,
            "algorithm": str(config.get("algorithm", "DoubleDQN")),
            "learning_rate": learning_rate,
            "gamma": gamma,
            "batch_size": batch_size,
            "actual_epochs": int(result.get("actual_epochs", 0)),
            "best_epoch": int(result.get("best_epoch", 0)),
            "best_validation": best_validation,
            "validation_score": _score({"best_validation": best_validation}),
            "model_path": str(candidate_path),
            "status": "trained",
        }

        # Every trained candidate receives a completely fresh 40-alert cycle.
        cycle = start_new_live_cycle(
            reason=f"model_candidate_{index}",
            metadata={"model_name": name, "candidate_index": index, "candidate_count": len(configs)},
        )

        # Candidate becomes temporarily active so the live inference engine
        # uses exactly this checkpoint and gets its own model version.
        shutil.copy2(candidate_path, MODEL_PATH)
        candidate_meta = ensure_model_version(
            model_path=MODEL_PATH,
            model_name=name,
            extra={
                "candidate_index": index,
                "candidate_count": len(configs),
                "best_epoch": candidate["best_epoch"],
                "actual_epochs": candidate["actual_epochs"],
                "learning_rate": learning_rate,
                "decision_cycle_id": cycle["cycle_id"],
            },
        )
        live = run_live_inference(only_uninferred=True)
        candidate["model_version"] = candidate_meta.get("model_version")
        candidate["live_cycle_id"] = cycle["cycle_id"]
        candidate["live_inference"] = live

        comparison_records.append(candidate)
        comparison_records.sort(key=lambda item: float(item.get("validation_score", 0.0)), reverse=True)
        _write_comparison(comparison_records, comparison_records[0], "running")
        (EXPERIMENTS_DIR / f"{name}.training.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        (EXPERIMENTS_DIR / f"{name}.live.json").write_text(json.dumps({"cycle": cycle, "inference": live, "model": candidate_meta}, indent=2, default=str), encoding="utf-8")

        print(f"[LIVE] {name}: cycle={cycle['cycle_id']} actions={live.get('action_distribution')}")
        print(f"[LIVE] Human-review routed={live.get('human_review_routed', 0)}")
        del model

    if not comparison_records:
        raise RuntimeError("No model candidates completed.")

    best = comparison_records[0]
    best_path = Path(best["model_path"])
    if not best_path.exists():
        raise RuntimeError(f"Best model checkpoint missing: {best_path}")

    # Promote winner and run one final clean champion cycle.
    shutil.copy2(best_path, MODEL_PATH)
    final_cycle = start_new_live_cycle(
        reason="champion_model",
        metadata={"winner": best["name"], "selection_score": best["validation_score"]},
    )
    champion_meta = ensure_model_version(
        model_path=MODEL_PATH,
        model_name=str(best.get("algorithm") or best["name"]),
        extra={
            "winner_name": best["name"],
            "selection_score": best["validation_score"],
            "best_epoch": best["best_epoch"],
            "actual_epochs": best["actual_epochs"],
            "decision_cycle_id": final_cycle["cycle_id"],
        },
    )
    champion_live = run_live_inference(only_uninferred=True)

    _write_comparison(comparison_records, {**best, "status": "CHAMPION", "model_version": champion_meta.get("model_version"), "live_cycle_id": final_cycle["cycle_id"], "live_inference": champion_live}, "selected")

    final_metrics = evaluate(test_csv=test_csv, model_path=str(MODEL_PATH))
    TEST_METRICS_PATH.write_text(json.dumps(final_metrics, indent=2), encoding="utf-8")

    selected_history = json.loads((EXPERIMENTS_DIR / f"{best['name']}.training.json").read_text(encoding="utf-8"))
    selected_config = selected_history.get("config", {})
    selected_config.update({
        "model_name": best["name"],
        "algorithm": best.get("algorithm", "DoubleDQN"),
        "candidate_count": len(comparison_records),
        "selected": True,
        "selection_score": best["validation_score"],
        "selection_rule": "validation only; final unseen test evaluation after champion selection",
        "experiment_mode": "sequential_model_then_live_cycle",
    })
    TRAIN_METRICS_PATH.write_text(json.dumps({
        "config": selected_config,
        "metrics": selected_history.get("metrics", []),
        "best_epoch": best["best_epoch"],
        "actual_epochs": best["actual_epochs"],
        "best_validation": best["best_validation"],
        "total_updates_used": selected_history.get("total_updates_used"),
        "updates_per_epoch": selected_history.get("updates_per_epoch"),
        "max_total_updates": selected_history.get("max_total_updates"),
        "model_comparison": comparison_records,
        "champion_model_version": champion_meta.get("model_version"),
        "champion_live_cycle": final_cycle,
        "champion_live_inference": champion_live,
    }, indent=2, default=str), encoding="utf-8")

    print("\n" + "=" * 78)
    print("SEQUENTIAL EXPERIMENT COMPLETE")
    print("=" * 78)
    print(f"Winner             : {best['name']}")
    print(f"Champion version   : {champion_meta.get('model_version')}")
    print(f"Champion cycle     : {final_cycle['cycle_id']}")
    print(f"Final live actions  : {champion_live.get('action_distribution')}")
    print(f"Human review routed : {champion_live.get('human_review_routed', 0)}")
    print("=" * 78)


if __name__ == "__main__":
    main()
