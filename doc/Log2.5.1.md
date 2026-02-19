# Dev session — Projet 1 (Obsidian RAG) — Log 2.5.1 — 2026-02-19

## Objectif de ce point d'étape

Stabiliser la qualité des réponses en **MCP-first** sans casser les performances observées, puis figer un état fonctionnel satisfaisant.

---

## Ce qui a été amélioré

### 1) Priorité au contexte Obsidian vérifié (MCP-first)

Le flux de génération privilégie désormais les notes complètes vérifiées via la couche Obsidian, puis utilise le RAG en complément.

**Intérêt pédagogique :**
- Le RAG est excellent pour retrouver des indices proches sémantiquement.
- Le MCP/notes complètes est meilleur pour la **fidélité au contenu réel**.
- En mettant MCP en premier, on réduit les réponses "plausibles mais inexactes".

Fichiers concernés:
- `rag/answering.py`

### 2) Exploitation des wikilinks Obsidian `[[...]]`

Le vérificateur suit maintenant les hyperliens de premier niveau depuis une note candidate.

Exemple de bénéfice:
- Si une note journalière contient `[[Grand orale]]`, la note cible peut être chargée directement.

**Intérêt pédagogique :**
- Obsidian n'est pas seulement une collection de fichiers, c'est un **graphe de connaissances**.
- Utiliser les liens permet de retrouver l'information principale même quand le chunk RAG initial est secondaire.

Fichiers concernés:
- `rag/obsidian_verify.py`

### 3) Résolution par titre de note depuis la requête

Ajout d'une logique de scoring simple pour détecter les notes dont le titre correspond à la question utilisateur.

Exemple:
- Requête: "de quoi j'ai parlé pour mon Grand Orale"
- Candidate prioritaire: `Grand orale.md`

**Intérêt pédagogique :**
- Un score lexical simple sur les titres est souvent plus robuste qu'une recherche purement vectorielle pour des entités nominales (noms de note, personnes, événements).

Fichiers concernés:
- `rag/obsidian_verify.py`

### 4) Ajustement du prompt système (moins concis)

Le prompt demande désormais des réponses:
- plus structurées,
- plus détaillées,
- avec mini résumé + points clés quand pertinent.

**Intérêt pédagogique :**
- Une meilleure consigne de style améliore la lisibilité sans modifier le moteur de retrieval.

Fichiers concernés:
- `rag/answering.py`

---

## Ce qui a été testé

- Compilation Python:
  - `uv run python -m py_compile rag/obsidian_verify.py rag/answering.py`

- Validation fonctionnelle sur cas réel:
  - question orientée "Grand Orale"
  - résultat perçu nettement meilleur (meilleure note cible, meilleure qualité de réponse)

---

## Leçon d'architecture retenue

Pour ce projet, l'ordre qui marche le mieux est:

1. **MCP / note complète vérifiée** (source de vérité)
2. **Graphe Obsidian** (wikilinks)
3. **RAG vectoriel** (complément)
4. **LLM** (raisonnement + formulation)

Cette hiérarchie réduit les hallucinations et améliore la pertinence métier.

---

## Suite recommandée (prochain jalon)

- Consolider la robustesse des scores de résolution de note.
- Ajouter une trace debug optionnelle des notes effectivement injectées au contexte.
- Puis seulement reprendre l'extension V1-beta (write sécurisé + confirmation explicite).
