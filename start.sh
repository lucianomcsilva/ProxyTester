#!/bin/bash
# ProxyTester automatic initialization script
# Sets up Python virtual environment and launches FastAPI backend

set -e

# Terminal colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Starting ProxyTester ===${NC}"

# Navigate to backend directory
cd "$(dirname "$0")/backend"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment (.venv)...${NC}"
    python3 -m venv .venv
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source .venv/bin/activate

# Install/update dependencies
echo -e "${GREEN}Installing/updating dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Start uvicorn server
echo -e "${BLUE}Starting server on port 8000...${NC}"
echo -e "${YELLOW}Open your browser at: http://localhost:8000${NC}"
uvicorn main:app --host 0.0.0.0 --port 8000
