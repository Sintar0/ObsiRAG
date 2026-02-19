import ollama

from .config import GENERATION_MODEL, MAX_CONTEXT_CHARS, MAX_DOC_CHARS, MAX_DOCS
from .obsidian_verify import build_verified_context
from .styles import Colors
from .text_processing import normalize_text


def compress_document(doc: str, keywords: list[str], max_chars: int) -> str:
    if not doc:
        return ""

    lines = [line.strip() for line in doc.splitlines() if line.strip()]

    if keywords:
        matched = [
            line for line in lines if any(keyword in normalize_text(line) for keyword in keywords)
        ]
    else:
        matched = []

    if matched:
        compressed = "\n".join(matched)
    else:
        compressed = "\n".join(lines[:6])

    if len(compressed) > max_chars:
        compressed = compressed[:max_chars].rsplit(" ", 1)[0] + "..."

    return compressed


def generate_answer(query, results):
    context_text = ""
    sources = set()

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    keywords = results.get("keywords", [])

    documents = documents[:MAX_DOCS]
    metadatas = metadatas[:MAX_DOCS]

    for i, doc in enumerate(documents):
        source_path = metadatas[i]["source"]
        filename = source_path.split("/")[-1]
        sources.add(filename)

        compressed = compress_document(doc, keywords, MAX_DOC_CHARS)
        if not compressed:
            continue

        addition = f"---\nSOURCE: {filename}\nCONTENU:\n{compressed}\n\n"
        if len(context_text) + len(addition) > MAX_CONTEXT_CHARS:
            break

        context_text += addition

    verified_context = build_verified_context(metadatas, keywords)
    if verified_context:
        remaining = MAX_CONTEXT_CHARS - len(context_text)
        if remaining > 200:
            context_text += "\n" + verified_context[:remaining]

    print(
        f"{Colors.GREEN}📚 {len(documents)} fragments trouvés dans : {', '.join(sources)}{Colors.ENDC}"
    )
    if verified_context:
        print(f"{Colors.BLUE}🧭 Vérification étendue via notes complètes activée{Colors.ENDC}")

    system_prompt = f"""
    Tu es un assistant personnel intelligent connecté aux notes Obsidian de l'utilisateur.

    Règles :
    1. Réponds en priorité avec les informations du CONTEXTE ci-dessous.
    2. Si le contexte contient la réponse complète, utilise-le et cite tes sources (ex: [Note.md]).
    3. Si le contexte contient des éléments pertinents mais incomplets, propose une réponse utile en indiquant clairement ce qui vient des notes vs tes connaissances.
    4. Si le contexte ne contient rien de pertinent, réponds avec tes connaissances générales en précisant : "Je n'ai pas trouvé cette info dans tes notes, mais voici ce que je sais..."
    5. Sois concis, structuré (Markdown) et naturel (évite un ton robotique).

    CONTEXTE :
    {context_text}
    """

    print(
        f"{Colors.HEADER}🤖 Génération de la réponse avec {GENERATION_MODEL}...{Colors.ENDC}\n"
    )

    stream = ollama.chat(
        model=GENERATION_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ],
        stream=True,
    )

    for chunk in stream:
        content = chunk["message"]["content"]
        print(content, end="", flush=True)

    print(f"\n\n{Colors.WARNING}--- Fin de la réponse ---{Colors.ENDC}")
