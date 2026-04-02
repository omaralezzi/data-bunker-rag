import requests

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "nomad_articles"
OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"


def get_embedding(text: str):
    r = requests.post(
        OLLAMA_EMBED_URL,
        json={
            "model": "nomic-embed-text",
            "input": text
        },
        timeout=120
    )
    r.raise_for_status()
    return r.json()["embeddings"][0]


def normalize_title(title: str) -> str:
    return title.replace("_", " ").lower().strip()


def search_titles(query: str, limit: int = 15):
    vector = get_embedding(query)

    r = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/search",
        json={
            "vector": vector,
            "limit": limit,
            "with_payload": True
        },
        timeout=120
    )
    r.raise_for_status()
    return r.json().get("result", [])


def rerank_results(results: list[dict], domain: str | None = None) -> list[dict]:
    ranked = []

    for item in results:
        payload = item.get("payload", {})
        title = payload.get("title", "").strip().lower()
        item_domain = payload.get("domain", "general").strip().lower()
        score = float(item.get("score", 0))

        bonus = 0.0

        # ✅ Strong domain boost
        if domain and item_domain == domain:
            bonus += 0.30

        # ✅ Mild penalty for mismatch
        if domain and item_domain != domain:
            bonus -= 0.15

        # ✅ Strong penalty for wrong domains
        if domain == "power" and item_domain == "medical":
            bonus -= 0.30
        if domain == "water" and item_domain == "medical":
            bonus -= 0.30
        if domain == "food" and item_domain == "medical":
            bonus -= 0.30

        # ✅ Keyword-based boost
        practical_keywords = [
            "water", "purification", "filter", "disinfection",
            "food", "preservation", "canning", "drying",
            "power", "generator", "battery", "solar",
            "medical", "first aid", "bleeding", "burn"
        ]

        for kw in practical_keywords:
            if kw in title:
                bonus += 0.02

        # ❌ Penalize unrelated keywords
        bad_keywords = ["medical", "disease", "infection"]
        if domain != "medical":
            for kw in bad_keywords:
                if kw in title:
                    bonus -= 0.10

        item["_rerank_score"] = score + bonus
        ranked.append(item)

    ranked.sort(key=lambda x: x["_rerank_score"], reverse=True)
    return ranked


def dedupe_results(results: list[dict]) -> list[dict]:
    seen = set()
    cleaned = []

    for item in results:
        payload = item.get("payload", {})
        title = payload.get("title", "").strip()
        normalized = normalize_title(title)

        if normalized in seen:
            continue

        seen.add(normalized)
        cleaned.append(item)

    return cleaned


def select_articles(query: str, domain: str | None = None, limit: int = 5) -> list[dict]:
    results = search_titles(query, limit=15)
    results = rerank_results(results, domain=domain)
    results = dedupe_results(results)

    selected = []
    for item in results[:limit]:
        payload = item.get("payload", {})
        selected.append({
            "title": payload.get("title", ""),
            "normalized_title": payload.get("normalized_title", ""),
            "domain": payload.get("domain", "general"),
            "score": item.get("score", 0),
            "rerank_score": item.get("_rerank_score", 0),
            "source": payload.get("source", "")
        })

    return selected