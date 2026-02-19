pip install chromadb ollama
```

2. Assurez-vous que Ollama est en cours d'exécution:
```bash
ollama serve
```

3. Télécharger le modèle d'embedding requis:
```bash
ollama pull nomic-embed-text
```

## Utilisation

```python
from ingest import ingest_file

# Ingestion d'un seul fichier
ingest_file("chemin/vers/votre/fichier/markdown.md")

# Ou traitement de plusieurs fichiers
import os
for filename in os.listdir("chemin/vers/votre/coffre-fort"):
    if filename.endswith(".md"):
        ingest_file(os.path.join("chemin/vers/votre/coffre-fort", filename))
```

## Stratégie de découpage

Le système utilise le découpage basé sur les titres au lieu du simple découpage par paragraphes:

- Le contenu est divisé par les titres markdown (`#`, `##`, `###`, etc.)
- Chaque titre et son contenu forment une unité sémantique
- Cette approche préserve la structure du document et améliore la qualité de la récupération

## Structure du projet

- `ingest.py`: Logique principale d'ingestion avec découpage basé sur les titres
- `test_chunking.py`: Fichier de test pour vérifier l'implémentation du découpage
- `main.py`: Interface en ligne de commande pour l'ingestion