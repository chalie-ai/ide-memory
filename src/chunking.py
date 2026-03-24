import re
from config import CHUNK_SIZE, CHUNK_OVERLAP


def chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks, preferring sentence boundaries."""
    if len(text) <= CHUNK_SIZE:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence_len = len(sentence)

        if current_len + sentence_len > CHUNK_SIZE and current:
            chunks.append(" ".join(current))

            # Build overlap from the end of current chunk
            overlap_parts: list[str] = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s) > CHUNK_OVERLAP:
                    break
                overlap_parts.insert(0, s)
                overlap_len += len(s) + 1

            current = overlap_parts
            current_len = overlap_len

        current.append(sentence)
        current_len += sentence_len + 1

    if current:
        chunks.append(" ".join(current))

    # Fallback: if no sentence boundaries were found, split by character position
    if len(chunks) <= 1 and len(text) > CHUNK_SIZE:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks if chunks else [text]


def enrich_chunk(chunk: str, project: str = "", memory_type: str = "", tags: list[str] | None = None) -> str:
    """Prepend metadata context to chunk text for better embedding quality."""
    parts = []
    if project:
        parts.append(f"[project: {project}]")
    if memory_type:
        parts.append(f"[type: {memory_type}]")
    if tags:
        parts.append(f"[tags: {', '.join(tags)}]")
    prefix = " ".join(parts)
    return f"{prefix} {chunk}" if prefix else chunk
