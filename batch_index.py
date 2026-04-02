import os
import time
import requests

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "nomad_articles"

OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"

DATA_DIR = os.path.expanduser("~/nomad_rag/data")

DOMAIN_FILES = [
    "article_list.txt",
    "water_articles.txt",
    "medical_articles.txt",
    "power_articles.txt",
    "food_articles.txt",
    "prepping_articles.txt",
]


def infer_domain_from_filename(filename: str) -> str:
    name = filename.lower()

    if name.startswith("water_"):
        return "water"
    if name.startswith("medical_"):
        return "medical"
    if name.startswith("power_"):
        return "power"
    if name.startswith("food_"):
        return "food"
    if name.startswith("prepping_"):
        return "prepping"

    return "general"


def extract_domain_and_title(raw: str, fallback_domain: str):
    raw = raw.strip()

    if "|" in raw:
        domain, title = raw.split("|", 1)
        return domain.strip().lower(), title.strip()

    return fallback_domain, raw


def normalize_title(title: str):
    return title.replace("_", " ").lower().strip()


def read_titles():
    titles = []
    seen = set()

    for filename in DOMAIN_FILES:
        path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(path):
            print(f"[WARN] Missing file: {path}")
            continue

        fallback_domain = infer_domain_from_filename(filename)

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw or raw.startswith("#"):
                    continue

                domain, title = extract_domain_and_title(raw, fallback_domain)
                normalized = normalize_title(title)

                if normalized in seen:
                    continue

                seen.add(normalized)
                titles.append((domain, title))

    return titles


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


def ensure_collection(vector_size: int):
    r = requests.get(f"{QDRANT_URL}/collections/{COLLECTION_NAME}")
    if r.status_code == 200:
        print(f"[OK] Collection exists: {COLLECTION_NAME}")
        return

    payload = {
        "vectors": {
            "size": vector_size,
            "distance": "Cosine"
        }
    }

    r = requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}",
        json=payload,
        timeout=60
    )
    r.raise_for_status()
    print(f"[OK] Created collection: {COLLECTION_NAME}")


def upsert_point(point_id: int, domain: str, title: str, embedding):
    payload = {
        "points": [
            {
                "id": point_id,
                "vector": embedding,
                "payload": {
                    "title": title,
                    "normalized_title": normalize_title(title),
                    "domain": domain,
                    "source": "wikipedia"
                }
            }
        ]
    }

    r = requests.put(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points",
        json=payload,
        timeout=120
    )
    r.raise_for_status()


def main():
    titles = read_titles()

    if not titles:
        print("[ERROR] No titles found.")
        return

    print(f"[INFO] Total unique titles: {len(titles)}")

    first_embedding = get_embedding(titles[0][1])
    ensure_collection(len(first_embedding))

    for i, (domain, title) in enumerate(titles, start=1):
        try:
            print(f"[{i}/{len(titles)}] {domain} | {title}")
            embedding = get_embedding(title)
            upsert_point(i, domain, title, embedding)
            time.sleep(0.2)
        except Exception as e:
            print(f"[ERROR] Failed on '{title}': {e}")

    print("[DONE] Indexing complete.")


if __name__ == "__main__":
    main()