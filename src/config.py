import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/memory")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
EMBEDDING_DIM = 1024
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "100000"))
MCP_PORT = int(os.getenv("MCP_PORT", "8080"))
MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("WEB_PORT", "3000"))
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
POOL_MIN = int(os.getenv("POOL_MIN", "5"))
POOL_MAX = int(os.getenv("POOL_MAX", "20"))
