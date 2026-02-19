# Dev session — Projet 1 (Obsidian RAG) — 2026-02-18

## Ce qui a été fait (V0)

* Mise en place d’un **pipeline RAG minimal** en Python, local, sans interface.
* Indexation du Vault Obsidian dans une **base vectorielle persistante** (ChromaDB).
* Implémentation d’une **recherche vectorielle** sur les chunks, puis génération d’une réponse via un modèle LLM.
* Ajout d’un script de **vérification rapide** de la base (compte + échantillons).

Scripts concernés :

* `ingest.py` : indexation du Vault → chunks → embeddings → stockage en base. 
* `check_db.py` : contrôle de la base (count + peek). 
* `query.py` : question → embedding → retrieval → prompt RAG → réponse du LLM. 

---

## Principe du chunking

Le Vault contient des notes longues et multi-sujets. Indexer un fichier entier en un seul vecteur est rarement efficace : on perd en précision et on récupère trop de contenu inutile.

En V0, on découpe une note en **chunks** :

* Découpage principal : **par headings Markdown** (`#`, `##`, `###`, etc.). Chaque chunk correspond à une section (le titre est inclus dans le texte du chunk pour aider la similarité sémantique). 
* Fallback : si aucun heading n’est présent, découpage en **paragraphes** (`\n\n`). 
* Filtrage : on ignore les chunks trop petits (pour éviter d’indexer des titres vides ou des sections non informatives). 

But : améliorer la précision du retrieval en ramenant un contexte court, pertinent, et facilement “citable”.

---

## Principe de la base vectorielle (ChromaDB)

Chaque chunk est transformé en embedding (vecteur numérique) et stocké dans une base vectorielle persistante (`./chroma_db`). 

Au moment d’une question :

1. On calcule l’embedding de la question.
2. On demande à la base les `top_k` chunks les plus proches.
3. On injecte ces chunks comme **contexte** dans le prompt du LLM, avec des sources. 

---

## Rôle des fichiers

### `ingest.py`

Responsabilités :

* Parcourir le Vault (`VAULT_PATH`) et ne prendre que les `.md`.
* Exclure certains dossiers (`.obsidian`, attachments, images, etc.). 
* Lire chaque note, appliquer le chunking, générer les embeddings via Ollama (`nomic-embed-text`) puis ajouter en base (documents + métadonnées). 

Résultat : une base ChromaDB remplie de chunks vectorisés.

### `check_db.py`

Responsabilités :

* Se connecter à la base et afficher :

  * le nombre total de chunks indexés (`count`)
  * un aperçu de quelques entrées (`peek`) pour valider que le contenu est cohérent (IDs, source, extrait). 

### `query.py`

Responsabilités :

* Prendre une question en mode interactif.
* Calculer l’embedding de la question, interroger ChromaDB et récupérer les chunks pertinents. 
* Construire un prompt “strict” : répondre uniquement avec le contexte, sinon avouer l’absence d’info, et citer les sources. 
* Appeler le modèle de génération (Mistral) et streamer la réponse dans le terminal. 

---

## TODO (suite logique après V0)

### Qualité / Robustesse

* Corriger le risque de **collision d’IDs** : actuellement `chunk_id = f"{base_name}_{i}"` peut entrer en conflit si deux notes ont le même nom dans des dossiers différents. 

  * Solution : inclure le chemin (slug) ou un hash (`sha1(file_path + i)`).
* Ajouter un vrai **mode “search”** : afficher les chunks + scores + chemins sans appeler le LLM (debug retrieval).
* Ajouter une **limite de taille chunk** + éventuel split des sections trop longues.
* Ajouter un **top_k configurable** et tester l’impact (ex: 5, 8, 12).

### Documentation / Évaluation

* Créer un mini dataset de **20 questions** “connues” et mesurer :

  * recall (la bonne note remonte-t-elle ?)
  * cohérence des sources
  * latence
* Documenter les paramètres retenus (chunking, top_k, modèle embeddings, modèle génération).

### Intégration future

* Exposer une **API FastAPI** (V0.5/V1) :

  * `POST /search`
  * `POST /query`
* UI : Portal (webview Obsidian) puis plugin Obsidian (plus tard).

---

Si tu veux, je te réécris aussi une version “README repo” plus courte (orientée installation + commandes) à mettre à la racine du projet, en complément de cette note “dev session”.
