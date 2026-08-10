from app.database.database import (
    client,
    alerts_collection,
    decisions_collection,
    rewards_collection,
    evaluations_collection,
    training_collection,
)
from app.schemas.dashboard_schema import DashboardSummary


def get_enhanced_dashboard_summary() -> DashboardSummary:
    try:
        total_alerts = alerts_collection.count_documents({})
        total_decisions = decisions_collection.count_documents({})
        total_rewards = rewards_collection.count_documents({})
    except Exception:
        return DashboardSummary(
            total_alerts=0,
            processed_alerts=0,
            total_decisions=0,
            total_rewards=0,
            average_reward=0.0,
            average_latency=0.0,
            accuracy=0.0,
            database_status="unhealthy",
            training_status="unknown",
            current_episode=0,
        )

    pipeline = [{"$group": {"_id": None, "avg_reward": {"$avg": "$reward_value"}}}]
    avg_reward_res = list(rewards_collection.aggregate(pipeline))
    average_reward = float(avg_reward_res[0]["avg_reward"]) if avg_reward_res and avg_reward_res[0].get("avg_reward") is not None else 0.0

    avg_latency = 0.0
    accuracy = 0.0
    try:
        eval_pipeline = [{"$group": {"_id": None, "avg_latency": {"$avg": "$latency_ms"}, "avg_accuracy": {"$avg": "$accuracy"}}}]
        eval_res = list(evaluations_collection.aggregate(eval_pipeline))
        if eval_res:
            avg_latency = float(eval_res[0].get("avg_latency") or 0.0)
            accuracy = float(eval_res[0].get("avg_accuracy") or 0.0)
    except Exception:
        pass

    try:
        client.admin.command("ping")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    try:
        status_doc = training_collection.find_one({"type": "status"}, sort=[("updated_at", -1)])
        training_status = status_doc.get("status", "unknown") if status_doc else "idle"
        history_doc = training_collection.find_one({"type": "history"}, sort=[("epoch", -1)])
        current_episode = int(history_doc["epoch"]) if history_doc and history_doc.get("epoch") is not None else 0
    except Exception:
        training_status = "unknown"
        current_episode = 0

    return DashboardSummary(
        total_alerts=total_alerts,
        processed_alerts=total_decisions,
        total_decisions=total_decisions,
        total_rewards=total_rewards,
        average_reward=round(average_reward, 2),
        average_latency=round(avg_latency, 2),
        accuracy=round(accuracy, 4),
        database_status=db_status,
        training_status=training_status,
        current_episode=current_episode,
    )
