from article_selector import select_articles
from utils.ollama_client_local import embed, chat
from utils.qdrant_client_local import search


def normalize_search_query(text: str) -> str:
    cleaned = text.replace("-", " ").replace("_", " ").strip()
    return " ".join(cleaned.split())


def detect_answer_language(question: str, answer_language: str) -> str:
    if answer_language in ("ar", "en"):
        return answer_language

    for ch in question:
        if "\u0600" <= ch <= "\u06FF":
            return "ar"
    return "en"


def translate_question_for_search(question: str) -> str:
    prompt = f"""Convert the following user question into a short English search query.

Rules:
- Use only 2 to 5 words
- Use plain English words only
- No punctuation
- No quotes
- No explanation
- No full sentence
- Return only the search query

Question:
{question}
"""
    result = chat(
        prompt,
        system="You convert user questions from any language into short English search queries for retrieval. Output only the query."
    ).strip()

    return normalize_search_query(result)


def normalize_title(title: str) -> str:
    return title.replace("_", " ").lower().strip()


def build_context(items: list[dict]) -> tuple[str, list[dict]]:
    context_parts = []
    sources = []

    for item in items:
        payload = item.get("payload", {})
        text = payload.get("text", "").strip()
        if not text:
            continue

        context_parts.append(text)
        sources.append({
            "title": payload.get("title", "Untitled"),
            "domain": payload.get("domain", "unknown"),
            "chunk": payload.get("chunk", "?"),
            "source": payload.get("source", "")
        })

    return "\n\n".join(context_parts), sources


def rerank_chunk_results(
    items: list[dict],
    selected_articles: list[dict],
    domain: str | None = None
) -> list[dict]:
    selected_titles = {
        normalize_title(article.get("title", ""))
        for article in selected_articles
        if article.get("title")
    }

    ranked = []

    for item in items:
        payload = item.get("payload", {})
        title = payload.get("title", "")
        item_domain = payload.get("domain", "general")
        score = float(item.get("score", 0))

        bonus = 0.0
        normalized_item_title = normalize_title(title)

        if normalized_item_title in selected_titles:
            bonus += 0.30

        if domain and item_domain == domain:
            bonus += 0.15

        if domain and item_domain != domain:
            bonus -= 0.08

        item["_rerank_score"] = score + bonus
        ranked.append(item)

    ranked.sort(key=lambda x: x["_rerank_score"], reverse=True)
    return ranked


def dedupe_chunk_results(items: list[dict], max_per_title: int = 2) -> list[dict]:
    counts = {}
    cleaned = []

    for item in items:
        payload = item.get("payload", {})
        title = payload.get("title", "Untitled")
        counts.setdefault(title, 0)

        if counts[title] >= max_per_title:
            continue

        counts[title] += 1
        cleaned.append(item)

    return cleaned


def generate_answer_english(question: str, context: str, selected_articles: list[dict]) -> str:
    article_hint = ", ".join([a["title"] for a in selected_articles[:5]]) if selected_articles else "None"

    prompt = f"""You must answer the user's question using ONLY the provided text.

Context:
- This is an OFFLINE survival knowledge system.
- The user may be in an emergency or no-internet scenario.

Instructions:
- Use only facts from the text
- Do NOT use outside knowledge
- Do NOT hallucinate
- Prefer PRACTICAL and ACTIONABLE steps
- Focus on survival and real-world usage
- Remove redundancy between similar methods
- Keep answer concise but useful
- Use bullet points starting with "-"
- Avoid unnecessary technical explanations
- If incomplete, start with: The available information suggests:
- If insufficient, say: The available sources are not sufficient.

Selected articles:
{article_hint}

Text:
{context}

Question:
{question}
"""
    return chat(
        prompt,
        system="You are a survival-focused RAG assistant. Give practical, actionable answers based only on provided text."
    ).strip()


def translate_answer_to_arabic(english_answer: str) -> str:
    prompt = f"""ترجم النص التالي إلى العربية الفصحى فقط.

قواعد:
- استخدم العربية الفصحى فقط
- لا تضف أي معلومة جديدة
- لا تشرح
- لا تلخص
- حافظ على المعنى كما هو
- إذا كانت هناك نقاط، فحافظ عليها كنقاط تبدأ بـ -
- لا تستخدم markdown
- اترك الأسماء أو الاختصارات التقنية فقط إذا كانت ضرورية

النص:
{english_answer}
"""
    return chat(
        prompt,
        system="أنت مترجم دقيق. ترجم فقط إلى العربية الفصحى الواضحة بدون إضافة أو حذف."
    ).strip()


