"""
Web UI — Obsidian RAG
FastAPI + HTMX, transport HTTP local.

Routes :
  GET  /              — interface principale
  POST /api/ask       — question → réponse LLM (streaming SSE)
  POST /api/search    — recherche vectorielle → chunks
  POST /api/todo      — texte → checklist TODO
  POST /api/note/get  — lire une note
  POST /api/note/write — écrire dans une note (active ou chemin)
"""

import html
import json
import logging
from typing import AsyncGenerator

import ollama
import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from rag.answering import build_rag_context
from rag.config import GENERATION_MODEL, OBSIDIAN_API_KEY, OBSIDIAN_HOST, OBSIDIAN_PORT
from rag.editing import format_last_answer_content
from rag.obsidian_verify import fetch_obsidian_note
from rag.retrieval import search_vault

logger = logging.getLogger(__name__)

app = FastAPI(title="Obsidian RAG UI")
templates = Jinja2Templates(directory="templates")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/ask")
async def ask(query: str = Form(...)):
    """Réponse LLM en streaming SSE."""

    async def event_stream() -> AsyncGenerator[str, None]:
        yield f"data: {json.dumps({'type': 'chunk', 'content': '🔍 <i>Recherche dans le vault en cours...</i>\\n\\n'})}\n\n"
        
        try:
            # On exécute l'action bloquante dans un thread pour ne pas bloquer l'async
            import asyncio
            loop = asyncio.get_event_loop()
            system_prompt, user_query, sources = await loop.run_in_executor(
                None, build_rag_context, query
            )
        except Exception as e:
            logger.exception("Erreur construction du contexte RAG")
            yield f"data: {json.dumps({'type': 'chunk', 'content': f'❌ Erreur contexte : {e}'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'sources': []})}\n\n"
            return

        try:
            stream = ollama.chat(
                model=GENERATION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                ],
                stream=True,
                keep_alive=-1,
                options={"num_ctx": 16384},
            )

            for chunk in stream:
                content = chunk["message"]["content"]
                yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"

        except Exception as e:
            logger.exception("Erreur Ollama (streaming ask)")
            yield f"data: {json.dumps({'type': 'chunk', 'content': f'❌ Erreur LLM : {e}'})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'sources': sources})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/search", response_class=HTMLResponse)
async def search(query: str = Form(...)):
    """Recherche vectorielle → fragments HTML."""
    results = search_vault(query, n_results=10)
    docs = results["documents"][0][:5]
    metas = results["metadatas"][0][:5]

    fragments = ""
    for doc, meta in zip(docs, metas):
        src = html.escape(meta.get("source", "").split("/")[-1])
        preview = html.escape(doc[:300])
        fragments += f"""
        <div class="chunk">
            <div class="chunk-source">📄 {src}</div>
            <div class="chunk-content">{preview}…</div>
        </div>"""
    return HTMLResponse(fragments or "<p class='empty'>Aucun résultat.</p>")


@app.post("/api/todo")
async def make_todo(text: str = Form(...), format_hint: str = Form("todo checklist")):
    """Transforme un texte en checklist TODO."""
    result = format_last_answer_content(text, f"Crée une note avec {format_hint}")
    return JSONResponse({"content": result})


@app.get("/api/notes/list")
async def notes_list():
    """Liste tous les fichiers .md du vault (chemins relatifs)."""
    from rag.obsidian_verify import build_vault_index
    by_rel_path, _ = build_vault_index()
    paths = sorted(by_rel_path.values(), key=lambda p: p.lower())
    return JSONResponse({"notes": paths})


@app.post("/api/note/get")
async def note_get(path: str = Form(...)):
    """Lit une note depuis le vault."""
    content = fetch_obsidian_note(path)
    if content is None:
        return JSONResponse({"error": f"Note introuvable : {path}"})
    return JSONResponse({"content": content})


@app.post("/api/note/edit")
async def note_edit(note_content: str = Form(...), edit_query: str = Form(...)):
    """Propose une version modifiée de la note selon la requête utilisateur."""
    system_prompt = (
        "Tu es un assistant d'édition de notes Markdown.\n"
        "L'utilisateur te donne une note existante et une instruction de modification.\n"
        "Règles STRICTES :\n"
        "1. Retourne TOUJOURS la note COMPLÈTE avec la modification intégrée — jamais un fragment.\n"
        "2. Ne retourne QUE le contenu Markdown brut, sans bloc de code englobant, sans explication, sans commentaire.\n"
        "3. Respecte la structure, le style et la langue de la note originale.\n"
        "4. Applique l'instruction avec précision sans inventer de contenu non demandé.\n"
        "5. Conserve le LaTeX tel quel (blocs $$ et $ inchangés).\n"
        "6. Si l'instruction dit 'ajoute X à la fin', copie toute la note puis ajoute X à la fin."
    )
    prompt = f"NOTE ORIGINALE:\n{note_content}\n\nINSTRUCTION: {edit_query}"

    async def stream_edit():
        try:
            s = ollama.chat(
                model=GENERATION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
                keep_alive=-1,
                options={"num_ctx": 16384},
            )
            for chunk in s:
                content = chunk["message"]["content"]
                yield f"data: {json.dumps({'content': content})}\n\n"
        except Exception as e:
            logger.exception("Erreur Ollama (streaming note_edit)")
            yield f"data: {json.dumps({'content': f'❌ Erreur LLM : {e}'})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(stream_edit(), media_type="text/event-stream")


@app.post("/api/note/write", response_class=HTMLResponse)
async def note_write(path: str = Form(...), content: str = Form(...), mode: str = Form("create")):
    """Écrit dans une note via l'API REST Obsidian."""
    import ssl
    import urllib.parse
    import urllib.request

    if not OBSIDIAN_API_KEY:
        return HTMLResponse('<p class="error">OBSIDIAN_API_KEY non configurée.</p>')

    encoded = urllib.parse.quote(path)
    url = f"https://{OBSIDIAN_HOST}:{OBSIDIAN_PORT}/vault/{encoded}"
    method = "PUT" if mode == "create" else "PATCH"
    data = content.encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {OBSIDIAN_API_KEY}",
            "Content-Type": "text/markdown",
        },
        method=method,
    )
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=5, context=ctx):
            return HTMLResponse(f'<p class="success">✅ Note écrite : {path}</p>')
    except Exception as e:
        return HTMLResponse(f'<p class="error">Erreur écriture : {e}</p>')


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("web_ui:app", host="127.0.0.1", port=8000, reload=True)