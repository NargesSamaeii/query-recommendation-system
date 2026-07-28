#!/bin/bash
# Restores Verona_Tourism_Ontop/tourismdb_jan 1.backup (custom-format pg_dump, ~280MB) into
# postgres-tourism on first container start via docker-entrypoint-initdb.d.
set -e

echo "Creating postgis extension (required: art_all's location table uses geometry columns)..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS postgis;"

echo "Restoring tourismdb backup (this can take several minutes for ~280MB)..."
set +e
pg_restore --no-owner --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --jobs=2 /backup/tourismdb.backup
RESTORE_STATUS=$?
set -e
if [ $RESTORE_STATUS -ne 0 ]; then
    echo "WARNING: pg_restore exited with status $RESTORE_STATUS."
    echo "This is often just non-fatal warnings from the original dump (missing roles/extensions"
    echo "already present, etc). Verify actual table row counts after startup -- see docker/README.md."
fi

echo "Tourism DB restore step complete."
