#!/usr/bin/env bash

SESSION="risksampl"

tmux has-session -t $SESSION 2>/dev/null

if [ $? == 0 ]; then
    tmux attach -t $SESSION
    exit
fi

tmux new-session -d -s $SESSION -n main
tmux new-window -t $SESSION -n server
tmux new-window -t $SESSION -n tailwind
tmux new-window -t $SESSION -n worker
tmux new-window -t $SESSION -n git
tmux select-window -t $SESSION:main

tmux attach -t $SESSION
