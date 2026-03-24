#!/bin/bash
set -e

PGVER=17
PGCLUSTER=main
PGDATA="/var/lib/postgresql/$PGVER/$PGCLUSTER"
PGCONF="/etc/postgresql/$PGVER/$PGCLUSTER"

# ── PostgreSQL ─────────────────────────────────────────────────────
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "Creating PostgreSQL cluster..."
    pg_createcluster "$PGVER" "$PGCLUSTER"
fi

# Ensure trust authentication (works on fresh or persisted volumes)
cat > "$PGCONF/pg_hba.conf" <<'HBA'
local   all   all                 trust
host    all   all   127.0.0.1/32  trust
host    all   all   ::1/128       trust
HBA

# Ensure PostgreSQL listens on localhost for TCP connections
sed -i "s/^#\?listen_addresses.*/listen_addresses = 'localhost'/" "$PGCONF/postgresql.conf"

# Performance tuning (idempotent — write to a separate include file)
mkdir -p "$PGCONF/conf.d"
grep -q "include_dir = 'conf.d'" "$PGCONF/postgresql.conf" 2>/dev/null || \
  echo "include_dir = 'conf.d'" >> "$PGCONF/postgresql.conf"
cat > "$PGCONF/conf.d/memory-tuning.conf" <<PERF
shared_buffers = ${PG_SHARED_BUFFERS:-256MB}
work_mem = ${PG_WORK_MEM:-16MB}
effective_cache_size = ${PG_EFFECTIVE_CACHE_SIZE:-512MB}
maintenance_work_mem = ${PG_MAINTENANCE_WORK_MEM:-256MB}
max_connections = 100
wal_buffers = 16MB
checkpoint_completion_target = 0.9
random_page_cost = 1.1
effective_io_concurrency = 200
PERF

echo "Starting PostgreSQL..."
pg_ctlcluster "$PGVER" "$PGCLUSTER" start

until pg_isready -q 2>/dev/null; do sleep 1; done
echo "PostgreSQL is ready."

# Create database if it doesn't exist
psql -U postgres -c "SELECT 1 FROM pg_database WHERE datname='memory'" -tA | grep -q 1 \
    || psql -U postgres -c "CREATE DATABASE memory"

# Run schema init (idempotent)
psql -U postgres -d memory -f /app/scripts/init.sql

echo "Schema initialized."

# ── Backup ────────────────────────────────────────────────────────
BACKUP_DIR="${BACKUP_DIR:-/app/backups}"
mkdir -p "$BACKUP_DIR"

# Run initial backup if data exists
if [ "$(psql -U postgres -d memory -tAc "SELECT COUNT(*) FROM memories" 2>/dev/null)" -gt 0 ]; then
    echo "Creating startup backup..."
    pg_dump -U postgres -d memory -Fc -f "$BACKUP_DIR/memory_$(date +%Y%m%d_%H%M%S).dump"
    # Keep only last 10 backups
    ls -t "$BACKUP_DIR"/memory_*.dump 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null
    echo "Backup complete."
fi

# Schedule hourly backups via background loop
(while true; do
    sleep 3600
    pg_dump -U postgres -d memory -Fc -f "$BACKUP_DIR/memory_$(date +%Y%m%d_%H%M%S).dump"
    ls -t "$BACKUP_DIR"/memory_*.dump 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null
    echo "Hourly backup complete at $(date)"
done) &
BACKUP_PID=$!

# ── Application ────────────────────────────────────────────────────
export DATABASE_URL="postgresql://postgres@localhost:5432/memory"

cd /app

echo "Starting MCP server on port ${MCP_PORT:-8080}..."
su appuser -s /bin/bash -c "PATH=$PATH PYTHONPATH=$PYTHONPATH DATABASE_URL=$DATABASE_URL MCP_PORT=${MCP_PORT:-8080} MCP_HOST=${MCP_HOST:-0.0.0.0} WEB_PORT=${WEB_PORT:-3000} WEB_HOST=${WEB_HOST:-0.0.0.0} python3 -u src/server.py" &
MCP_PID=$!

echo "Starting Web UI on port ${WEB_PORT:-3000}..."
su appuser -s /bin/bash -c "PATH=$PATH PYTHONPATH=$PYTHONPATH DATABASE_URL=$DATABASE_URL MCP_PORT=${MCP_PORT:-8080} MCP_HOST=${MCP_HOST:-0.0.0.0} WEB_PORT=${WEB_PORT:-3000} WEB_HOST=${WEB_HOST:-0.0.0.0} python3 -u src/api.py" &
WEB_PID=$!

trap "kill $MCP_PID $WEB_PID $BACKUP_PID 2>/dev/null; pg_ctlcluster $PGVER $PGCLUSTER stop; exit" SIGTERM SIGINT

wait -n
echo "A process exited unexpectedly. Shutting down."
kill $MCP_PID $WEB_PID $BACKUP_PID 2>/dev/null
pg_ctlcluster "$PGVER" "$PGCLUSTER" stop
exit 1
