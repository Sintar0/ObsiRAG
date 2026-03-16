# Log 6 : Interface Terminal (TUI) et Nettoyage du Backend

## Objectifs de cette étape
1. **Remplacer l'interface Web par une interface Terminal (TUI)** plus adaptée à un usage "hacker/terminal-first".
2. **Nettoyer le backend** en supprimant la gestion des templates HTML (Jinja2) pour ne garder qu'une API pure.
3. **Mettre à jour le modèle de génération** vers `LiquidAI_LFM2-24B-A2B-GGUF:Q4_K_M`.

---

## 1. Création du TUI avec `textual`

Nous avons utilisé la librairie Python `textual` pour créer une interface graphique directement dans le terminal. Cette librairie permet de créer des interfaces riches avec un système de widgets et de callbacks asynchrones, très similaire à ce qu'on trouve dans le développement web moderne.

### Le fichier `tui.py`
L'application `ObsiRAGTUI` gère :
- Une barre de recherche (widget `Input`).
- Une zone d'affichage des résultats avec rendu Markdown en temps réel (widget `Markdown`).
- La communication asynchrone avec le backend via `httpx` (streaming SSE).
- Un thème global "dracula" pour un look moderne en console.

### 💡 Snippet pédagogique : Les bases de Textual

Si tu souhaites réutiliser `textual` pour d'autres projets, voici la structure minimale pour comprendre comment ça fonctionne :

```python
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Label
from textual import work

class MonApp(App):
    # 1. Définition du thème ou du CSS (optionnel)
    theme = "dracula" 
    
    # 2. Raccourcis clavier globaux
    BINDINGS = [("q", "quit", "Quitter l'application")]

    # 3. La méthode compose() définit la structure de l'interface (comme du HTML)
    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Tapez quelque chose...", id="mon-input")
        yield Label("En attente...", id="mon-label")
        yield Footer()

    # 4. Gestion des événements (callbacks basés sur les actions de l'utilisateur)
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        # Récupération du widget cible
        label = self.query_one("#mon-label", Label)
        
        # Action immédiate sur l'UI
        label.update(f"⏳ Traitement de : {event.value}")
        
        # Lancement d'une tâche de fond (API call, calcul lourd...)
        self.faire_quelque_chose_en_fond(event.value)

    # 5. Le décorateur @work permet d'exécuter des requêtes asynchrones en arrière-plan sans bloquer l'UI
    @work(exclusive=True)
    async def faire_quelque_chose_en_fond(self, texte: str):
        # Simulation d'un traitement long
        import asyncio
        await asyncio.sleep(2)
        
        # Mise à jour de l'UI une fois la tâche terminée
        label = self.query_one("#mon-label", Label)
        label.update(f"✅ Terminé ! Vous avez tapé : {texte}")

if __name__ == "__main__":
    MonApp().run()
```

Concepts clés :
- `compose()` : C'est le "render" de l'application. On y place les widgets (Header, Input, Markdown...).
- `query_one(selecteur)` : Permet de cibler un composant spécifique (comme `document.querySelector` en JS).
- `@work` : Indispensable pour tout ce qui fait appel au réseau (`httpx`) ou à des traitements de données longs, pour éviter que l'interface ne "freeze".

---

## 2. Nettoyage et renommage du Backend

L'interface web n'étant plus nécessaire :
1. Suppression du dossier `templates/` et de `index.html`.
2. Suppression de l'utilisation de `Jinja2Templates` dans FastAPI.
3. Renommage du fichier serveur principal `web_ui.py` en **`fastAPI.py`**, ce qui décrit beaucoup mieux son rôle actuel : servir uniquement des endpoints REST/SSE (comme `/api/ask`).

---

## 3. Mise à jour du modèle d'IA
Dans `rag/config.py`, le `GENERATION_MODEL` a été mis à jour par le modèle local Ollama : `hf.co/bartowski/LiquidAI_LFM2-24B-A2B-GGUF:Q4_K_M`.
