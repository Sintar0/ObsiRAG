import chromadb
import ollama

from .config import COLLECTION_NAME, DB_PATH, EMBEDDING_MODEL, KEYWORD_WEIGHT
from .styles import Colors
from .text_processing import extract_keywords, keyword_hit_count

client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(name=COLLECTION_NAME)


def rerank_results(results, keywords: list[str]):
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    if not documents:
        results["keyword_hits"] = []
        return results

    scored = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        hits = keyword_hit_count(doc, keywords)
        score = hits * KEYWORD_WEIGHT - dist
        scored.append((score, hits, dist, doc, meta))

    scored.sort(key=lambda x: (x[0], -x[2]), reverse=True)

    results["documents"][0] = [entry[3] for entry in scored]
    results["metadatas"][0] = [entry[4] for entry in scored]
    results["distances"][0] = [entry[2] for entry in scored]
    results["keyword_hits"] = [entry[1] for entry in scored]
    return results


def reformulate_query(query: str) -> str:
    search_query = query
    patterns = [
        "donne moi la définition d'une ",
        "donne moi la définition d'un ",
        "donne moi la définition de ",
        "c'est quoi le ",
        "c'est quoi la ",
        "c'est quoi l'",
        "qu'est-ce que le ",
        "qu'est-ce que la ",
        "qu'est-ce qu'",
        "définition de ",
    ]

    for pattern in patterns:
        if pattern in query.lower():
            idx = query.lower().find(pattern)
            if idx != -1:
                term = query[idx + len(pattern) :].strip()
                search_query = f"{term} définition"
                print(
                    f"{Colors.WARNING}   → Reformulé en : '{search_query}'{Colors.ENDC}"
                )
                break

    return search_query


def search_vault(query, n_results=15):
    print(f"{Colors.BLUE}🔍 Recherche vectorielle pour : '{query}'...{Colors.ENDC}")

    search_query = reformulate_query(query)
    query_embed = ollama.embeddings(model=EMBEDDING_MODEL, prompt=search_query)["embedding"]

    results = collection.query(query_embeddings=[query_embed], n_results=n_results)

    keywords = extract_keywords(query)
    if not keywords and search_query != query:
        keywords = extract_keywords(search_query)

    results = rerank_results(results, keywords)
    results["keywords"] = keywords
    results["search_query"] = search_query
    return results
