#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# backup.sh - Create a timestamped SQLite backup using the .backup command
#
# Usage:
#   ./scripts/backup.sh [path/to/database.db]
#
# Defaults to data/weeklyamp.db if no argument is provided.
# Keeps the most recent 7 backups and removes older ones.
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

DB_PATH="${1:-data/weeklyamp.db}"

# Resolve relative paths against the project root
if [[ "$DB_PATH" != /* ]]; then
    DB_PATH="$PROJECT_DIR/$DB_PATH"
fi

BACKUP_DIR="$PROJECT_DIR/backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="$BACKUP_DIR/weeklyamp_${TIMESTAMP}.db"

# --- Pre-flight checks -----------------------------------------------------

if ! command -v sqlite3 &>/dev/null; then
    echo "ERROR: sqlite3 is not installed or not on PATH." >&2
    exit 1
fi

if [[ ! -f "$DB_PATH" ]]; then
    echo "ERROR: Database file not found: $DB_PATH" >&2
    exit 1
fi

# --- Create backup ----------------------------------------------------------

mkdir -p "$BACKUP_DIR"

echo "Starting backup of $DB_PATH ..."
echo "Destination: $BACKUP_FILE"

if sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"; then
    echo "Backup completed successfully."
else
    echo "ERROR: Backup failed." >&2
    exit 1
fi

# --- Prune old backups (keep last 7) ---------------------------------------

BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/weeklyamp_*.db 2>/dev/null | wc -l | tr -d ' ')
echo "Total backups on disk: $BACKUP_COUNT"

if [[ "$BACKUP_COUNT" -gt 7 ]]; then
    DELETE_COUNT=$((BACKUP_COUNT - 7))
    echo "Pruning $DELETE_COUNT old backup(s) ..."
    ls -1t "$BACKUP_DIR"/weeklyamp_*.db | tail -n "$DELETE_COUNT" | while read -r old; do
        echo "  Removing $old"
        rm -f "$old"
    done
fi

echo "Done."
