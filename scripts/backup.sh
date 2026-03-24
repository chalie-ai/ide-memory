#!/bin/bash
# Manual backup & restore utility for the institutional memory system
# Usage:
#   backup.sh backup [output_path]    — Create a backup
#   backup.sh restore <backup_path>   — Restore from a backup
#   backup.sh list                    — List available backups

set -e

BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
DB_NAME="${DB_NAME:-memory}"
DB_USER="${DB_USER:-postgres}"

case "${1:-help}" in
  backup)
    OUTPUT="${2:-$BACKUP_DIR/memory_$(date +%Y%m%d_%H%M%S).dump}"
    mkdir -p "$(dirname "$OUTPUT")"
    echo "Backing up database '$DB_NAME' to $OUTPUT..."
    pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc -f "$OUTPUT"
    SIZE=$(du -h "$OUTPUT" | cut -f1)
    MEMORIES=$(psql -U "$DB_USER" -d "$DB_NAME" -tAc "SELECT COUNT(*) FROM memories WHERE NOT is_archived")
    echo "Backup complete: $OUTPUT ($SIZE, $MEMORIES active memories)"
    ;;

  restore)
    if [ -z "$2" ]; then
      echo "Usage: backup.sh restore <backup_path>"
      exit 1
    fi
    if [ ! -f "$2" ]; then
      echo "Error: Backup file not found: $2"
      exit 1
    fi
    echo "WARNING: This will replace ALL data in database '$DB_NAME'."
    echo "Restoring from $2..."
    pg_restore -U "$DB_USER" -d "$DB_NAME" --clean --if-exists -Fc "$2"
    echo "Restore complete."
    ;;

  list)
    echo "Available backups in $BACKUP_DIR:"
    if ls "$BACKUP_DIR"/memory_*.dump 1>/dev/null 2>&1; then
      ls -lh "$BACKUP_DIR"/memory_*.dump | awk '{print $NF, $5}'
    else
      echo "  (none)"
    fi
    ;;

  *)
    echo "Usage: backup.sh {backup|restore|list} [path]"
    echo ""
    echo "Commands:"
    echo "  backup [output_path]  — Create a pg_dump backup"
    echo "  restore <path>        — Restore from a backup file"
    echo "  list                  — List available backups"
    exit 1
    ;;
esac
