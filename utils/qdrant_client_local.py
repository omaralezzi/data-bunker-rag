import requests

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "nomad_rag_v2"


def search(vector, limit=5, domain=None, titles=None):
    must_conditions = []

    if domain and domain != "all":
        must_conditions.append({
            "key": "domain",
            "match": {"value": domain}
        })

    if titles:
        must_conditions.append({
            "key": "title",
            "match": {"any": titles}
        })

    query = {
        "vector": vector,
        "limit": limit,
        "with_payload": True
    }

    if must_conditions:
        query["filter"] = {
            "must": must_conditions
        }

    r = requests.post(
        f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/search",
        json=query,
        timeout=120
    )
    r.raise_for_status()
    return r.json()