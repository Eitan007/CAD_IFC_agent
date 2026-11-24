#!/bin/bash

# ==============================================================================
# BIM/CAD Agent Development Environment Starter
# ==============================================================================
# This script uses tmux to open two panes in a single terminal session:
# 1. Frontend (Vite)
# 2. BIM Assistant Backend (FastAPI)
#
# It also opens the frontend in your default browser.
# ==============================================================================

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="bim_dev"

# Check for tmux
if ! command -v tmux &> /dev/null; then
    echo "Error: tmux is not installed. Please install it with: sudo apt install tmux"
    exit 1
fi

# The local API is configured to use Neo4j at localhost:7687.  Compose starts
# that database in Docker and waits for its health check before we start the API.
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not available in this WSL terminal."
    exit 1
fi

echo "Starting Neo4j database..."
if ! (cd "$REPO_ROOT/bim_assistant" && docker compose up -d --wait neo4j); then
    echo "Error: Neo4j could not start. Make sure Docker Desktop is running, then try again."
    exit 1
fi

# Kill existing session if it exists to start fresh
tmux kill-session -t $SESSION 2>/dev/null

echo "Starting BIM/CAD Agent services in tmux session: $SESSION..."

# 1. Create session and start the frontend in the first pane
tmux new-session -d -s $SESSION -n 'dev'
tmux set-option -t $SESSION mouse on
tmux send-keys -t $SESSION:0 "cd $REPO_ROOT/frontend && npm run dev" C-m

# 2. Split vertically for the backend API
tmux split-window -v -t $SESSION:0
tmux send-keys -t $SESSION:0.1 "cd $REPO_ROOT/bim_assistant && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" C-m

# Open the browser (using explorer.exe for WSL -> Windows integration)
# We run this in the background with a slight delay to allow Vite to initialize.
(sleep 5 && explorer.exe "http://localhost:5173" 2>/dev/null) &

# Finalize layout and attach
tmux select-layout -t $SESSION:0 tiled
echo "Services starting. Attaching to tmux..."
sleep 1
tmux attach-session -t $SESSION
