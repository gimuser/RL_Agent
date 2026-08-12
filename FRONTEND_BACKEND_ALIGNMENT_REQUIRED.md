# Frontend / Backend Alignment Required

The authoritative backend entrypoint is:

- backend/main.py

The authoritative health endpoint is:

- /api/system/health

The authoritative real RL training endpoints are:

- GET /api/training/status
- POST /api/training/full-real-training
- GET /api/training/full-real-training/status

Authoritative real artifacts:

- models/real_dqn_agent.pt
- models/training_metrics.json
- models/real_test_metrics.json
- models/test_predictions.csv
- models/real_test_predictions.jsonl

Authoritative real datasets:

- data/rl_incident/train_incident.csv
- data/rl_incident/test_incident.csv

Do NOT hardcode model metrics into the frontend.

The frontend should consume the backend's real:

- training status
- training history
- checkpoint information
- evaluation metrics
- decisions
- rewards
- dashboard data

Before modifying frontend behavior, compare the exact backend schemas and
routes with:

Backend:
- backend/app/api/training.py
- backend/app/api/router.py
- backend/app/services/training_service.py
- backend/app/services/experiment_service.py
- backend/app/services/model_service.py
- backend/app/schemas/training_schema.py
- backend/main.py

Frontend:
- frontend/src/pages/Training.tsx
- frontend/src/pages/History.tsx
- frontend/src/pages/Decisions.tsx
- frontend/src/pages/Dashboard.tsx
- frontend/src/services/training.service.ts
- frontend/src/services/decisions.service.ts
- frontend/src/services/dashboard.service.ts
- frontend/src/types/domain.ts
- frontend/src/types/api.ts
