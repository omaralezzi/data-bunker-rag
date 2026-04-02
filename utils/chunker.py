from config import CHUNK_SIZE

def chunk_text(text):
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start:start + CHUNK_SIZE]
        chunks.append(chunk)
        start += CHUNK_SIZE
    return chunks
