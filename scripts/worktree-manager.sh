#!/usr/bin/env bash
# worktree-manager.sh — Manage git worktrees for concurrent Claude Code sessions.
#
# Usage:
#   scripts/worktree-manager.sh create <name> [branch]  Create a worktree (symlinks .env)
#   scripts/worktree-manager.sh list                     List active worktrees
#   scripts/worktree-manager.sh remove <name>            Remove a worktree
#   scripts/worktree-manager.sh clean                    Remove ALL worktrees
#   scripts/worktree-manager.sh setup [count]            Create N worktrees (default: 5)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TREES_DIR="${REPO_DIR}-trees"

# Untracked files to symlink into each worktree
SYMLINK_FILES=(".env")

usage() {
    sed -n '2,8p' "$0" | sed 's/^# \?//'
    exit 0
}

symlink_configs() {
    local tree_path="$1"
    for f in "${SYMLINK_FILES[@]}"; do
        local src="$REPO_DIR/$f"
        local dst="$tree_path/$f"
        if [ -f "$src" ] && [ ! -L "$dst" ]; then
            ln -sf "$src" "$dst"
            echo "  Symlinked $f"
        fi
    done
}

cmd_create() {
    local name="${1:-}"
    local branch="${2:-}"

    if [ -z "$name" ]; then
        echo "Usage: $0 create <name> [branch]"
        echo "  name:   worktree directory name (e.g., agent-1, feat-auth)"
        echo "  branch: branch to check out (default: detached HEAD from main)"
        exit 1
    fi

    local tree_path="$TREES_DIR/$name"

    if [ -d "$tree_path" ]; then
        echo "Worktree '$name' already exists at $tree_path"
        exit 1
    fi

    mkdir -p "$TREES_DIR"

    if [ -n "$branch" ]; then
        # Check if branch exists
        if git -C "$REPO_DIR" rev-parse --verify "$branch" >/dev/null 2>&1; then
            git -C "$REPO_DIR" worktree add "$tree_path" "$branch"
        else
            # Create new branch from main
            git -C "$REPO_DIR" worktree add "$tree_path" -b "$branch" main
        fi
    else
        # Detached HEAD from current main
        git -C "$REPO_DIR" worktree add --detach "$tree_path" main
    fi

    symlink_configs "$tree_path"
    echo "Created worktree: $tree_path"
}

cmd_list() {
    git -C "$REPO_DIR" worktree list
}

cmd_remove() {
    local name="${1:-}"

    if [ -z "$name" ]; then
        echo "Usage: $0 remove <name>"
        exit 1
    fi

    local tree_path="$TREES_DIR/$name"

    if [ ! -d "$tree_path" ]; then
        echo "Worktree '$name' not found at $tree_path"
        exit 1
    fi

    git -C "$REPO_DIR" worktree remove "$tree_path"
    echo "Removed worktree: $name"
}

cmd_clean() {
    if [ ! -d "$TREES_DIR" ]; then
        echo "No worktrees directory found."
        exit 0
    fi

    local count=0
    for tree in "$TREES_DIR"/*/; do
        [ -d "$tree" ] || continue
        local name
        name=$(basename "$tree")
        git -C "$REPO_DIR" worktree remove --force "$tree" 2>/dev/null || rm -rf "$tree"
        echo "Removed: $name"
        count=$((count + 1))
    done

    git -C "$REPO_DIR" worktree prune
    echo "Cleaned $count worktrees."
}

cmd_setup() {
    local count="${1:-5}"

    mkdir -p "$TREES_DIR"

    for i in $(seq 1 "$count"); do
        local name="agent-$i"
        local tree_path="$TREES_DIR/$name"

        if [ -d "$tree_path" ]; then
            echo "Skipping $name (already exists)"
            continue
        fi

        git -C "$REPO_DIR" worktree add --detach "$tree_path" main
        symlink_configs "$tree_path"
        echo "Created: $name"
    done

    echo ""
    echo "Worktrees ready at: $TREES_DIR/"
    git -C "$REPO_DIR" worktree list
}

# --- Main ---
COMMAND="${1:-}"
shift 2>/dev/null || true

case "$COMMAND" in
    create)  cmd_create "$@" ;;
    list)    cmd_list ;;
    remove)  cmd_remove "$@" ;;
    clean)   cmd_clean ;;
    setup)   cmd_setup "$@" ;;
    -h|--help|help|"") usage ;;
    *)
        echo "Unknown command: $COMMAND"
        usage
        ;;
esac
