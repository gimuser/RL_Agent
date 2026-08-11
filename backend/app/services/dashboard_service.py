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
            total_alerts=None,
            processed_alerts=None,
            total_decisions=None,
            total_rewards=None,
            average_reward=None,
            average_latency=None,
            accuracy=None,
            database_status="UNAVAILABLE",
            training_status="UNKNOWN",
            current_episode=None,
        )

    pipeline = [{"$group": {"_id": None, "avg_reward": {"$avg": "$reward_value"}}}]
    avg_reward_res = list(rewards_collection.aggregate(pipeline))
    average_reward = (
        float(avg_reward_res[0]["avg_reward"])
        if avg_reward_res and avg_reward_res[0].get("avg_reward") is not None
        else None
    )

    avg_latency = None
    accuracy = None
    try:
        eval_pipeline = [{"$group": {"_id": None, "avg_latency": {"$avg": "$latency_ms"}, "avg_accuracy": {"$avg": "$accuracy"}}}]
        eval_res = list(evaluations_collection.aggregate(eval_pipeline))
        if eval_res:
            if eval_res[0].get("avg_latency") is not None:
                avg_latency = float(eval_res[0]["avg_latency"])
            if eval_res[0].get("avg_accuracy") is not None:
                accuracy = float(eval_res[0]["avg_accuracy"])
    except Exception:
        pass

    try:
        client.admin.command("ping")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    try:
        status_doc = training_collection.find_one({"type": "status"}, sort=[("updated_at", -1)])
        training_status = status_doc.get("status", "IDLE") if status_doc else "IDLE"
        history_doc = training_collection.find_one({"type": "history"}, sort=[("epoch", -1)])
        current_episode = int(history_doc["epoch"]) if history_doc and history_doc.get("epoch") is not None else None
    except Exception:
        training_status = "UNKNOWN"
        current_episode = None

    return DashboardSummary(
        total_alerts=total_alerts,
        processed_alerts=total_decisions,
        total_decisions=total_decisions,
        total_rewards=total_rewards,
        average_reward=round(average_reward, 2) if average_reward is not None else None,
        average_latency=round(avg_latency, 2) if avg_latency is not None else None,
        accuracy=round(accuracy, 4) if accuracy is not None else None,
        database_status=db_status,
        training_status=training_status,
        current_episode=current_episode,
    )
