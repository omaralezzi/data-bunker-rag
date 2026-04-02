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


def normalize_title(title: str) -> str:
    title = title.strip()
    if "|" in title:
        return title.split("|", 1)[1].strip().lower()
    return title.lower()


def rerank_results(results: list[dict], domain: str | None = None) -> list[dict]:
    ranked = []

    for item in results:
        payload = item.get("payload", {})
        title = payload.get("title", "").strip()
        title_lower = title.lower()
        score = float(item.get("score", 0))

        bonus = 0.0

        # Domain boost
        if domain and title_lower.startswith(domain.lower() + "|"):
            bonus += 0.25

        # Practical keyword boosts
        practical_keywords = [
            "generator", "battery", "power", "water", "filter", "purification",
            "food", "preservation", "canning", "drying", "emergency"
        ]
        for kw in practical_keywords:
            if kw in title_lower:
                bonus += 0.02

        # Penalize misleading cross-domain matches
        if domain == "power" and "medical" in title_lower:
            bonus -= 0.20
        if domain == "water" and "medical" in title_lower:
            bonus -= 0.20
        if domain == "food" and "medical" in title_lower:
            bonus -= 0.20

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


def main():
    query = input("Search query: ").strip()
    if not query:
        print("Empty query.")
        return

    domain = input("Domain (all/water/medical/power/food/prepping): ").strip().lower()
    if domain == "all" or domain == "":
        domain = None

    results = search_titles(query, limit=15)
    results = rerank_results(results, domain=domain)
    results = dedupe_results(results)

    print("\n=== RESULTS ===\n")
    for i, item in enumerate(results[:8], start=1):
        payload = item.get("payload", {})
        print(f"{i}. {payload.get('title', 'Untitled')}")
        print(f"   score: {item.get('score')}")
        print(f"   rerank: {item.get('_rerank_score')}")
        print(f"   source: {payload.get('source')}")
        print()


if __name__ == "__main__":
    main()
