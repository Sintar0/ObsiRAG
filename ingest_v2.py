import os
import re
import time

import chromadb
import ollama

# --- CONFIGURATION ---
VAULT_PATH = "./Obsidian"

# Dossiers à ignorer (Sensible à la casse !)
EXCLUDED_DIRS = {
    "Excalidraw",
    "Images",
    "Assets",
    "Attachments",
    ".obsidian",
    ".git",
    ".trash",
}

# --- SETUP ---
DB_PATH = "./chroma_db"
COLLECTION_NAME = "obsidian-vault"
client = chromadb.PersistentClient(path=DB_PATH)
collection = client.get_or_create_collection(name=COLLECTION_NAME)


def embed_text(text):
    try:
        response = ollama.embeddings(model="nomic-embed-text", prompt=text)
        return response["embedding"]
    except Exception as e:
        print(f"\n❌ Erreur Ollama sur un chunk : {e}")
        return None


def smart_chunk(content):
    """
    Stratégie de chunking optimisée basée sur l'analyse du Vault :
    
    1. Fichiers avec titres (56%) : découper par titres ## et ###
    2. Fichiers avec listes (59%) : découper par items si > 5 items
    3. Fichiers sans structure (33%) : découper par paragraphes
    4. Regrouper les sections courtes (< 150 chars)
    """
    
    lines = content.split("\n")
    chunks = []
    
    # Détecter la structure du fichier
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
    headings = []
    
    for i, line in enumerate(lines):
        match = heading_pattern.match(line.strip())
        if match:
            level = len(match.group(1))
            headings.append((i, level, line.strip()))
    
    # Compter les items de liste
    list_items = [i for i, line in enumerate(lines) if re.match(r'^[\s]*[-*+]\s+', line)]
    
    # STRATÉGIE 1 : Fichiers avec titres
    if len(headings) > 0:
        chunks = chunk_by_headings_smart(lines, headings)
    
    # STRATÉGIE 2 : Fichiers avec beaucoup de listes (> 5 items) mais sans titres
    elif len(list_items) > 5:
        chunks = chunk_by_list_items(lines, list_items)
    
    # STRATÉGIE 3 : Fichiers sans structure - découper par paragraphes
    else:
        chunks = chunk_by_paragraphs(content)
    
    # Post-traitement : regrouper les chunks trop courts
    chunks = merge_short_chunks(chunks, min_length=150)
    
    return chunks


def chunk_by_headings_smart(lines, headings):
    """
    Découpe par titres avec gestion intelligente :
    - Privilégier les niveaux ## et ### (les plus utilisés)
    - Découper les sections avec beaucoup de listes
    """
    chunks = []
    
    for i, (start_idx, level, heading) in enumerate(headings):
        end_idx = headings[i + 1][0] if i < len(headings) - 1 else len(lines)
        
        section_lines = lines[start_idx:end_idx]
        section_content = "\n".join(section_lines).strip()
        
        # Si la section contient beaucoup de listes (> 5), découper par items
        list_count = sum(1 for line in section_lines if re.match(r'^[\s]*[-*+]\s+', line))
        
        if list_count > 5:
            # Découper cette section par items de liste
            list_items = [j for j, line in enumerate(section_lines) 
                         if re.match(r'^[\s]*[-*+]\s+', line)]
            sub_chunks = chunk_section_by_lists(section_lines, list_items, heading)
            chunks.extend(sub_chunks)
        else:
            # Garder la section entière
            if len(section_content) > 50:
                chunks.append(section_content)
    
    return chunks


def chunk_section_by_lists(section_lines, list_indices, parent_heading):
    """
    Découpe une section par items de liste en gardant le contexte du titre parent
    """
    chunks = []
    current_item = []
    
    for i, line in enumerate(section_lines):
        if i in list_indices:
            # Sauvegarder l'item précédent
            if current_item:
                item_text = "\n".join(current_item).strip()
                if len(item_text) > 30:
                    # Ajouter le contexte du titre parent
                    chunk_with_context = f"{parent_heading}\n\n{item_text}"
                    chunks.append(chunk_with_context)
            
            # Commencer un nouvel item
            current_item = [line]
        elif current_item:
            # Ligne de continuation
            current_item.append(line)
        elif line.strip() and not re.match(r'^#{1,6}\s+', line.strip()):
            # Contenu avant la première liste
            current_item.append(line)
    
    # Dernier item
    if current_item:
        item_text = "\n".join(current_item).strip()
        if len(item_text) > 30:
            chunk_with_context = f"{parent_heading}\n\n{item_text}"
            chunks.append(chunk_with_context)
    
    return chunks


