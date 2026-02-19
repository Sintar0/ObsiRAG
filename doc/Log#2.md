# Dev session — Projet 1 (Obsidian RAG) — 2026-02-19

## Objectif de la session

- Ranger le repo.
- Découper `query.py` en modules plus clairs.
- Supprimer le fichier de test devenu inutile à la racine.
- Produire une cartographie à jour du projet.

---

## Changements réalisés

### 1) Refactor modulaire de `query.py`

`query.py` est maintenant un **point d'entrée léger** (CLI interactive) qui délègue au package `rag/`:

- `rag/retrieval.py` : retrieval Chroma + reformulation + reranking mots-clés
- `rag/answering.py` : construction du contexte + appel LLM
- `rag/obsidian_verify.py` : vérification post-retrieval via API Obsidian (et fallback local)
- `rag/text_processing.py` : normalisation texte + extraction mots-clés
- `rag/config.py` : configuration centralisée
- `rag/styles.py` : styles terminal
- `rag/__init__.py` : exports de haut niveau

`query.py` conserve les fonctions importables (`search_vault`, `generate_answer`) via les imports de façade.

### 2) Nettoyage fichier inutile

Suppression du fichier racine :

- `Révision partiel S3 management Si.md`

Le contenu source est désormais dans un vault Obsidian externe (`~/Obsidian/...`).

### 3) Vérification technique

Compilation Python validée :

- `uv run python -m py_compile query.py rag/*.py`

---

## Cartographie actuelle du projet

```text
obsidian-rag/
├── (vault externe) ~/Obsidian/   # Vault source (notes markdown)
├── chroma_db/                    # Base vectorielle persistante
├── doc/
│   ├── Log#1.md
│   └── Log#2.md
├── rag/
│   ├── __init__.py
│   ├── answering.py              # génération réponse + prompt + contexte
│   ├── config.py                 # constantes et variables d'env
│   ├── obsidian_verify.py        # enrichissement via note complète
│   ├── retrieval.py              # embedding query + Chroma + rerank
│   ├── styles.py                 # couleurs terminal
│   └── text_processing.py        # normalize/extract keywords
├── analyze_vault.py              # statistiques structure du vault
├── check_db.py                   # inspection rapide de la base Chroma
├── ingest.py                     # ingestion/chunking optimisé
├── query.py                      # entrypoint CLI (façade)
├── README.md
├── pyproject.toml
└── uv.lock
```

---

## Flux applicatif actuel (forme cible)

1. `query.py` lit la question utilisateur.
2. `rag.retrieval.search_vault()`
   - reformule la requête si nécessaire,
   - embed la question,
   - récupère top-k Chroma,
   - rerank par mots-clés.
3. `rag.answering.generate_answer()`
   - compresse les chunks,
   - enrichit avec `rag.obsidian_verify.build_verified_context()` (note complète API/fallback local),
   - construit le prompt système,
   - appelle Ollama en stream.

---

## Notes d'architecture

- Le projet fonctionne désormais avec une séparation claire :
  - **retrieval**,
  - **vérification source**,
  - **génération**,
  - **orchestration CLI**.
- Cette structure simplifie les prochaines étapes :
  - ajout d'API web (FastAPI),
  - ajout de tests unitaires par module,
  - tuning retrieval/answering sans modifier l'entrypoint.

---

## Complément par rapport à `doc/Log#1.md`

Par rapport au V0 décrit dans `Log#1`, on a introduit une couche clé :

- **Vérification Obsidian/MCP-like** : après retrieval vectoriel, on recharge la note complète via API Obsidian (ou fallback local) pour enrichir le contexte avant génération.
- Résultat attendu : moins de réponses "robotiques" quand le bon fragment est remonté mais insuffisant seul.

Cette brique prépare le terrain pour des interactions plus "agentiques" avec le vault.

### Vision V1 (prochaine étape)

Objectif V1 : ajouter l'**écriture de notes/tâches** en langage naturel, par exemple :

> "Ajoute-moi dans mon fichier TODO.md une tâche pour faire les courses"

Comportement attendu du système :

1. Identifier la note cible (`TODO.md`) dans le vault.
2. Ajouter la ligne (ou checklist) au bon endroit.
3. Confirmer l'opération avec le chemin de la note modifiée.

Ce sera traité après stabilisation complète du V0 (retrieval + génération + vérification).

---

## Spécification V1 — Édition généraliste de notes (RAG + MCP comme source de vérité)

### Objectif produit

Permettre à l'utilisateur de demander en langage naturel une modification de note Obsidian (ajout, édition, restructuration simple), avec un processus fiable qui limite les hallucinations.

Le système doit utiliser :

- **RAG** pour localiser les notes candidates,
- **MCP/API Obsidian** pour vérifier le contenu réel avant écriture,
- une étape explicite de **prévisualisation + confirmation** avant mutation.

### Cas d'usage V1 (scope)

1. Ajouter du contenu dans une note existante.
2. Modifier un passage ciblé (par titre/section quand possible).
3. Créer une note si demandée explicitement.
4. Ajouter des tâches/checklists dans n'importe quelle note (pas seulement `TODO.md`).

Hors scope V1 :

- modifications multi-notes automatiques sans confirmation,
- refactor massif de structure du vault,
- actions "agentiques" ouvertes sans garde-fous.

### Pipeline fonctionnel V1

1. **Compréhension de l'intention**
   - extraire : action (`add`, `edit`, `create`), cible probable, contenu demandé.
2. **Localisation de la note (RAG)**
   - récupérer les top-k notes candidates avec score.
3. **Vérification source (MCP/API)**
   - charger la note complète réelle,
   - confirmer que la cible existe (ou signaler ambiguïté).
4. **Construction du patch**
   - générer une proposition textuelle de modification (où + quoi).
5. **Prévisualisation**
   - afficher un mini diff (avant/après ou bloc inséré).
6. **Confirmation utilisateur**
   - exiger un `oui` explicite avant écriture.
7. **Application**
   - écrire via API/outil de patch,
   - retourner le chemin exact de la note modifiée.
8. **Journalisation**
   - logger action, cible, patch, timestamp, statut.

### Règles anti-hallucination (obligatoires)

1. **Pas de write si note non résolue**.
2. **Si ambiguïté de cible** : demander à l'utilisateur de choisir.
3. **Pas d'invention de chemin** : toujours vérifier l'existence réelle via MCP/API.
4. **Toujours prévisualiser avant mutation**.
5. **Toujours confirmer l'opération et la note finale** après écriture.

### Critères d'acceptation V1

- Sur un jeu de 20 commandes réelles :
  - >= 90% des modifications vont dans la bonne note,
  - 0 écriture sans confirmation,
  - 0 écriture sur note inexistante,
  - log d'action généré pour 100% des writes.

### Plan d'itération

- **V1-alpha**
  - append/prepend simple,
  - preview + confirmation,
  - log minimal.
- **V1-beta**
  - édition par section/titre,
  - gestion d'ambiguïté robuste,
  - meilleure UX CLI.
- **V1.0.0**
  - stabilité,
  - tests manuels validés,
  - docs à jour.

### Politique de tags Git

- `v1.0.0-alpha.1`
- `v1.0.0-beta.1`
- `v1.0.0`

Règle : un tag est posé uniquement quand les critères de l'étape sont validés.
