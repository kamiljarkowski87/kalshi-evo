#!/bin/bash

DB="/home/claude-runner/kalshi-evo/memory/trade_history.db"
BACKUP_DIR="/home/claude-runner/backups/kalshi-evo"
DATE=$(date +%Y-%m-%d_%H-%M)
BACKUP_FILE="$BACKUP_DIR/trade_history_$DATE.db"

cp "$DB" "$BACKUP_FILE"

# Zostaw tylko ostatnie 7 kopii, starsze usuń
ls -t "$BACKUP_DIR"/trade_history_*.db | tail -n +8 | xargs -r rm

echo "[$DATE] Backup zapisany: $BACKUP_FILE"
