"""Tests for experiment orchestration and status reporting."""

from app.services.experiment_service import get_experiment_status, start_experiment_background


def test_experiment_status_is_available_for_unknown_run():
    status = get_experiment_status("does-not-exist")
    assert status["status"] == "not_found"


def test_experiment_background_starts_and_returns_run_id():
    response = start_experiment_background([
        {"name": "dqn_baseline", "learning_rate": 1e-3, "training_passes": 1},
    ])
    assert response["status"] == "started"
    assert response["run_id"]
