set -e

echo "🏎️  F1 AI Platform Starting..."
echo "=============================="

# Export environment for supervisord
export PATH="/root/.local/bin:$PATH"
export PYTHONPATH="/app"
export ENVIRONMENT="production"

# Ensure log directory exists
mkdir -p /app/logs

# Verify backend is importable
python3 -c "from src.api.main import app; print('✓ FastAPI import OK')" || {
    echo "✗ FastAPI import failed"
    exit 1
}

# Start supervisord (manages nginx + uvicorn)
echo "Starting services via supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf