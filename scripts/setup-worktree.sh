#!/usr/bin/env bash

if [ $# -ne 1 ]; then
  echo "Error: Exactly one argument required"
  echo "Usage: $0 <worktree_name>"
  exit 1
fi

BRANCH_NAME=$1
WORKTREE_NAME=$2
WT_PATH=".worktrees/$2"

git worktree add -b $BRANCH_NAME $WT_PATH
cp .env $WT_PATH/.env

cd $WT_PATH
cp .env ./web/.env
cp .env ./worker/.env

bun i
bun run web:setup
bun run worker:setup
