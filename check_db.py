import random
from textwrap import shorten

import chromadb

# --- CONFIG ---
DB_PATH = "./chroma_db"
COLLECTION_NAME = "obsidian-vault"

# Connexion
client = chromadb.PersistentClient(path=DB_PATH)
try:
    collection = client.get_collection(name=COLLECTION_NAME)
except Exception as e:
    print(
        f"❌ Erreur : La collection '{COLLECTION_NAME}' n'existe pas. As-tu lancé ingest.py ?"
    )
    exit()

# 1. Le Comptage
count = collection.count()
print(f"\n📊 ÉTAT DE LA BASE DE DONNÉES")
print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"📚 Total de vecteurs (chunks) : {count}")

if count == 0:
    print("⚠️  La base est vide ! Vérifie ton chemin VAULT_PATH dans ingest.py.")
    exit()

# 2. L'Inspection (Peek)
# On regarde les 10 premiers items pour voir la structure
print(f"\n🔍 INSPECTION (Echantillon de 3 items)")
print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

data = collection.peek(limit=10)
ids = data["ids"]
documents = data["documents"]
metadatas = data["metadatas"]

# On prend 3 index au hasard parmi les 10 premiers (ou moins si <10)
indices = random.sample(range(len(ids)), min(3, len(ids)))

for idx in indices:
    print(f"\n🆔 ID      : {ids[idx]}")
    print(
        f"📂 Source  : {metadatas[idx].get('source', 'Inconnue')} (Path: {metadatas[idx].get('path', '?')})"
    )
    print(f'📝 Contenu : "{shorten(documents[idx], width=100, placeholder="...")}"')
    print("-" * 30)

print("\n✅ Si tu vois des titres et du texte cohérent ci-dessus, c'est gagné.")
