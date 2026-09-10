#!/usr/bin/env bash
# ==============================================================================
# PBPX SQLite Database Restoration Script
# Restores a verified backup snapshot into the active database path.
# Performs pre-flight integrity check and creates a pre-restore safety copy.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

DATA_DIR="${PBPX_DATA_DIR:-$PROJECT_ROOT/data}"
DB_PATH="${PBPX_DB_PATH:-$DATA_DIR/pbpx.db}"
BACKUP_DIR="${DATA_DIR}/backups"

BACKUP_SOURCE="${1:-}"

if [ -z "$BACKUP_SOURCE" ]; then
    # Pick the latest backup automatically
    LATEST_BACKUP=$(find "$BACKUP_DIR" -name "pbpx_*.db" -type f 2>/dev/null | sort -r | head -n 1 || true)
    if [ -z "$LATEST_BACKUP" ]; then
        echo "[PBPX Restore Error] No backup file specified and none found in $BACKUP_DIR" >&2
        echo "Usage: $0 [path/to/backup.db]" >&2
        exit 1
    fi
    BACKUP_SOURCE="$LATEST_BACKUP"
fi

if [ ! -f "$BACKUP_SOURCE" ]; then
    echo "[PBPX Restore Error] Backup file not found: $BACKUP_SOURCE" >&2
    exit 1
fi

echo "[PBPX Restore] Pre-flight: Verifying integrity of $BACKUP_SOURCE..."
INTEGRITY=$(sqlite3 "$BACKUP_SOURCE" "PRAGMA integrity_check;")
if [ "$INTEGRITY" != "ok" ]; then
    echo "[PBPX Restore Error] Backup file failed integrity check ($INTEGRITY). Restoration aborted!" >&2
    exit 2
fi

echo "[PBPX Restore] Backup integrity verified: ok."

if [ ! -f "$DB_PATH" ] && [ -f "${DATA_DIR}/demopals.db" ]; then
    DB_PATH="${DATA_DIR}/demopals.db"
fi

# Safety copy of current database if present
if [ -f "$DB_PATH" ]; then
    SAFETY_COPY="${DB_PATH}.pre_restore_$(date +%Y%m%d_%H%M%S)"
    echo "[PBPX Restore] Creating pre-restore safety copy at: $SAFETY_COPY"
    cp -p "$DB_PATH" "$SAFETY_COPY"
fi

# Clean up WAL and SHM files to prevent WAL replay conflicts
echo "[PBPX Restore] Removing active WAL/SHM journals..."
rm -f "${DB_PATH}-wal" "${DB_PATH}-shm"

echo "[PBPX Restore] Applying backup snapshot to $DB_PATH..."
cp -p "$BACKUP_SOURCE" "$DB_PATH"

# Final integrity check on the newly placed database
FINAL_CHECK=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;")
if [ "$FINAL_CHECK" != "ok" ]; then
    echo "[PBPX Restore Error] Post-restore check failed ($FINAL_CHECK)!" >&2
    exit 3
fi

TOTAL_DEMOS=$(sqlite3 "$DB_PATH" "SELECT count(*) FROM demos;" 2>/dev/null || echo "N/A")
TOTAL_USERS=$(sqlite3 "$DB_PATH" "SELECT count(*) FROM users;" 2>/dev/null || echo "N/A")

echo "=============================================================================="
echo "[PBPX Restore] Successfully restored database!"
echo "Source:       $BACKUP_SOURCE"
echo "Target:       $DB_PATH"
echo "Total Demos:  $TOTAL_DEMOS"
echo "Total Users:  $TOTAL_USERS"
echo "=============================================================================="
