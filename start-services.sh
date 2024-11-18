#!/bin/bash

# Colors for pretty output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Ensure we're in the script's directory
cd "$(dirname "$0")"

# Create data directory if it doesn't exist
mkdir -p ./data/redis

# Cleanup function
cleanup() {
    echo -e "\n${GREEN}Shutting down services...${NC}"
    
    # Kill the Flask application if it's running
    pkill -f "python app.py"
    
    # Stop and remove the Redis container (data persists in ./data/redis)
    if docker ps -q -f name=redis-counter >/dev/null; then
        echo "Stopping Redis container..."
        docker stop redis-counter >/dev/null 2>&1
        echo "Removing Redis container..."
        docker rm redis-counter >/dev/null 2>&1
    fi
    
    echo -e "${GREEN}Cleanup complete (Redis data preserved in ./data/redis)${NC}"
    exit 0
}

# Set up trap for cleanup on script exit
trap cleanup SIGINT SIGTERM

echo -e "${GREEN}Starting Counter Service Stack...${NC}"

# Create Redis volume if it doesn't exist
if ! docker volume ls | grep -q "redis-counter-data"; then
    echo -e "\n${GREEN}Creating Redis data volume...${NC}"
    docker volume create redis-counter-data
fi

# Check if Redis container is already running
if ! docker ps | grep -q "redis-counter"; then
    echo -e "\n${GREEN}Starting Redis...${NC}"
    docker run --name redis-counter \
        -p 6379:6379 \
        -v "$(pwd)/data/redis:/data" \
        -d redis:latest redis-server --appendonly yes
    
    # Wait for Redis to be ready
    sleep 2
else
    echo -e "\n${GREEN}Redis is already running...${NC}"
fi

# Check if Redis is responding
echo -e "\n${GREEN}Checking Redis connection...${NC}"
MAX_RETRIES=5
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec redis-counter redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}Redis is ready!${NC}"
        break
    fi
    echo "Waiting for Redis to be ready..."
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}Redis failed to start properly${NC}"
    exit 1
fi

# Start the Flask application
echo -e "\n${GREEN}Starting Flask application...${NC}"
source venv/bin/activate
export REDIS_HOST=localhost
export REDIS_PORT=6379
python app.py
