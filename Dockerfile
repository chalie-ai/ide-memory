FROM debian:bookworm-slim

# PostgreSQL apt repo
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
      gpg --dearmor -o /usr/share/keyrings/postgresql.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list

# Install PostgreSQL 17 + pgvector + Python 3
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      postgresql-17 \
      postgresql-17-pgvector \
      python3 python3-pip python3-venv \
      curl \
    && rm -rf /var/lib/apt/lists/*

# Python environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Non-root user for Python processes
RUN useradd -r -m -s /bin/bash appuser

# Pre-download the embedding model at build time
RUN python3 -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-large-en-v1.5')"

# Application
COPY src/    /app/src/
COPY static/ /app/static/
COPY scripts/ /app/scripts/

RUN chmod +x /app/scripts/start.sh /app/scripts/backup.sh

RUN chown -R appuser:appuser /app/static /app/src

ENV MCP_PORT=8080 \
    MCP_HOST=0.0.0.0 \
    WEB_PORT=3000 \
    WEB_HOST=0.0.0.0

# PostgreSQL performance tuning defaults
ENV PG_SHARED_BUFFERS="256MB"
ENV PG_WORK_MEM="16MB"
ENV PG_EFFECTIVE_CACHE_SIZE="512MB"
ENV PG_MAINTENANCE_WORK_MEM="256MB"

EXPOSE 8080 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1

CMD ["/app/scripts/start.sh"]
