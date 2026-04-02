from utils.ollama_client_local import embed, chat
from utils.qdrant_client_local import search


def translate_question_for_search(question):
    prompt = f"""Convert this Arabic question into a short and precise English search query only.
Do not explain anything.

Question:
{question}
"""
    return chat(
        prompt,
        system="You convert Arabic questions into short English search queries only."
    ).strip()


def ask_question(question, domain=None, limit=5):
    search_query = translate_question_for_search(question)
    query_vector = embed(search_query)
    search_result = search(query_vector, limit=limit, domain=domain)

    items = search_result.get("result", [])
    if not items:
        print("ماكو نتائج.")
        return

    context_parts = []
    sources = []

    for item in items:
        payload = item["payload"]
        context_parts.append(payload["text"])
        sources.append(
            f"- {payload.get('title', 'بدون عنوان')} | "
            f"domain: {payload.get('domain', 'unknown')} | "
            f"chunk: {payload.get('chunk', '?')}"
        )

    context = "\n\n".join(context_parts)

    prompt = f"""اعتمد فقط على المعلومات التالية.
إذا لم تكن المعلومة موجودة بوضوح، فقل ذلك.
اكتب جوابًا عربيًا فصيحًا وواضحًا.
لا تخترع معلومات غير موجودة في النص.
إذا كانت هناك عدة طرق، اعرضها كنقاط قصيرة.

المعلومات:
{context}

السؤال:
{question}
"""

    answer = chat(prompt)

    print("\n===== search query =====\n")
    print(search_query)

    print("\n===== الجواب =====\n")
    print(answer)

    print("\n===== المصادر المستخدمة =====\n")
    for s in sources[:3]:
        print(s)


if __name__ == "__main__":
    question = input("اكتب سؤالك: ").strip()
    domain = input("اختر domain (water / medical / power / food / prepping) أو اتركه فارغ: ").strip() or None
    ask_question(question, domain=domain)
