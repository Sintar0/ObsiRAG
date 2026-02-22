# Dev session — Projet 1 (Obsidian RAG) — Log 3.5 — 2026-02-22

## Objectif de ce point d'étape

Construire une **Web UI FastAPI + HTMX** exposant le pipeline RAG, puis l'affiner en une interface d'édition LLM-assistée centrée sur les notes Obsidian.

---

## Ce qui a été construit (depuis Log 3)

### 1) Serveur Web FastAPI (`web_ui.py`)

Un serveur FastAPI expose le pipeline RAG via HTTP :

| Route | Rôle |
|---|---|
| `GET /` | Sert le template HTML |
| `POST /api/ask` | Question → réponse LLM en streaming SSE |
| `GET /api/notes/list` | Liste tous les `.md` du vault |
| `POST /api/note/get` | Lit une note via l'API REST Obsidian |
| `POST /api/note/edit` | Propose une version modifiée de la note par le LLM (streaming) |
| `POST /api/note/write` | Écrit la proposition dans le vault via l'API REST Obsidian |

**Choix techniques :**
- **HTMX** pour le frontend : zéro Node.js, zéro build step, HTML servi directement.
- **Jinja2** pour le templating côté serveur.
- **SSE (Server-Sent Events)** pour le streaming des réponses LLM token par token.
- **`python-dotenv`** pour charger `OBSIDIAN_API_KEY` depuis `.env`.

**Intérêt pédagogique :**
- FastAPI + HTMX est une stack légère idéale pour prototyper des interfaces IA sans overhead frontend.
- Le streaming SSE permet un retour visuel immédiat sans WebSocket.

Fichiers concernés :
- `web_ui.py`, `templates/index.html`

---

### 2) Interface en 2 onglets

Après une première version avec 4 onglets (Ask / Search / TODO / Note), l'interface a été **simplifiée à 2 onglets** suite à un retour d'expérience :

- **Search** : redondant avec un bon prompt Ask.
- **TODO** : gimmick, bypassable par un prompt Ask bien formé.

**Onglets conservés :**

#### 💬 Ask
- Champ de question + streaming token par token
- Barre de sources affichée après la réponse
- Rendu Markdown + KaTeX à la fin du stream

#### 📝 Note — éditeur LLM-assisté (split view)
- **Gauche** : `textarea` éditable avec la note originale (source brute)
- **Droite** : preview rendu en Markdown + KaTeX
  - Au chargement : affiche la note originale rendue
  - Après instruction : affiche la proposition LLM en streaming, puis rendue
- **Barre d'instruction** : champ texte libre → le LLM retravaille la note entière
- **Bouton "💾 Écrire dans le vault"** : activé uniquement quand une proposition est prête

**Intérêt pédagogique :**
- Le split view source/preview est un pattern classique des éditeurs Markdown (ex: Typora, HackMD).
- Désactiver le bouton d'écriture jusqu'à validation évite les écritures accidentelles.

---

### 3) Rendu Markdown + KaTeX (CDN, sans build)

Deux bibliothèques ajoutées via CDN :

- **Marked.js** : rendu Markdown complet (titres, listes, code, blockquotes, bold)
- **KaTeX** + `auto-render` : rendu LaTeX avec les délimiteurs `$...$`, `$$...$$`, `\(...\)`, `\[...\]`

Appliqué sur : réponses Ask, note originale chargée, proposition LLM.

**Comportement streaming :** texte brut affiché pendant la génération → `renderMarkdown()` appelé une fois `done` reçu pour éviter le re-rendu à chaque token.

---

### 4) Autocomplétion des noms de notes

Le champ de chemin de note utilise un `<datalist>` HTML natif alimenté par `/api/notes/list` au chargement de la page.

- Filtre en temps réel en tapant
- Gère les espaces dans les noms de fichiers
- Zéro dépendance JS supplémentaire

---

### 5) Spinner d'attente LLM

**CLI (`rag/answering.py`) :**
- Spinner `\ | / -` animé dans un thread daemon pendant que le LLM "réfléchit"
- S'arrête proprement dès le premier token reçu
- S'efface avec `\r   \r` pour ne pas polluer la sortie

**Web UI (`templates/index.html`) :**
- Barre de progression CSS animée (slide horizontal, couleur accent)
- Affichée avec "Réflexion en cours…" pendant l'attente
- Disparaît automatiquement au premier chunk

---

### 6) Correction du prompt d'édition

**Bug identifié :** le LLM retournait uniquement le fragment ajouté (ex: "Bonjour !") au lieu de la note entière modifiée.

**Cause :** le prompt système ne précisait pas explicitement que la note complète devait être retournée.

**Correction :** ajout de règles explicites dans le system prompt :
- "Retourne TOUJOURS la note COMPLÈTE avec la modification intégrée — jamais un fragment."
- "Si l'instruction dit 'ajoute X à la fin', copie toute la note puis ajoute X à la fin."

**Intérêt pédagogique :**
- Les LLMs optimisent pour la concision par défaut. Sans contrainte explicite, ils retournent le minimum suffisant pour satisfaire l'instruction littérale.
- Un prompt d'édition doit toujours spécifier le périmètre de la sortie attendue.

Fichiers concernés :
- `web_ui.py`

---

## Ce qui a été testé

- Démarrage du serveur : `uv run python web_ui.py`
- Compilation Python : `web_ui.py`, `rag/answering.py`
- Route `/api/notes/list` : 200 OK, liste chargée dans le datalist
- Route `/api/note/get` : 200 OK, note chargée et rendue
- Route `/api/note/edit` : 200 OK, streaming fonctionnel
- Spinner CLI : thread daemon, arrêt propre au premier token
- Barre de progression Web : animation CSS, disparition au premier chunk

---

## Leçon d'architecture retenue

Une bonne interface d'édition LLM-assistée suit ce schéma :

1. **Charger** la source (note brute éditable)
2. **Afficher** un preview rendu immédiatement (Markdown + KaTeX)
3. **Instruire** le LLM avec une consigne en langage naturel
4. **Streamer** la proposition token par token
5. **Valider** visuellement avant toute écriture
6. **Écrire** uniquement sur action explicite de l'utilisateur

Ce pattern garantit que l'utilisateur reste en contrôle à chaque étape.

---

## Suite recommandée

- Ajouter `vault_note_create` et `vault_note_append` dans le MCP server pour l'édition contrôlée depuis Claude Code
- Envisager un diff visuel avant/après dans le split view
- Ajouter un historique des propositions LLM dans la session
