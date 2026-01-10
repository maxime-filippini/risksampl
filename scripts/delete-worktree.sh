#!/usr/bin/env bash

if [ $# -ne 1 ]; then
  echo "Error: Exactly one argument required"
  echo "Usage: $0 <worktree_name>"
  exit 1
fi

git branch -D feature/$1
git worktree remove $1
