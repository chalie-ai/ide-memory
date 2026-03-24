CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Core memories table
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    memory_type VARCHAR(100) NOT NULL DEFAULT 'note',
    author VARCHAR(255) NOT NULL DEFAULT 'unknown',
    repo VARCHAR(512),
    file_path VARCHAR(1024),
    branch_name VARCHAR(255),
    source VARCHAR(100) NOT NULL DEFAULT 'manual',
    source_ref VARCHAR(2048),
    affected_services TEXT[] DEFAULT '{}',
    affected_files TEXT[] DEFAULT '{}',
    affected_modules TEXT[] DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    search_vector tsvector,
    confidence VARCHAR(20) NOT NULL DEFAULT 'medium',
    last_validated_at TIMESTAMPTZ,
    content_hash VARCHAR(64),
    is_archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Migrate existing installations (ADD COLUMN IF NOT EXISTS)
ALTER TABLE memories ADD COLUMN IF NOT EXISTS source VARCHAR(100) NOT NULL DEFAULT 'manual';
ALTER TABLE memories ADD COLUMN IF NOT EXISTS source_ref VARCHAR(2048);
ALTER TABLE memories ADD COLUMN IF NOT EXISTS affected_services TEXT[] DEFAULT '{}';
ALTER TABLE memories ADD COLUMN IF NOT EXISTS affected_files TEXT[] DEFAULT '{}';
ALTER TABLE memories ADD COLUMN IF NOT EXISTS affected_modules TEXT[] DEFAULT '{}';
ALTER TABLE memories ADD COLUMN IF NOT EXISTS confidence VARCHAR(20) NOT NULL DEFAULT 'medium';
ALTER TABLE memories ADD COLUMN IF NOT EXISTS last_validated_at TIMESTAMPTZ;
ALTER TABLE memories ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);

DO $$ BEGIN
    ALTER TABLE memories ADD CONSTRAINT chk_memory_type
      CHECK (memory_type IN ('decision','rule','change','context','incident','note'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE memories ADD CONSTRAINT chk_confidence
      CHECK (confidence IN ('high','medium','low'));
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE memories ADD CONSTRAINT chk_content_length
      CHECK (length(content) <= 100000);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Vector chunks for semantic search
CREATE TABLE IF NOT EXISTS memory_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    embedding_model VARCHAR(255) NOT NULL DEFAULT 'BAAI/bge-large-en-v1.5',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE memory_chunks ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(255) NOT NULL DEFAULT 'BAAI/bge-large-en-v1.5';

-- Indexes: memories
CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_author ON memories(author);
CREATE INDEX IF NOT EXISTS idx_memories_repo ON memories(repo) WHERE repo IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memories_file_path ON memories(file_path) WHERE file_path IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source);
CREATE INDEX IF NOT EXISTS idx_memories_project_date ON memories(project, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_memories_archived ON memories(is_archived) WHERE is_archived = FALSE;
CREATE INDEX IF NOT EXISTS idx_memories_tags ON memories USING gin(tags);
CREATE INDEX IF NOT EXISTS idx_memories_affected_services ON memories USING gin(affected_services);
CREATE INDEX IF NOT EXISTS idx_memories_affected_files ON memories USING gin(affected_files);
CREATE INDEX IF NOT EXISTS idx_memories_affected_modules ON memories USING gin(affected_modules);
CREATE INDEX IF NOT EXISTS idx_memories_metadata ON memories USING gin(metadata jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_memories_search ON memories USING gin(search_vector);
CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_content_hash
  ON memories(project, content_hash) WHERE content_hash IS NOT NULL AND NOT is_archived;
CREATE INDEX IF NOT EXISTS idx_memories_validated ON memories(last_validated_at) WHERE last_validated_at IS NOT NULL;

-- Indexes: chunks
CREATE INDEX IF NOT EXISTS idx_chunks_memory_id ON memory_chunks(memory_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON memory_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 24, ef_construction = 128);

-- Trigger: keep search_vector in sync (includes impact scope for discoverability)
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', coalesce(NEW.project, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.memory_type, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.repo, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(array_to_string(NEW.affected_services, ' '), '')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.file_path, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(array_to_string(NEW.affected_files, ' '), '')), 'B') ||
        setweight(to_tsvector('english', coalesce(array_to_string(NEW.affected_modules, ' '), '')), 'B') ||
        setweight(to_tsvector('english', coalesce(array_to_string(NEW.tags, ' '), '')), 'B') ||
        setweight(to_tsvector('english', coalesce(NEW.content, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS memories_search_vector ON memories;
CREATE TRIGGER memories_search_vector
    BEFORE INSERT OR UPDATE ON memories
    FOR EACH ROW
    EXECUTE FUNCTION update_search_vector();

-- Trigger: auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS memories_updated_at ON memories;
CREATE TRIGGER memories_updated_at
    BEFORE UPDATE ON memories
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();
