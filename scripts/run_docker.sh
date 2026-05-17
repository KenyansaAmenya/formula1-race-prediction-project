#!/bin/bash
set -e

echo " Starting F1 AI Platform — Docker Mode"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check .env
if [[ ! -f .env ]]; then
    echo -e "${RED}ERROR: .env not found${NC}"
    exit 1
fi

# Build images
echo -e "${YELLOW}[1/3] Building Docker images...${NC}"
docker-compose build --no-cache

# Initialize data volume
echo -e "${YELLOW}[2/3] Preparing data volume...${NC}"
mkdir -p docker-data/models docker-data/metrics
cp -r artifacts/models/* docker-data/models/ 2>/dev/null || true

# Start stack
echo -e "${YELLOW}[3/3] Starting services...${NC}"
docker-compose up -d

# Wait for health checks
echo ""
echo "Waiting for services to be healthy..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health/live > /dev/null 2>&1; then
        echo -e "${GREEN} API healthy${NC}"
        break
    fi
    sleep 2
    echo -n "."
done

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}   F1 AI Platform is running!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Access points:"
echo "  Frontend:    http://localhost"
echo "  API:         http://localhost/api"
echo "  API Docs:    http://localhost/api/docs"
echo ""
echo "Commands:"
echo "  Logs:        docker-compose logs -f api"
echo "  Stop:        docker-compose down"
echo "  Restart:     docker-compose restart"