import sys
sys.path.insert(0, ".")
from ingestion.chunker import chunk_text


def test_short_text_produces_one_chunk():
    chunks = chunk_text("Hello world", chunk_size=512, overlap=64)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


def test_long_text_splits_into_multiple_chunks():
    words = ["word"] * 600
    text = " ".join(words)
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) > 1


def test_chunks_overlap():
    words = [str(i) for i in range(200)]
    text = " ".join(words)
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    assert len(chunks) >= 2
    last_words_chunk0 = set(chunks[0].split()[-10:])
    first_words_chunk1 = set(chunks[1].split()[:10])
    assert len(last_words_chunk0 & first_words_chunk1) > 0


def test_empty_text_returns_empty_list():
    assert chunk_text("", chunk_size=512, overlap=64) == []


def test_chunk_size_respected():
    words = ["word"] * 1000
    text = " ".join(words)
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    for chunk in chunks:
        assert len(chunk.split()) <= 100
