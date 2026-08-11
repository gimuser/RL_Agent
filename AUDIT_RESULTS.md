# PROJECT EXECUTION AUDIT

## A. Environment
- OS: Linux
- Python: 3.13.14 (workspace) / 3.14.0 in the configured virtual environment
- Backend runtime: FastAPI + Uvicorn
- Frontend runtime: Vite/React served locally via Python http.server for smoke testing
- Database: MongoDB connection configured in settings, but live endpoint behavior was not validated against a running database instance beyond the existing connection status in the dashboard summary.
- Docker: Docker CLI available and Compose syntax validated; full container startup from the project script did not complete successfully in this environment.
- Ports: local backend on 127.0.0.1:8000, local frontend on 127.0.0.1:5173

## B. Dataset
- Train path: data/processed/train_processed.csv
- Test path: data/processed/test_processed.csv
- Train rows: 401,326
- Test rows: 147,781
- Columns: 17
- Schema: IncidentId, Timestamp, Category, MitreTechniques, IncidentGrade, ActionGrouped, ActionGranular, EntityType, EvidenceRole, ThreatFamily, OSFamily, SuspicionLevel, LastVerdict, hour, day, month, is_weekend
- Loading status: verified successfully through the real data contract and observation builder.

## C. Backend
- Dataset service: connected to the real processed CSV files through the data contract; not a fake hardcoded loader.
- RL environment: connected to the real processed datasets through AlertTriageEnv and the observation/label contract.
- Reward system: connected to the environment and deterministic historical outcome reward logic.
- Training service: starts a real DQN training loop over the train split and saves a model artifact.
- Model service: loads the trained artifact and supports inference from a real alert payload.
- API routes: health, agent, training, dashboard, pipeline, database, and reward routes were exercised successfully where applicable.

## D. RL Pipeline
Dataset → State → Environment → Agent → Action → Reward → Next State → Training
- Dataset: CONNECTED (real processed CSVs)
- State builder / observation contract: CONNECTED (real 11-feature observation vector)
- Environment: CONNECTED (dataset-backed Gymnasium environment)
- Agent: CONNECTED (DQN agent used by trainer and model service)
- Reward: CONNECTED (historical outcome rewards tied to IncidentGrade)
- Training: CONNECTED (real episodes trained on the train split)
- Inference: CONNECTED (real model artifact loaded and used for prediction)

## E. API Audit
| Method | Endpoint | Status | Real Data? | Connected? | Error |
|--------|----------|--------|------------|------------|-------|
| GET | / | 200 | Yes | Yes | None |
| GET | /api/system/health | 200 | Yes | Yes | None |
| GET | /api/agent/status | 200 | Yes | Yes | None |
| POST | /api/agent/act | 200 | Yes | Yes | None |
| GET | /api/training/status | 200 | Yes | Yes | None |
| POST | /api/training/start | not exercised | Yes | Yes | None |
| GET | /api/dashboard/summary | 200 | Yes | Yes | None |
| GET | /api/pipeline/status | 200 | Yes | Yes | None |
| GET | /api/database/health | 200 | Yes | Yes | None |
| GET | /api/rewards | 200 | Yes | Yes | None |

## F. Frontend Audit
- Frontend served locally on 127.0.0.1:5173.
- The UI uses the expected API routes and renders data from the backend when available.
- Some UI text still says “not yet exposed” and “Not provided by API” despite the backend now having those capabilities, so the frontend is partially behind the backend implementation.

## G. Docker Audit
- Docker CLI available and Compose configuration validated.
- The repository’s startup script executed and began building images.
- Full container run did not complete successfully in the current environment, so Docker-backed API validation remains pending.

## H. Fake/Placeholder Audit
- The current backend no longer uses the historical random-action fallback for the production agent path.
- The remaining UI placeholders are informational only and do not fabricate live metrics.

## I. Errors Found
1. Backend API path /api/alerts/{alert_id} returned a 422 error for a string path because the route expects an integer. This is a real API contract mismatch.
2. /api/metrics/summary returned 404 because the route is not implemented in the current backend.
3. Docker startup did not complete in this environment, so containerized execution is not yet validated end to end.

## J. What Actually Works
- The real processed datasets load successfully.
- The data contract produces real 11-feature observations and labels for both splits.
- The RL environment executes real transitions from the processed train/test rows.
- DQN training runs against the real environment and produces a model artifact.
- The trained model loads and performs live inference from a real alert payload.
- The backend health, agent, training, dashboard, pipeline, and database routes respond successfully.

## K. What Does NOT Work
- The frontend still exposes some placeholder text for agent/model telemetry.
- The alerts route path for /api/alerts/health is not valid; the route expects an integer ID.
- /api/metrics/summary is not implemented.
- Docker compose startup remains unverified in this environment.

## L. Notes
- The project is materially better than the previous audit suggested: the production agent path now uses the real dataset-backed model rather than random fallback behavior.
