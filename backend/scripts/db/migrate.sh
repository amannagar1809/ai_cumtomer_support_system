#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

CMD="${1:-upgrade}"
TARGET="${2:-head}"

case "$CMD" in
  upgrade)
    python -m alembic upgrade "$TARGET"
    ;;
  downgrade)
    python -m alembic downgrade "$TARGET"
    ;;
  current)
    python -m alembic current
    ;;
  history)
    python -m alembic history --verbose
    ;;
  *)
    echo "Usage: $0 {upgrade|downgrade|current|history} [revision]"
    exit 1
    ;;
esac
