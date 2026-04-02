import json
import urllib.request
import urllib.parse

from config import KIWIX_BASE, MAX_CHUNKS_PER_DOC
from utils.html_cleaner import clean_html
from utils.chunker import chunk_text
from utils.ollama_client_local import embed
from utils.qdrant_client_local import upsert


def fetch_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as r:
        return r.read().decode("utf-8", errors="ignore")


def build_article_url(zim_name, article_name):
    article_name = article_name.replace(" ", "_")
    encoded = urllib.parse.quote(article_name, safe="_()/")
    return f"{KIWIX_BASE}/{zim_name}/A/{encoded}"


def make_point_id(base_text):
    return abs(hash(base_text)) % (10**12)


def index_article(zim_name, article_name, domain="wikipedia_general"):
    url = build_article_url(zim_name, article_name)
    html = fetch_url(url)
    text = clean_html(html)
    chunks = chunk_text(text)[:MAX_CHUNKS_PER_DOC]

    points = []
    for i, chunk in enumerate(chunks, start=1):
        point_id = make_point_id(f"{url}::chunk::{i}")
        points.append({
            "id": point_id,
            "vector": embed(chunk),
            "payload": {
                "title": article_name,
                "source": url,
                "zim": zim_name,
                "domain": domain,
                "chunk": i,
                "text": chunk
            }
        })

    result = upsert(points)
    print(json.dumps(result, indent=2))
    print(f"Indexed article: {article_name}")
    print(f"Saved chunks: {len(points)}")
    print(f"Source URL: {url}")


if __name__ == "__main__":
    zim_name = input("اسم ملف الـ ZIM بدون .zim: ").strip()
    article_name = input("اسم المقالة: ").strip()
    domain = input("domain [default: wikipedia_general]: ").strip() or "wikipedia_general"

    index_article(zim_name, article_name, domain)
