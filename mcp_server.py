"""
Serveur MCP local — Obsidian RAG
Expose le pipeline RAG comme tools MCP (transport stdio).

Tools disponibles :
  vault_search   — recherche vectorielle + rerank
  vault_answer   — réponse complète MCP-first
  vault_todo     — transforme un texte en checklist TODO
  vault_note_get — lit une note brute depuis le vault
"""

import json
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from rag.config import VAULT_ROOT
from rag.editing import format_last_answer_content
from rag.obsidian_verify import fetch_obsidian_note
from rag.retrieval import search_vault

app = Server("obsidian-rag")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _results_to_dict(results: dict, top_k: int) -> list[dict]:
    docs = results.get("documents", [[]])[0][:top_k]
    metas = results.get("metadatas", [[]])[0][:top_k]
    distances = results.get("distances", [[]])[0][:top_k]
    hits = results.get("keyword_hits", [0] * len(docs))

    out = []
    for doc, meta, dist, hit in zip(docs, metas, distances, hits):
        out.append({
            "source": meta.get("source", "").split("/")[-1],
            "content": doc,
            "distance": round(dist, 4),
            "keyword_hits": hit,
        })
    return out


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="vault_search",
            description=(
                "Recherche dans le vault Obsidian via RAG vectoriel + reranking par mots-clés. "
                "Retourne les chunks les plus pertinents avec leur source."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La question ou requête de recherche.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Nombre de résultats à retourner (défaut: 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="vault_answer",
            description=(
                "Génère une réponse complète à partir du vault Obsidian. "
                "Utilise le pipeline MCP-first (notes complètes prioritaires) + RAG en complément. "
                "Retourne la réponse textuelle et les sources utilisées."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "La question à poser au vault.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Nombre de chunks RAG à considérer (défaut: 15).",
                        "default": 15,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="vault_todo",
            description=(
                "Transforme un texte (réponse LLM, notes brutes, etc.) en checklist TODO Markdown. "
                "Utilise une transformation sémantique en 2 étapes : extraction des concepts puis reformatage."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Le texte source à transformer.",
                    },
                    "format_hint": {
                        "type": "string",
                        "description": (
                            "Indication de format souhaitée, ex: 'todo', 'résumé', 'liste'. "
                            "Défaut: 'todo checklist'."
                        ),
                        "default": "todo checklist",
                    },
                },
                "required": ["text"],
            },
        ),
        Tool(
            name="vault_note_get",
            description=(
                "Lit le contenu brut d'une note Obsidian depuis le vault. "
                "Le chemin est relatif à la racine du vault."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Chemin relatif de la note dans le vault, ex: 'Grand orale.md'.",
                    },
                },
                "required": ["path"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    if name == "vault_search":
        query = arguments["query"]
        top_k = int(arguments.get("top_k", 5))
        results = search_vault(query, n_results=max(top_k, 15))
        chunks = _results_to_dict(results, top_k)
        return [TextContent(type="text", text=json.dumps(chunks, ensure_ascii=False, indent=2))]

    elif name == "vault_answer":
        from rag.answering import generate_answer

        query = arguments["query"]
        top_k = int(arguments.get("top_k", 15))
        results = search_vault(query, n_results=top_k)

        # generate_answer streame vers stdout en CLI — on capture la valeur retournée
        answer = generate_answer(query, results)
        sources = list({
            m.get("source", "").split("/")[-1]
            for m in results.get("metadatas", [[]])[0]
        })
        payload = {"answer": answer, "sources": sources}
        return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]

    elif name == "vault_todo":
        text = arguments["text"]
        format_hint = arguments.get("format_hint", "todo checklist")
        transformed = format_last_answer_content(text, f"Crée une note avec {format_hint}")
        return [TextContent(type="text", text=transformed)]

    elif name == "vault_note_get":
        rel_path = arguments["path"]
        content = fetch_obsidian_note(rel_path)
        if content is None:
            return [TextContent(type="text", text=f"Erreur : note introuvable → {rel_path}")]
        return [TextContent(type="text", text=content)]

    else:
        return [TextContent(type="text", text=f"Outil inconnu : {name}")]


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