def chunk_by_list_items(lines, list_indices):
    """
    Découpe par items de liste pour les fichiers sans titres
    """
    chunks = []
    current_item = []
    
    for i, line in enumerate(lines):
        if i in list_indices:
            if current_item:
                item_text = "\n".join(current_item).strip()
                if len(item_text) > 30:
                    chunks.append(item_text)
            current_item = [line]
        elif current_item:
            current_item.append(line)
        elif line.strip():
            current_item.append(line)
    
    if current_item:
        item_text = "\n".join(current_item).strip()
        if len(item_text) > 30:
            chunks.append(item_text)
    
    return chunks


def chunk_by_paragraphs(content):
    """
    Découpe par paragraphes pour les fichiers sans structure
    Taille cible : 300-500 caractères
    """
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    chunks = []
    current_chunk = []
    current_length = 0
    
    for para in paragraphs:
        para_length = len(para)
        
        # Si le paragraphe est déjà assez long, le garder seul
        if para_length > 300:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            chunks.append(para)
        
        # Sinon, regrouper jusqu'à atteindre 300-500 chars
        elif current_length + para_length < 500:
            current_chunk.append(para)
            current_length += para_length
        else:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
            current_chunk = [para]
            current_length = para_length
    
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
    
    return chunks


def merge_short_chunks(chunks, min_length=150):
    """
    Regroupe les chunks trop courts (< min_length) avec leurs voisins
    """
    if not chunks:
        return chunks
    
    merged = []
    current = chunks[0]
    
    for i in range(1, len(chunks)):
        if len(current) < min_length:
            # Fusionner avec le suivant
            current = current + "\n\n" + chunks[i]
        else:
            merged.append(current)
            current = chunks[i]
    
    # Ajouter le dernier
    if current:
        merged.append(current)
    
    return merged


def process_file(file_path):
    """Traite un fichier unique"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        chunks = smart_chunk(content)
        if not chunks:
            return 0

        ids = []
        embeddings = []
        documents = []
        metadatas = []

        base_name = os.path.basename(file_path)

        for i, chunk in enumerate(chunks):
            vector = embed_text(chunk)
            if vector is None:
                continue

            chunk_id = f"{base_name}_{i}"

            ids.append(chunk_id)
            embeddings.append(vector)
            documents.append(chunk)
            metadatas.append({"source": base_name, "path": file_path})

        if ids:
            collection.add(
                ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
            )
            return len(ids)

    except Exception as e:
        print(f"⚠️ Erreur lecture fichier {file_path}: {e}")
        return 0
    return 0


def crawl_and_ingest(root_path):
    print(f"🚀 Démarrage de l'indexation de : {root_path}")
    print(f"🚫 Dossiers exclus : {', '.join(EXCLUDED_DIRS)}\n")

    total_files = 0
    total_chunks = 0

    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]

        for file in files:
            if file.endswith(".md"):
                full_path = os.path.join(root, file)

                print(f"📄 Traitement : {file}...", end="\r")

                chunks_count = process_file(full_path)
                total_files += 1
                total_chunks += chunks_count

    print("\n" + "=" * 50)
    print(f"✅ TERMINE !")
    print(f"📚 Fichiers scannés : {total_files}")
    print(f"🧩 Chunks vectorisés : {total_chunks}")
    print(f"💾 Base de données : {DB_PATH}")


if __name__ == "__main__":
    if not os.path.exists(VAULT_PATH):
        print(f"❌ Erreur : Le dossier '{VAULT_PATH}' n'existe pas.")
        print("-> Modifie la variable VAULT_PATH ligne 8.")
    else:
        print(f"⚠️  Attention : La base de données existante sera utilisée.")
        print(
            f"   Pour effacer les données existantes, supprimez le dossier '{DB_PATH}'"
        )

        crawl_and_ingest(VAULT_PATH)
