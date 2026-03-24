#!/bin/bash
set -e

IMAGE_NAME="ide-memory"
CONTAINER_NAME="ide-memory"

case "${1:-start}" in
  build)
    echo "Building $IMAGE_NAME..."
    docker build -t "$IMAGE_NAME" .
    ;;
  start)
    echo "Starting $CONTAINER_NAME..."
    docker run -d \
      --name "$CONTAINER_NAME" \
      -p "127.0.0.1:${MCP_PORT:-8080}:8080" \
      -p "127.0.0.1:${WEB_PORT:-3000}:3000" \
      -v memory-pgdata:/var/lib/postgresql \
      --restart unless-stopped \
      "$IMAGE_NAME"
    echo ""
    echo "  MCP server (agents): http://localhost:${MCP_PORT:-8080}/sse"
    echo "  Web UI (humans):     http://localhost:${WEB_PORT:-3000}"
    echo ""
    ;;
  stop)
    echo "Stopping $CONTAINER_NAME..."
    docker stop "$CONTAINER_NAME" && docker rm "$CONTAINER_NAME"
    ;;
  logs)
    docker logs -f "$CONTAINER_NAME"
    ;;
  restart)
    $0 stop 2>/dev/null || true
    $0 start
    ;;
  *)
    echo "Usage: $0 {build|start|stop|restart|logs}"
    exit 1
    ;;
esac
