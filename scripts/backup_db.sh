#!/usr/bin/env bash
# ==============================================================================
# PBPX Zero-Downtime SQLite Backup Script
# Creates an atomic, consistent WAL snapshot using SQLite's VACUUM INTO command.
# Safe to run while the application and users are actively writing to the database.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

DATA_DIR="${PBPX_DATA_DIR:-$PROJECT_ROOT/data}"
DB_PATH="${PBPX_DB_PATH:-$DATA_DIR/pbpx.db}"
BACKUP_DIR="${DATA_DIR}/backups"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_PATH" ]; then
    if [ -f "${DATA_DIR}/demopals.db" ]; then
        DB_PATH="${DATA_DIR}/demopals.db"
    else
        echo "[PBPX Backup Error] Database file not found at: $DB_PATH" >&2
        exit 1
    fi
fi

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/pbpx_${TIMESTAMP}.db"

echo "[PBPX Backup] Creating atomic snapshot of $(basename "$DB_PATH")..."
sqlite3 "$DB_PATH" "VACUUM INTO '$BACKUP_FILE';"

# Verify integrity of the backup file
INTEGRITY=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;")
if [ "$INTEGRITY" != "ok" ]; then
    echo "[PBPX Backup Error] Integrity check failed for backup: $INTEGRITY" >&2
    rm -f "$BACKUP_FILE"
    exit 2
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[PBPX Backup] Successfully created: $BACKUP_FILE ($BACKUP_SIZE, integrity: ok)"

# Retention policy: keep last 14 days of backups
echo "[PBPX Backup] Rotating backups older than 14 days..."
find "$BACKUP_DIR" -name "pbpx_*.db" -type f -mtime +14 -print -delete 2>/dev/null || true

echo "[PBPX Backup] Complete."
