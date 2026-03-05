# Dev session — Projet 1 (Obsidian RAG) — Log 4 — 2026-03-05

## Objectif de cette session

**Audit de code complet** du projet suivi de l'application systématique des correctifs identifiés, puis swap du modèle de génération.

---

## Ce qui a été fait

### 1) Audit de code — 14 points identifiés

Un audit complet a été réalisé sur les 9 fichiers Python + le template HTML. Les problèmes ont été classés par priorité (P0 critique → P3 nice-to-have).

**Points positifs relevés :**
- Architecture modulaire (`rag/` bien découpé)
- Chunking adaptatif intelligent (titres → listes → paragraphes)
- Approche MCP-first + RAG en complément
- Suivi des wikilinks de 1er niveau
- Sécurité d'écriture (path validation, confirmation CLI)

---

### 2) P0 — Dé-duplication de la logique RAG

**Bug :** `web_ui.py` contenait une copie intégrale de la logique de `generate_answer()` dans un helper `_build_answer_stream()` (42 lignes dupliquées). Toute modification du prompt ou de la logique de contexte dans `answering.py` n'était pas reflétée dans la Web UI.

**Correction :** extraction d'une nouvelle fonction réutilisable dans `rag/answering.py` :

```python
def build_rag_context(query: str, n_results: int = 15) -> tuple[str, str, list[str]]:
    """Retourne (system_prompt, user_query, sources)."""
```

Le prompt système est aussi factorisé dans `_build_system_prompt(context_text)`.

`web_ui.py` appelle maintenant `build_rag_context()` directement — le helper `_build_answer_stream()` est supprimé.

Fichiers concernés :
- `rag/answering.py`, `web_ui.py`, `rag/__init__.py`

---

### 3) P0 — Gestion d'erreur sur les appels Ollama

**Bug :** aucun `try/except` autour des appels `ollama.chat()` dans la Web UI. Si Ollama est down ou le modèle absent → erreur 500 non descriptive.

**Correction :** ajout de `try/except` sur les endpoints `/api/ask` et `/api/note/edit`. En cas d'erreur, le stream SSE renvoie un message `❌ Erreur LLM : ...` visible par l'utilisateur au lieu d'un crash silencieux.

Ajout de `import logging` et d'un `logger` pour tracer les erreurs côté serveur.

Fichiers concernés :
- `web_ui.py`

---

### 4) P1 — Centralisation des constantes

**Bug :** 4 constantes identiques (`VAULT_PATH`, `DB_PATH`, `COLLECTION_NAME`, `EMBEDDING_MODEL`) étaient redéfinies dans `ingest.py`, `check_db.py` et `analyze_vault.py` au lieu d'importer depuis `rag/config.py`. Notamment, `ingest.py` hardcodait `~/Obsidian` et ignorait la variable d'environnement `VAULT_PATH`.

**Correction :** les 3 fichiers importent maintenant depuis `rag.config`. Une seule source de vérité.

Fichiers concernés :
- `ingest.py`, `check_db.py`, `analyze_vault.py`

---

### 5) P2 — Collision d'IDs de chunks

**Bug :** `chunk_id = f"{base_name}_{i}"` — deux fichiers dans des dossiers différents mais avec le même nom (ex: `README.md`) écrasaient silencieusement leurs chunks mutuels dans ChromaDB.

**Correction :** `chunk_id = f"{rel_path}_{i}"` — utilisation du chemin relatif au vault.

**Conséquence :** nécessite une réingestion complète (`rm -rf chroma_db/ && uv run ingest.py`).

Fichiers concernés :
- `ingest.py`

---

### 6) P2 — Échappement HTML

**Bug :** l'endpoint `/api/search` échappait manuellement `<` et `>` avec `.replace()`, oubliant `&`, `"` et `'`.

**Correction :** remplacement par `html.escape()` du module standard.

Fichiers concernés :
- `web_ui.py`

---

### 7) Fix — `retrieval.py` crash à l'import si DB vide

**Bug découvert pendant les tests :** `rag/retrieval.py` utilisait `client.get_collection()` au niveau module, ce qui crashait si la collection ChromaDB n'existait pas encore (ex: après un `rm -rf chroma_db/`).

**Correction :** remplacé par `client.get_or_create_collection()`.

Fichiers concernés :
- `rag/retrieval.py`

---

### 8) Swap de modèle : mistral-small3.2 → qwen3.5:9b

Remplacement du modèle de génération pour des réponses potentiellement plus rapides.

Fichiers concernés :
- `rag/config.py` (`GENERATION_MODEL`)
- `templates/index.html` (header UI)

---

## Résumé des fichiers modifiés

| Fichier | Changements |
|---|---|
| `rag/answering.py` | +`build_rag_context()`, +`_build_system_prompt()` |
| `rag/config.py` | Modèle → `qwen3.5:9b` |
| `rag/retrieval.py` | `get_collection` → `get_or_create_collection` |
| `rag/__init__.py` | Export de `build_rag_context` |
| `web_ui.py` | Suppression duplication, +error handling, +`html.escape`, +logging |
| `ingest.py` | Imports centralisés, chunk IDs uniques |
| `check_db.py` | Imports centralisés |
| `analyze_vault.py` | Import centralisé |
| `templates/index.html` | Header model name |

---

## Leçon retenue

**Un audit de code régulier est un bon investissement**, même sur un projet solo. Les bugs de duplication (logique RAG dupliquée, constantes redéfinies) sont invisibles au quotidien mais deviennent des pièges dès qu'on modifie une seule des copies.

La règle : **une seule source de vérité** pour chaque information (config, prompt système, logique métier).

---

## Suite recommandée

- Ajouter un système d'ingestion incrémentale (stockage des `mtime`, ré-ingestion sélective)
- Remplacer les `print()` par `logging` dans tout le projet
- Écrire des tests unitaires pour le parsing d'édition et le chunking
- Évaluer la qualité des réponses `qwen3.5:9b` vs `mistral-small3.2`
