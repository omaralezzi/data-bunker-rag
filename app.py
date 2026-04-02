import json
import uuid
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request

from rag_engine import run_rag

try:
    from config import QDRANT_URL, COLLECTION_NAME, KIWIX_BASE, OLLAMA_CHAT_URL
except Exception:
    QDRANT_URL = "http://localhost:6333"
    COLLECTION_NAME = "nomad_articles"
    KIWIX_BASE = "http://localhost:8090/content"
    OLLAMA_CHAT_URL = "http://localhost:11434/api/generate"

BASE_DIR = Path(__file__).resolve().parent
CHAT_DIR = BASE_DIR / "data" / "chats"
DATA_DIR = BASE_DIR / "data"
CHAT_DIR.mkdir(parents=True, exist_ok=True)

DOMAIN_FILES = {
    "water": "water_articles.txt",
    "medical": "medical_articles.txt",
    "power": "power_articles.txt",
    "food": "food_articles.txt",
    "prepping": "prepping_articles.txt",
}

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)


def _chat_file(chat_id: str) -> Path:
    return CHAT_DIR / f"{chat_id}.json"


def load_chat(chat_id: str) -> dict | None:
    path = _chat_file(chat_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_chat(chat_data: dict) -> None:
    path = _chat_file(chat_data["id"])
    path.write_text(json.dumps(chat_data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_chats() -> list[dict]:
    items = []
    for path in sorted(CHAT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items.append({
                "id": data["id"],
                "title": data.get("title", "New RAG Chat"),
                "updated_at": data.get("updated_at", "")
            })
        except Exception:
            continue
    return items


def count_lines_in_file(path: Path) -> int:
    if not path.exists():
        return 0

    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            count += 1
    return count


def qdrant_exact_count(filter_payload: dict | None = None) -> int:
    payload = {"exact": True}
    if filter_payload:
        payload["filter"] = filter_payload

    try:
        r = requests.post(
            f"{QDRANT_URL}/collections/{COLLECTION_NAME}/points/count",
            json=payload,
            timeout=10
        )
        r.raise_for_status()
        return int(r.json().get("result", {}).get("count", 0))
    except Exception:
        return 0


def check_http_ok(url: str) -> bool:
    try:
        r = requests.get(url, timeout=5)
        return 200 <= r.status_code < 500
    except Exception:
        return False


def get_ollama_models() -> list[str]:
    try:
        base = OLLAMA_CHAT_URL.split("/api/")[0]
        r = requests.get(f"{base}/api/tags", timeout=10)
        r.raise_for_status()
        data = r.json()
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


@app.route("/")
@app.route("/chat")
def chat_page():
    return render_template("chat.html")


@app.get("/api/chats")
def api_list_chats():
    return jsonify({"items": list_chats()})


@app.post("/api/chats")
def api_create_chat():
    chat_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    data = {
        "id": chat_id,
        "title": "New RAG Chat",
        "created_at": now,
        "updated_at": now,
        "messages": []
    }
    save_chat(data)
    return jsonify(data)


@app.get("/api/chats/<chat_id>")
def api_get_chat(chat_id: str):
    data = load_chat(chat_id)
    if not data:
        return jsonify({"error": "Chat not found"}), 404
    return jsonify(data)


@app.delete("/api/chats/<chat_id>")
def api_delete_chat(chat_id: str):
    path = _chat_file(chat_id)
    if path.exists():
        path.unlink()
    return jsonify({"ok": True})


@app.get("/api/domains")
def api_domains():
    items = []

    for domain, filename in DOMAIN_FILES.items():
        file_path = DATA_DIR / filename
        article_count = count_lines_in_file(file_path)
        indexed_count = qdrant_exact_count({
            "must": [
                {
                    "key": "domain",
                    "match": {"value": domain}
                }
            ]
        })

        items.append({
            "domain": domain,
            "file": filename,
            "article_count": article_count,
            "indexed_count": indexed_count
        })

    return jsonify({
        "collection_name": COLLECTION_NAME,
        "items": items
    })


@app.get("/api/index-status")
def api_index_status():
    kiwix_root = KIWIX_BASE.rsplit("/content", 1)[0] if "/content" in KIWIX_BASE else KIWIX_BASE
    ollama_base = OLLAMA_CHAT_URL.split("/api/")[0]

    qdrant_ok = check_http_ok(QDRANT_URL)
    kiwix_ok = check_http_ok(kiwix_root)
    ollama_ok = check_http_ok(f"{ollama_base}/api/tags")

    total_points = qdrant_exact_count()
    ollama_models = get_ollama_models()

    return jsonify({
        "qdrant_ok": qdrant_ok,
        "kiwix_ok": kiwix_ok,
        "ollama_ok": ollama_ok,
        "collection_name": COLLECTION_NAME,
        "total_points": total_points,
        "qdrant_url": QDRANT_URL,
        "kiwix_base": KIWIX_BASE,
        "ollama_base": ollama_base,
        "ollama_models": ollama_models
    })


@app.post("/api/chat")
def api_chat():
    payload = request.get_json(force=True)
    chat_id = payload.get("chat_id")
    question = (payload.get("message") or "").strip()
    domain = payload.get("domain") or "all"
    mode = payload.get("mode") or "answer_sources"
    answer_language = payload.get("answer_language") or "ar"

    try:
        limit = int(payload.get("limit", 5))
    except Exception:
        limit = 5

    if not question:
        return jsonify({"error": "Empty message"}), 400

    chat_data = load_chat(chat_id) if chat_id else None
    if not chat_data:
        chat_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        chat_data = {
            "id": chat_id,
            "title": question[:40] if question else "New RAG Chat",
            "created_at": now,
            "updated_at": now,
            "messages": []
        }

    user_msg = {
        "role": "user",
        "content": question,
        "created_at": datetime.utcnow().isoformat()
    }
    chat_data["messages"].append(user_msg)

    rag_result = run_rag(
        question=question,
        domain=domain,
        limit=limit,
        mode=mode,
        answer_language=answer_language,
    )

    assistant_msg = {
        "role": "assistant",
        "content": rag_result["answer"],
        "sources": rag_result.get("sources", []),
        "search_query": rag_result.get("search_query", ""),
        "resolved_language": rag_result.get("resolved_language", answer_language),
        "selected_articles": rag_result.get("selected_articles", []),
        "followup_questions": rag_result.get("followup_questions", []),
        "created_at": datetime.utcnow().isoformat(),
        "meta": {
            "domain": domain,
            "mode": mode,
            "limit": limit,
            "answer_language": answer_language,
            "resolved_language": rag_result.get("resolved_language", answer_language)
        }
    }

    chat_data["messages"].append(assistant_msg)
    chat_data["updated_at"] = datetime.utcnow().isoformat()

    if chat_data.get("title") == "New RAG Chat" and question:
        chat_data["title"] = question[:40]

    save_chat(chat_data)

    return jsonify({
        "chat_id": chat_data["id"],
        "message": assistant_msg,
        "title": chat_data["title"]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8091, debug=True)