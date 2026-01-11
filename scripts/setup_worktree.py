#!/usr/bin/env -S uv run --python 3.13 --script


import argparse
import pathlib
import subprocess
from collections.abc import Sequence

ROOT_PATH = pathlib.Path(__file__).parent.parent
BRANCH_TYPES = [
    "feature",
    "chore",
    "bugfix",
    "hotfix",
    "release",
]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("branch_type", choices=BRANCH_TYPES)
    parser.add_argument("wt")
    args = parser.parse_args(argv)

    branch_name = f"{args.branch_type}/{args.wt}"
    worktree_path = ROOT_PATH / ".worktrees" / args.wt

    subprocess.call(
        ["git", "worktree", "add", "-b", branch_name, str(worktree_path)], cwd=ROOT_PATH
    )

    subprocess.call(["cp", ".env", str(worktree_path / ".env")], cwd=ROOT_PATH)

    subprocess.call(
        ["cp", ".env", str(worktree_path / "web" / ".env")], cwd=worktree_path
    )

    subprocess.call(
        ["cp", ".env", str(worktree_path / "worker" / ".env")], cwd=worktree_path
    )

    subprocess.call(["bun", "install"], cwd=worktree_path)
    subprocess.call(["bun", "run", "web:setup"], cwd=worktree_path)
    subprocess.call(["bun", "run", "worker:setup"], cwd=worktree_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
