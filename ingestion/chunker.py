from typing import List


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> List[str]:
    if not text.strip():
        return []
    words = text.split()
    if not words:
        return []
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks
