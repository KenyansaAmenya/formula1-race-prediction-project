# Formula 1 Race Prediction Platform

An end-to-end Formula 1 analytics platform for **data ingestion**, **feature engineering**, **machine learning model training**, and **real-time race prediction delivery** via a FastAPI backend and React frontend.
![Dashboard](dashbord.png)
---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Core Features](#core-features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Configuration](#environment-configuration)
  - [Install Dependencies](#install-dependencies)
- [Running the Project](#running-the-project)
  - [Option A: Local Development](#option-a-local-development)
  - [Option B: Docker Compose](#option-b-docker-compose)
- [Data & ML Workflow](#data--ml-workflow)
  - [1) Ingestion](#1-ingestion)
  - [2) Processing](#2-processing)
  - [3) Feature Engineering](#3-feature-engineering)
  - [4) Training](#4-training)
  - [5) Evaluation](#5-evaluation)
- [API Guide](#api-guide)
  - [Auth Endpoints](#auth-endpoints)
  - [Prediction Endpoints](#prediction-endpoints)
  - [Health Endpoints](#health-endpoints)
- [Frontend](#frontend)
- [Testing](#testing)
- [Configuration Reference](#configuration-reference)
- [Deployment Notes](#deployment-notes)
- [Security Notes](#security-notes)
- [Troubleshooting](#troubleshooting)
- [Roadmap Ideas](#roadmap-ideas)
- [License](#license)

---

## Overview

This project is designed as a production-style F1 prediction platform:

- Ingests race and telemetry-style data from multiple motorsport data sources.
- Cleans and transforms raw data into model-ready features.
- Trains multiple model families for tasks like:
  - winner prediction (`is_winner`)
  - podium/top-3 prediction (`is_top3`)
  - points prediction (`points`)
- Serves predictions through authenticated API endpoints.
- Provides a modern web frontend for dashboards and race insights.

---

## Architecture

High-level flow:

1. **Data ingestion** (`src/ingestion/*`) pulls raw F1 data.
2. **Processing + feature engineering** (`src/processing`, `src/features`) creates training datasets.
3. **Model training/evaluation** (`src/models`) generates artifacts and metrics.
4. **Prediction service** (`src/services/prediction_service.py`) loads models and performs inference.
5. **FastAPI app** (`src/api`) exposes auth/data/prediction/health endpoints.
6. **React frontend** (`src/frontend`) consumes API and renders analytics UI.

---

## Tech Stack

### Backend
- Python 3.11+
- FastAPI + Uvicorn
- Pydantic
- SQLAlchemy

### ML & Data
- Pandas / NumPy
- Scikit-learn
- XGBoost

### Frontend
- React + TypeScript + Vite
- TailwindCSS
- 3D/visual components under `src/frontend/src/components/three`

### Infrastructure
- Docker + Docker Compose
- Nginx
- Redis (optional profile)

---

## Repository Structure

```text
formula1-race-prediction-project/
├── app/
│   └── streamlit_app.py              # Phase 1 monitoring (legacy)
├── artifacts/
│   ├── models/                       # Serialized ML models
│   └── metrics/                      # Evaluation reports
├── config/
│   └── settings.yaml                 # Unified configuration
├── data/
│   ├── raw/
│   └── processed/
├── notebooks/
│   ├── 01_eda.ipynb                 # Exploratory analysis
│   ├── 02_feature_analysis.ipynb    # Feature validation
│   ├── 03_model_experiments.ipynb   # Model training
│   ├── 04_prediction_analysis.ipynb # Prediction review
│   └── 05_model_explainability.ipynb # SHAP analysis
├── sql/
│   └── schema_postgres.sql           # Database schema + RLS
├── src/
│   ├── api/
│   │   ├── main.py                   # FastAPI application
│   │   ├── middleware.py             # Logging & rate limiting
│   │   └── routes/
│   │       ├── auth.py              # JWT authentication
│   │       ├── predictions.py       # Prediction endpoints
│   │       ├── data.py              # Data endpoints
│   │       └── health.py            # Health checks
│   ├── frontend/                     # React 3D Application
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   ├── tailwind.config.js
│   │   ├── Dockerfile
│   │   └── src/
│   │       ├── main.tsx
│   │       ├── App.tsx
│   │       ├── index.css
│   │       ├── lib/
│   │       │   └── api.ts           # API client
│   │       ├── components/
│   │       │   ├── Layout.tsx
│   │       │   ├── Navigation.tsx
│   │       │   ├── three/
│   │       │   │   ├── F1Car.tsx
│   │       │   │   ├── DriverCard.tsx
│   │       │   │   ├── PodiumScene.tsx
│   │       │   │   └── BackgroundEffect.tsx
│   │       │   └── charts/
│   │       │       └── PredictionChart.tsx
│   │       └── pages/
│   │           ├── Dashboard.tsx
│   │           ├── Login.tsx
│   │           ├── RacePredictions.tsx
│   │           ├── DriverAnalysis.tsx
│   │           └── Leaderboard.tsx
│   ├── ingestion/
│   │   ├── base.py
│   │   ├── ingest_ergast.py
│   │   ├── ingest_openf1.py
│   │   └── ingest_fastf1.py
│   ├── models/
│   │   ├── train.py                 # ML training pipeline
│   │   └── evaluate.py              # Model evaluation
│   ├── processing/
│   │   └── clean_data.py
│   ├── features/
│   │   └── build_features.py
│   ├── services/
│   │   └── prediction_service.py    # Inference engine
│   ├── utils/
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── io_utils.py
│   │   ├── logger.py
│   │   └── security.py              # JWT & API key auth
│   └── validation/
│       └── __init__.py
├── tests/
│   ├── test_config.py
│   ├── test_ingestion.py
│   ├── test_processing.py
│   ├── test_features.py
│   ├── test_api.py                  # API endpoint tests
│   └── test_security.py             # Auth tests
├── .github/
│   └── workflows/
│       └── ci-cd.yml                # GitHub Actions
├── nginx.conf                       # Reverse proxy config
├── docker-compose.yml               # Full stack orchestration
├── Dockerfile                       # API container
├── requirements.txt
├── .env.example
├── .dockerignore
└── README.md
```

---

## Core Features

- Multi-source ingestion pipeline (Ergast/Jolpi, OpenF1, FastF1).
- Config-driven ML experiments with baseline and advanced models.
- JWT-based auth flow with refresh tokens.
- Prediction endpoints for individual drivers and full-race leaderboards.
- Health/liveness/readiness endpoints for operations and orchestration.
- Local + containerized execution paths.

---

## Getting Started

### Prerequisites

- Python 3.11 or newer
- Node.js 18+ and npm (for frontend)
- Docker + Docker Compose (optional, for container flow)
- PostgreSQL-compatible database credentials (Supabase pooler is configured by default in `settings.yaml`)

### Environment Configuration

1. Copy environment template:

```bash
cp .env.example .env
```

2. Fill required values in `.env` (at minimum):

- `DB_PASSWORD`
- `JWT_SECRET_KEY`
- `API_KEY` (if used in your flow)
- optional overrides such as `API_BASE_URL`, `REDIS_URL`, `LOG_LEVEL`

### Install Dependencies

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Frontend dependencies:

```bash
cd src/frontend
npm install
cd ../..
```

---

## Running the Project

### Option A: Local Development

You can use the helper script:

```bash
chmod +x scripts/run_local.sh
./scripts/run_local.sh
```

What it does:

1. Loads `.env`.
2. Tests DB connection.
3. Checks schema/data presence.
4. Triggers quick model training if artifacts are missing.
5. Starts FastAPI on `http://localhost:8000`.

To run frontend separately:

```bash
cd src/frontend
npm run dev
```

### Option B: Docker Compose

Start full stack:

```bash
docker compose up --build
```

Services exposed:

- API: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Nginx reverse proxy: `http://localhost`
- Redis (if enabled): `localhost:6379`

To include optional Redis profile:

```bash
docker compose --profile with-redis up --build
```

---

## Data & ML Workflow

### 1) Ingestion

Modules:

- `src/ingestion/ingest_ergast.py`
- `src/ingestion/ingest_openf1.py`
- `src/ingestion/ingest_fastf1.py`

Typical execution:

```bash
python -m src.ingestion.ingest_ergast
python -m src.ingestion.ingest_openf1
python -m src.ingestion.ingest_fastf1
```

### 2) Processing

```bash
python -m src.processing.clean_data
```

### 3) Feature Engineering

```bash
python -m src.features.build_features
```

### 4) Training

```bash
python -m src.models.train
```

### 5) Evaluation

```bash
python -m src.models.evaluate
```

Generated outputs:

- model binaries under `artifacts/models`
- metric reports under `artifacts/metrics`

---

## API Guide

FastAPI app entrypoint: `src/api/main.py`.

Interactive docs (non-production mode):

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Auth Endpoints

Base prefix: `/auth`

- `POST /auth/login` → returns access + refresh tokens.
- `POST /auth/refresh` → refreshes access token.
- `GET /auth/me` → returns current authenticated user context.
- `POST /auth/logout` → logout placeholder endpoint.

> Note: Current login route supports development-friendly behavior; tighten for production.

### Prediction Endpoints

Base prefix: `/predict`

- `POST /predict/driver`
  - Query params: `race_id`, `driver_id`, `model_type`, `target`
  - Returns prediction for one driver.
- `GET /predict/race/{race_id}`
  - Returns prediction set for a full race.
- `GET /predict/leaderboard/{race_id}`
  - Returns top-3 style leaderboard from race predictions.

### Health Endpoints

Base prefix: `/health`

- `GET /health/` → overall status response.
- `GET /health/live` → liveness probe.
- `GET /health/ready` → readiness with DB connectivity check.
- `GET /health/metrics` → placeholder operational metrics.

---

## Frontend

Frontend source: `src/frontend`.

Run in development mode:

```bash
cd src/frontend
npm run dev
```

Build for production:

```bash
npm run build
```

Core pages include:

- Dashboard
- Race Predictions
- Driver Analysis
- Leaderboard
- Login

---

## Testing

Run all tests:

```bash
pytest -q
```

Or run selected suites:

```bash
pytest tests/test_api.py -q
pytest tests/test_security.py -q
pytest tests/test_ingestion.py -q
```

---

## Configuration Reference

Primary config file: `config/settings.yaml`.

Major sections:

- `database`: DB host/user/pool settings.
- `api`: host/port/CORS/rate-limits/JWT settings.
- `ml`: model directories, targets, algorithms, hyperparameters.
- `ingestion`: per-source retry/timeout/rate-limit tuning.
- `storage`: raw/processed paths and serialization format.
- `processing`: null/duplication/timezone strategies.
- `features`: rolling/form windows.
- `logging`: level/format/retention.
- `security`: masking and query guardrails.

---

## Deployment Notes

- `Dockerfile` contains API production image stages.
- `docker-compose.yml` provides local multi-service orchestration.
- `nginx.conf` can be used for reverse proxying API/frontend.
- `render.yaml` and `vercel.json` indicate cloud deployment targets.

---

## Security Notes

Before production rollout:

- Replace development-friendly auth acceptance in `src/api/routes/auth.py` with strict credential validation.
- Ensure strong, rotated `JWT_SECRET_KEY` and DB credentials.
- Restrict CORS origins to trusted domains only.
- Keep rate limiting enabled and tuned.
- Apply schema + row-level-security policies from `sql/schema_postgres.sql`.

---

## Troubleshooting

- **`/health/ready` returns not ready**: verify DB credentials in `.env` and network access.
- **Prediction endpoint returns service unavailable**: ensure model artifacts exist and prediction service initializes correctly.
- **Frontend cannot reach backend**: verify `VITE_API_URL` and CORS config.
- **Docker startup issues**: inspect service logs with `docker compose logs -f api frontend`.

---

## Roadmap Ideas

- Add experiment tracking (MLflow / Weights & Biases).
- Add drift detection and automated retraining schedule.
- Add richer observability (Prometheus/Grafana/OpenTelemetry).
- Add role-based authorization beyond current basic role checks.
- Add CI gates for model quality thresholds.

---

## License

No license file is currently included in this repository.
