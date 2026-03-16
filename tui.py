import sys
import asyncio
import httpx
import json
from textual.app import App, ComposeResult
from textual.widgets import Input, Markdown, Header, Footer
from textual.containers import Container
from textual import work

class ObsiRAGTUI(App):
    """L'interface Terminal (TUI) d'ObsiRAG avec rendu Markdown en temps réel."""

    theme = "dracula"

    BINDINGS = [
        ("q", "quit", "Quitter"),
    ]

    def __init__(self, initial_query: str = None):
        super().__init__()
        self.initial_query = initial_query

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        search_input = Input(placeholder="Que souhaitez-vous explorer aujourd'hui ?", id="search-input")
        if self.initial_query:
            search_input.value = self.initial_query
            
        yield search_input
        yield Markdown("En attente d'une requête... (Tapez votre recherche en haut puis Entrée)", id="results-md")
        yield Footer()

    async def on_mount(self) -> None:
        """S'exécute au lancement de l'UI."""
        if self.initial_query:
            # On simule la soumission pour lancer directement la recherche
            md_widget = self.query_one("#results-md", Markdown)
            await md_widget.update("⏳ *Recherche en cours...*")
            self.fetch_search_stream(self.initial_query)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
            
        md_widget = self.query_one("#results-md", Markdown)
        await md_widget.update("⏳ *Recherche en cours...*")
        
        # Lance la requête en arrière-plan (non bloquant pour l'UI Textual)
        self.fetch_search_stream(query)

    @work(exclusive=True)
    async def fetch_search_stream(self, query: str):
        md_widget = self.query_one("#results-md", Markdown)
        url = "http://127.0.0.1:8000/api/ask"
        
        full_text = ""
        
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, data={"query": query}, timeout=120.0) as response:
                    response.raise_for_status()
                    
                    # On parcourt le streaming SSE envoyé par FastAPI
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                            
                        # Nettoyer "data: "
                        token = line[6:]
                        
                        if not token:
                            continue
                            
                        try:
                            # Parse JSON
                            data = json.loads(token)
                            msg_type = data.get("type")
                            content = data.get("content", "")
                            
                            if msg_type == "status":
                                if content != "[TERMINÉ]":
                                    status = content.strip("[]")
                                    await md_widget.update(f"💡 *{status}*")
                            elif msg_type == "chunk":
                                full_text += content
                                await md_widget.update(full_text)
                            elif msg_type == "done":
                                sources = data.get("sources", [])
                                if sources:
                                    sources_str = ", ".join(sources)
                                    full_text += f"\n\n**Sources :** {sources_str}"
                                    await md_widget.update(full_text)
                                
                        except json.JSONDecodeError:
                            # Fallback au cas où
                            if token.startswith("[") and token.endswith("]"):
                                if token != "[TERMINÉ]":
                                    status = token[1:-1]
                                    await md_widget.update(f"💡 *{status}*")
                            else:
                                full_text += token.replace("[TERMINÉ]", "")
                                await md_widget.update(full_text)
                            
            if not full_text:
                await md_widget.update("Aucun résultat.")
                
        except Exception as e:
            await md_widget.update(f"**Erreur :** `{str(e)}`")

if __name__ == "__main__":
    initial_q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    app = ObsiRAGTUI(initial_query=initial_q)
    app.run()
