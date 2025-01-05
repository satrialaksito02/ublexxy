#!/bin/bash

# Start or attach to a tmux session
SESSION_NAME="ublexxy"

# Check if tmux session exists
tmux has-session -t $SESSION_NAME 2>/dev/null

if [ $? != 0 ]; then
    echo "Starting new Userbot session..."
    tmux new-session -d -s $SESSION_NAME 'python3 /root/ublexxy/ub.py'
else
    echo "Attaching to existing Userbot session..."
fi

tmux attach -t $SESSION_NAME
