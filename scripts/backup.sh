#!/usr/bin/env bash
# SirenTracker weekly backup — run via cron
# Snapshots the SQLite DB, photos, and Gmail OAuth token, then uploads to
# Google Drive via rclone. The .backup file is comprehensive — there is no
# longer a per-table CSV export, since hand-maintained column lists drift
# out of date with the schema (and the admin UI exposes CSV export anyway).
#
# Cron example (every Sunday at 2 AM):
#   0 2 * * 0 /opt/sirentracker/scripts/backup.sh >> /var/log/sirentracker-backup.log 2>&1

set -euo pipefail

APP_DIR="/opt/sirentracker"
BACKUP_DIR="/tmp/sirentracker_backup_$(date +%Y%m%d)"
DB_PATH="${APP_DIR}/instance/sirentracker.db"
GMAIL_TOKEN="${APP_DIR}/instance/gmail_token.json"
RCLONE_REMOTE="gdrive:SirenTracker-Backups"

echo "$(date '+%Y-%m-%d %H:%M:%S') Starting backup..."

mkdir -p "${BACKUP_DIR}"

# Safe SQLite backup (works while the app is running)
sqlite3 "${DB_PATH}" ".backup '${BACKUP_DIR}/sirentracker.db'"
echo "Snapshotted SQLite DB"

# Gmail OAuth token — without this, magic-link login emails stop working
# and re-auth requires running scripts/gmail_auth.py from a workstation.
if [ -f "${GMAIL_TOKEN}" ]; then
    cp "${GMAIL_TOKEN}" "${BACKUP_DIR}/gmail_token.json"
    chmod 600 "${BACKUP_DIR}/gmail_token.json"
    echo "Copied gmail_token.json"
else
    echo "WARN: ${GMAIL_TOKEN} not found — Gmail token NOT backed up"
fi

# Photos
if [ -d "${APP_DIR}/media/photos" ]; then
    cp -r "${APP_DIR}/media/photos" "${BACKUP_DIR}/photos"
    echo "Copied photos directory"
fi

# Upload to Google Drive — fail loudly if rclone returns non-zero so cron
# emails the failure and we don't silently delete a broken backup.
if ! rclone copy "${BACKUP_DIR}" "${RCLONE_REMOTE}/$(date +%Y-%m-%d)/" --log-level INFO; then
    echo "ERROR: rclone upload failed — leaving ${BACKUP_DIR} for inspection"
    exit 1
fi

# Cleanup
rm -rf "${BACKUP_DIR}"

echo "$(date '+%Y-%m-%d %H:%M:%S') Backup complete."