def generate_followup_questions(
    question: str,
    answer: str,
    selected_articles: list[dict],
    answer_language: str = "ar"
) -> list[str]:
    article_hint = ", ".join([a["title"] for a in selected_articles[:5]]) if selected_articles else "None"

    if answer_language == "ar":
        prompt = f"""اعتمادًا على السؤال والجواب التاليين، ولّد 3 أسئلة متابعة ذكية ومفيدة.

قواعد:
- اكتب 3 أسئلة فقط
- كل سطر = سؤال واحد
- لا تضع ترقيمًا
- لا تضع شرحًا
- اجعل الأسئلة عملية ومكملة للموضوع
- استخدم العربية الفصحى فقط

السؤال:
{question}

الجواب:
{answer}

المقالات المختارة:
{article_hint}
"""
        raw = chat(
            prompt,
            system="أنت مساعد يقترح أسئلة متابعة ذكية وعملية باللغة العربية فقط."
        ).strip()
    else:
        prompt = f"""Based on the following question and answer, generate 3 smart and useful follow-up questions.

Rules:
- Write exactly 3 questions
- One line per question
- No numbering
- No explanation
- Make them practical and closely related to the topic
- Use English only

Question:
{question}

Answer:
{answer}

Selected articles:
{article_hint}
"""
        raw = chat(
            prompt,
            system="You generate smart, practical follow-up questions in English only."
        ).strip()

    lines = [line.strip(" -•\t") for line in raw.splitlines() if line.strip()]
    cleaned = []

    for line in lines:
        if not line:
            continue
        if line not in cleaned:
            cleaned.append(line)
        if len(cleaned) == 3:
            break

    return cleaned


def generate_answer(
    question: str,
    context: str,
    selected_articles: list[dict],
    answer_language: str = "ar"
) -> str:
    english_answer = generate_answer_english(question, context, selected_articles)

    if answer_language == "en":
        return english_answer

    return translate_answer_to_arabic(english_answer)


def run_rag(
    question: str,
    domain: str | None = None,
    limit: int = 5,
    mode: str = "answer_sources",
    answer_language: str = "ar",
) -> dict:
    resolved_language = detect_answer_language(question, answer_language)
    search_query = translate_question_for_search(question)

    selected_domain = domain if domain and domain != "all" else None

    selected_articles = select_articles(
        query=search_query,
        domain=selected_domain,
        limit=5
    )

    query_vector = embed(search_query)
    raw_search_result = search(query_vector, limit=12, domain=selected_domain)
    raw_items = raw_search_result.get("result", [])

    if not raw_items:
        if resolved_language == "en":
            return {
                "answer": "No suitable results were found.",
                "sources": [],
                "search_query": search_query,
                "resolved_language": resolved_language,
                "selected_articles": selected_articles,
                "followup_questions": [],
            }
        return {
            "answer": "ماكو نتائج مناسبة.",
            "sources": [],
            "search_query": search_query,
            "resolved_language": resolved_language,
            "selected_articles": selected_articles,
            "followup_questions": [],
        }

    reranked_items = rerank_chunk_results(
        raw_items,
        selected_articles=selected_articles,
        domain=selected_domain
    )
    reranked_items = dedupe_chunk_results(reranked_items, max_per_title=2)
    final_items = reranked_items[:limit]

    context, sources = build_context(final_items)

    if not context.strip():
        if resolved_language == "en":
            return {
                "answer": "The available sources are not sufficient.",
                "sources": sources,
                "search_query": search_query,
                "resolved_language": resolved_language,
                "selected_articles": selected_articles,
                "followup_questions": [],
            }
        return {
            "answer": "المصادر المتاحة غير كافية.",
            "sources": sources,
            "search_query": search_query,
            "resolved_language": resolved_language,
            "selected_articles": selected_articles,
            "followup_questions": [],
        }

    if mode == "sources_only":
        if resolved_language == "en":
            return {
                "answer": "Sources retrieved only.",
                "sources": sources,
                "search_query": search_query,
                "resolved_language": resolved_language,
                "selected_articles": selected_articles,
                "followup_questions": [],
            }
        return {
            "answer": "تم جلب المصادر فقط.",
            "sources": sources,
            "search_query": search_query,
            "resolved_language": resolved_language,
            "selected_articles": selected_articles,
            "followup_questions": [],
        }

    answer = generate_answer(
        question=question,
        context=context,
        selected_articles=selected_articles,
        answer_language=resolved_language,
    )

    followup_questions = generate_followup_questions(
        question=question,
        answer=answer,
        selected_articles=selected_articles,
        answer_language=resolved_language,
    )

    if mode == "answer_only":
        return {
            "answer": answer,
            "sources": [],
            "search_query": search_query,
            "resolved_language": resolved_language,
            "selected_articles": selected_articles,
            "followup_questions": followup_questions,
        }

    return {
        "answer": answer,
        "sources": sources,
        "search_query": search_query,
        "resolved_language": resolved_language,
        "selected_articles": selected_articles,
        "followup_questions": followup_questions,
    }