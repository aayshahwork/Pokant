#!/usr/bin/env bash
set -e
# Ensure we run from repo root (works even if build runs from a different cwd)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
pnpm install --frozen-lockfile
pnpm run build
