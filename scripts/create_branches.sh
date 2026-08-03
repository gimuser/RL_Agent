#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

create_or_skip() {
  local branch="$1"
  if git rev-parse --verify "$branch" >/dev/null 2>&1; then
    echo "Branch already exists: $branch"
  else
    git branch "$branch"
    echo "Created branch: $branch"
  fi
}

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository."
  exit 0
fi

create_or_skip "develop"
create_or_skip "feature/rl-agent"
create_or_skip "feature/data-pipeline"
create_or_skip "feature/environment"
create_or_skip "feature/reward-system"
create_or_skip "feature/backend-api"
create_or_skip "feature/database-monitoring"
create_or_skip "feature/frontend"

for branch in develop feature/rl-agent feature/data-pipeline feature/environment feature/reward-system feature/backend-api feature/database-monitoring feature/frontend; do
  if git rev-parse --verify "$branch" >/dev/null 2>&1; then
    git branch --set-upstream-to="origin/$branch" "$branch" 2>/dev/null || true
    git push -u origin "$branch" 2>/dev/null || true
  fi
done

git checkout develop

echo "Branches prepared successfully."
