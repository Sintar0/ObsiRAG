#!/usr/bin/env python3
"""
Analyse du Vault Obsidian pour déterminer la stratégie de chunking optimale
"""

import os
import re
from collections import Counter, defaultdict

VAULT_PATH = os.path.expanduser("~/Obsidian")

# Statistiques globales
stats = {
    "total_files": 0,
    "files_with_headings": 0,
    "files_with_lists": 0,
    "files_with_both": 0,
    "files_with_neither": 0,
    "heading_levels": Counter(),
    "list_types": Counter(),
    "avg_file_length": [],
    "avg_section_length": [],
    "list_item_counts": [],
}

# Patterns
heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
bullet_list_pattern = re.compile(r'^[\s]*[-*+]\s+', re.MULTILINE)
numbered_list_pattern = re.compile(r'^[\s]*\d+\.\s+', re.MULTILINE)

def analyze_file(filepath):
    """Analyse un fichier markdown"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Longueur du fichier
        stats["avg_file_length"].append(len(content))
        
        # Recherche de headings
        headings = heading_pattern.findall(content)
        has_headings = len(headings) > 0
        
        if has_headings:
            stats["files_with_headings"] += 1
            for level, _ in headings:
                stats["heading_levels"][len(level)] += 1
        
        # Recherche de listes
        bullet_lists = bullet_list_pattern.findall(content)
        numbered_lists = numbered_list_pattern.findall(content)
        has_lists = len(bullet_lists) > 0 or len(numbered_lists) > 0
        
        if has_lists:
            stats["files_with_lists"] += 1
            if bullet_lists:
                stats["list_types"]["bullet"] += len(bullet_lists)
            if numbered_lists:
                stats["list_types"]["numbered"] += len(numbered_lists)
            
            # Compter les items de liste
            stats["list_item_counts"].append(len(bullet_lists) + len(numbered_lists))
        
        # Classification
        if has_headings and has_lists:
            stats["files_with_both"] += 1
        elif not has_headings and not has_lists:
            stats["files_with_neither"] += 1
        
        # Longueur moyenne des sections (entre headings)
        if has_headings:
            sections = heading_pattern.split(content)
            for i in range(2, len(sections), 3):  # Sauter les groupes de capture
                if i < len(sections):
                    section_content = sections[i] if i < len(sections) else ""
                    if section_content.strip():
                        stats["avg_section_length"].append(len(section_content))
        
        return {
            "has_headings": has_headings,
            "has_lists": has_lists,
            "num_headings": len(headings),
            "num_lists": len(bullet_lists) + len(numbered_lists),
            "length": len(content),
        }
        
    except Exception as e:
        return None

# Parcourir le vault
print("🔍 Analyse du Vault Obsidian...")
print("=" * 80)

excluded_dirs = {".obsidian", ".git", ".trash", "Excalidraw", "Images", "Assets", "Attachments"}

for root, dirs, files in os.walk(VAULT_PATH):
    dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith(".")]
    
    for file in files:
        if file.endswith(".md"):
            stats["total_files"] += 1
            filepath = os.path.join(root, file)
            analyze_file(filepath)

# Affichage des résultats
print(f"\n📊 STATISTIQUES GLOBALES")
print("=" * 80)
print(f"Total de fichiers .md : {stats['total_files']}")

if stats['total_files'] == 0:
    print("\n❌ Aucun fichier .md trouvé dans le Vault!")
    print(f"   Chemin analysé : {VAULT_PATH}")
    exit(1)

print(f"Fichiers avec titres (#) : {stats['files_with_headings']} ({stats['files_with_headings']/stats['total_files']*100:.1f}%)")
print(f"Fichiers avec listes : {stats['files_with_lists']} ({stats['files_with_lists']/stats['total_files']*100:.1f}%)")
print(f"Fichiers avec les deux : {stats['files_with_both']} ({stats['files_with_both']/stats['total_files']*100:.1f}%)")
print(f"Fichiers sans structure : {stats['files_with_neither']} ({stats['files_with_neither']/stats['total_files']*100:.1f}%)")

print(f"\n📏 LONGUEURS MOYENNES")
print("=" * 80)
if stats["avg_file_length"]:
    avg_file = sum(stats["avg_file_length"]) / len(stats["avg_file_length"])
    print(f"Longueur moyenne d'un fichier : {avg_file:.0f} caractères")

if stats["avg_section_length"]:
    avg_section = sum(stats["avg_section_length"]) / len(stats["avg_section_length"])
    print(f"Longueur moyenne d'une section : {avg_section:.0f} caractères")

if stats["list_item_counts"]:
    avg_list_items = sum(stats["list_item_counts"]) / len(stats["list_item_counts"])
    print(f"Nombre moyen d'items de liste par fichier : {avg_list_items:.1f}")

print(f"\n📋 DISTRIBUTION DES TITRES")
print("=" * 80)
for level in sorted(stats["heading_levels"].keys()):
    count = stats["heading_levels"][level]
    print(f"Niveau {'#' * level} : {count} occurrences")

print(f"\n📝 TYPES DE LISTES")
print("=" * 80)
for list_type, count in stats["list_types"].items():
    print(f"{list_type.capitalize()} : {count} items")

print(f"\n💡 RECOMMANDATIONS DE CHUNKING")
print("=" * 80)

# Analyse et recommandations
heading_ratio = stats['files_with_headings'] / stats['total_files']
list_ratio = stats['files_with_lists'] / stats['total_files']

if heading_ratio > 0.7:
    print("✅ Stratégie principale : Chunking par TITRES (#)")
    print("   → La majorité des fichiers ont une structure avec titres")
else:
    print("⚠️  Stratégie principale : Chunking HYBRIDE")
    print("   → Beaucoup de fichiers sans titres")

if list_ratio > 0.5:
    print("✅ Stratégie secondaire : Découpage par ITEMS DE LISTE")
    print("   → Beaucoup de fichiers utilisent des listes")
    
    if stats["list_item_counts"]:
        avg_items = sum(stats["list_item_counts"]) / len(stats["list_item_counts"])
        if avg_items > 10:
            print(f"   → Seuil recommandé : découper si > 5 items (moyenne actuelle : {avg_items:.1f})")
        else:
            print(f"   → Seuil recommandé : découper si > 3 items (moyenne actuelle : {avg_items:.1f})")

if stats["avg_section_length"]:
    avg_section = sum(stats["avg_section_length"]) / len(stats["avg_section_length"])
    if avg_section > 1000:
        print(f"⚠️  Sections longues détectées (moyenne : {avg_section:.0f} chars)")
        print("   → Recommandation : découpage supplémentaire par paragraphes (\\n\\n)")

print("\n" + "=" * 80)
