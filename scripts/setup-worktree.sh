#!/usr/bin/env bash

if [ $# -ne 2 ]; then
  echo "Error: Exactly two arguments required"
  echo "Usage: $0 <branch_name> <worktree_name>"
  exit 1
fi

BRANCH_NAME=$1
WORKTREE_NAME=$2
WT_PATH=".worktrees/$2"

git worktree add -b $BRANCH_NAME $WT_PATH
cp .env $WT_PATH

cd $WT_PATH
cp .env ./web/.env
cp .env ./worker/.env

bun i
bun run web:setup
bun run worker:setup
