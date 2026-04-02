# ===== Ollama =====
OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

EMBED_MODEL = "nomic-embed-text:v1.5"
CHAT_MODEL = "qwen3:14b"

# ===== Qdrant =====
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "nomad_rag_v2"

# ===== Kiwix =====
KIWIX_BASE = "http://localhost:8090/content"

# ===== Chunking =====
CHUNK_SIZE = 1200
MAX_CHUNKS_PER_DOC = 20

# ===== General =====
TIMEOUT = 60