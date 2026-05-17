#!/bin/bash
set -e

source venv/bin/activate
export ENVIRONMENT=development

echo "  Starting F1 AI Platform — Local Mode"
echo "========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check .env
if [[ ! -f .env ]]; then
    echo -e "${RED}ERROR: .env not found. Run ./scripts/setup.sh first${NC}"
    exit 1
fi

# Load environment
export $(grep -v '^#' .env | xargs)

# Step 1: Initialize database (if needed)
echo -e "${YELLOW}[1/5] Checking database connection...${NC}"
python3 -c "
from src.utils.db import get_db
db = get_db()
if db.test_connection():
    print(' Database connected')
else:
    print(' Database connection failed')
    exit(1)
" || { echo -e "${RED}Database connection failed. Check .env credentials${NC}"; exit 1; }

# Step 2: Run schema (if tables don't exist)
echo -e "${YELLOW}[2/5] Ensuring database schema...${NC}"
python3 -c "
from src.utils.db import get_db
from sqlalchemy import text
db = get_db()
try:
    result = db.execute_query('SELECT 1 FROM races LIMIT 1')
    print(' Schema exists')
except:
    print(' Schema missing — run schema manually: psql \$DB_URL -f sql/schema_postgres.sql')
" || true

# Step 3: Ingest sample data (if empty)
echo -e "${YELLOW}[3/5] Checking data availability...${NC}"
python3 -c "
from src.utils.db import get_db
db = get_db()
result = db.execute_query('SELECT COUNT(*) as count FROM races')
count = result[0]['count'] if result else 0
if count == 0:
    print(' No race data found. Run data ingestion:')
    print('  python -m src.ingestion.ingest_ergast')
else:
    print(f' Found {count} races in database')
"

# Step 4: Train models (if missing)
echo -e "${YELLOW}[4/5] Checking ML models...${NC}"
if [[ ! -f artifacts/models/*_is_winner_*.pkl ]]; then
    echo " No trained models found. Training now..."
    python3 -c "
from src.models.train import F1ModelTrainer
trainer = F1ModelTrainer()
# Quick train on recent years
trainer.train_all_models(years=[2023, 2024, 2025])
print(' Models trained')
"
else
    echo " Models found in artifacts/models/"
fi

# Step 5: Start services
echo -e "${YELLOW}[5/5] Starting services...${NC}"
echo ""

# Start API server in background
echo -e "${BLUE}Starting FastAPI backend on http://localhost:8000${NC}"
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload --log-level info &
API_PID=$!

# Wait for API to be ready
sleep 3
if curl -s http://localhost:8000/health/live > /dev/null; then
    echo -e "${GREEN} API ready${NC}"
else
    echo -e "${RED} API failed to start${NC}"
    kill $API_PID 2>/dev/null
    exit 1
fi

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}   F1 AI Platform is running!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Services:"
echo "  API Docs:    http://localhost:8000/docs"
echo "  API Health:  http://localhost:8000/health"
echo "  Frontend:    http://localhost:3000 (start separately)"
echo ""
echo "To start frontend:"
echo "  cd src/frontend && npm install && npm run dev"
echo ""
echo "Press Ctrl+C to stop all services"

# Trap to clean up on exit
trap "kill $API_PID 2>/dev/null; echo -e '${YELLOW}Services stopped${NC}'; exit 0" INT TERM

wait