"""Tests for the chunking module."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Override config before importing chunking
os.environ.setdefault("CHUNK_SIZE", "1200")
os.environ.setdefault("CHUNK_OVERLAP", "200")

from chunking import chunk_text, enrich_chunk


def test_short_text_single_chunk():
    text = "This is a short memory."
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_empty_text():
    chunks = chunk_text("")
    assert len(chunks) == 1
    assert chunks[0] == ""


def test_long_text_splits():
    sentences = ["This is sentence number %d." % i for i in range(100)]
    text = " ".join(sentences)
    chunks = chunk_text(text)
    assert len(chunks) > 1
    # All content should be present across chunks
    joined = " ".join(chunks)
    for s in sentences:
        assert s in joined


def test_chunks_have_overlap():
    sentences = ["Sentence %d is here for testing overlap behavior." % i for i in range(50)]
    text = " ".join(sentences)
    chunks = chunk_text(text)
    if len(chunks) >= 2:
        # The end of chunk N should overlap with the start of chunk N+1
        # Check that at least one sentence appears in both adjacent chunks
        for i in range(len(chunks) - 1):
            words_end = set(chunks[i].split()[-10:])
            words_start = set(chunks[i + 1].split()[:10])
            assert words_end & words_start, "No overlap found between chunks %d and %d" % (i, i + 1)


def test_fallback_for_no_sentence_boundaries():
    # Text with no sentence-ending punctuation
    text = "word " * 500
    chunks = chunk_text(text.strip())
    assert len(chunks) > 1


def test_enrich_chunk_with_all_fields():
    enriched = enrich_chunk("Some content", project="billing", memory_type="decision", tags=["db", "migration"])
    assert enriched.startswith("[project: billing]")
    assert "[type: decision]" in enriched
    assert "[tags: db, migration]" in enriched
    assert "Some content" in enriched


def test_enrich_chunk_no_metadata():
    enriched = enrich_chunk("Just content")
    assert enriched == "Just content"


def test_enrich_chunk_partial_metadata():
    enriched = enrich_chunk("Content", project="myproj")
    assert enriched == "[project: myproj] Content"
    assert "[type:" not in enriched


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
