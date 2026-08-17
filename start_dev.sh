#!/bin/bash

# ==============================================================================
# BIM/CAD Agent Development Environment Starter
# ==============================================================================
# This script uses tmux to open three panes in a single terminal session:
# 1. LiveKit Voice Agent
# 2. Frontend (Vite)
# 3. BIM Assistant Backend (FastAPI)
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

# Kill existing session if it exists to start fresh
tmux kill-session -t $SESSION 2>/dev/null

echo "Starting BIM/CAD Agent services in tmux session: $SESSION..."

# 1. Create session and start Voice Agent in the first pane
tmux new-session -d -s $SESSION -n 'dev'
tmux set-option -t $SESSION mouse on
tmux send-keys -t $SESSION:0 "cd $REPO_ROOT/livekit-voice-agent && source .venv/bin/activate && export BIM_API_BASE=http://127.0.0.1:8000 && uv run agent.py dev" C-m

# 2. Split vertically for the Frontend
tmux split-window -v -t $SESSION:0
tmux send-keys -t $SESSION:0.1 "cd $REPO_ROOT/frontend && npm run dev" C-m

# 3. Split horizontally for the Backend API
tmux split-window -h -t $SESSION:0.1
tmux send-keys -t $SESSION:0.2 "cd $REPO_ROOT/bim_assistant && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000" C-m

# Open the browser (using explorer.exe for WSL -> Windows integration)
# We run this in the background with a slight delay to allow Vite to initialize.
(sleep 5 && explorer.exe "http://localhost:5173" 2>/dev/null) &

# Finalize layout and attach
tmux select-layout -t $SESSION:0 tiled
echo "Services starting. Attaching to tmux..."
sleep 1
tmux attach-session -t $SESSION
