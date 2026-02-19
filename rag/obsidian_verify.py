import os
import re
import ssl
import urllib.parse
import urllib.request

from .config import (
    OBSIDIAN_API_KEY,
    OBSIDIAN_HOST,
    OBSIDIAN_PORT,
    OBSIDIAN_VERIFY_SNIPPET_CHARS,
    OBSIDIAN_VERIFY_TOP_FILES,
    VAULT_ROOT,
)
from .text_processing import extract_keywords, normalize_text


def source_to_vault_path(source_path: str) -> str | None:
    if not source_path:
        return None

    try:
        abs_source = os.path.abspath(source_path)
        if abs_source.startswith(VAULT_ROOT + os.sep):
            return os.path.relpath(abs_source, VAULT_ROOT).replace("\\", "/")
    except Exception:
        pass

    marker = "/Obsidian/"
    if marker in source_path:
        return source_path.split(marker, 1)[1].replace("\\", "/")

    return os.path.basename(source_path)


def build_vault_index() -> tuple[dict[str, str], dict[str, list[str]]]:
    by_rel_path: dict[str, str] = {}
    by_basename: dict[str, list[str]] = {}

    if not os.path.isdir(VAULT_ROOT):
        return by_rel_path, by_basename

    for root, _, files in os.walk(VAULT_ROOT):
        for name in files:
            if not name.lower().endswith(".md"):
                continue
            abs_path = os.path.join(root, name)
            rel_path = os.path.relpath(abs_path, VAULT_ROOT).replace("\\", "/")

            by_rel_path[rel_path.lower()] = rel_path
            by_basename.setdefault(name.lower(), []).append(rel_path)

    return by_rel_path, by_basename


def extract_wikilinks(note_text: str) -> list[str]:
    links = re.findall(r"\[\[([^\]]+)\]\]", note_text)
    cleaned = []
    for link in links:
        target = link.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            cleaned.append(target)
    return list(dict.fromkeys(cleaned))


def resolve_note_link(link_target: str, by_rel_path: dict[str, str], by_basename: dict[str, list[str]]) -> str | None:
    candidate = link_target.strip().replace("\\", "/")
    if not candidate:
        return None

    if not candidate.lower().endswith(".md"):
        candidate_md = f"{candidate}.md"
    else:
        candidate_md = candidate

    direct = by_rel_path.get(candidate_md.lower())
    if direct:
        return direct

    basename = os.path.basename(candidate_md).lower()
    matches = by_basename.get(basename, [])
    if matches:
        return matches[0]

    return None


def find_query_note_paths(query: str, by_rel_path: dict[str, str], by_basename: dict[str, list[str]], limit: int = 2) -> list[str]:
    if not query:
        return []

    query_norm = normalize_text(query)
    query_keywords = set(extract_keywords(query))
    scored: list[tuple[int, str]] = []

    for rel_lower, rel_path in by_rel_path.items():
        _ = rel_lower
        stem = os.path.splitext(os.path.basename(rel_path))[0]
        stem_norm = normalize_text(stem)
        stem_keywords = set(extract_keywords(stem))

        overlap = len(query_keywords & stem_keywords)
        score = overlap

        if stem_norm and stem_norm in query_norm:
            score += 4

        if score > 0:
            scored.append((score, rel_path))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in scored[:limit]]


def fetch_obsidian_note(vault_rel_path: str) -> str | None:
    if not vault_rel_path:
        return None

    if OBSIDIAN_API_KEY:
        encoded_path = urllib.parse.quote(vault_rel_path)
        url = f"https://{OBSIDIAN_HOST}:{OBSIDIAN_PORT}/vault/{encoded_path}"
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {OBSIDIAN_API_KEY}"},
            method="GET",
        )
        context = ssl._create_unverified_context()

        try:
            with urllib.request.urlopen(request, timeout=4, context=context) as response:
                return response.read().decode("utf-8", errors="replace")
        except Exception:
            pass

    local_path = os.path.join(VAULT_ROOT, vault_rel_path)
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as file:
                return file.read()
        except Exception:
            return None

    return None


def extract_passages(note_text: str, keywords: list[str], max_chars: int) -> str:
    if not note_text:
        return ""

    lines = note_text.splitlines()
    if not lines:
        return ""

    hit_indices = []
    if keywords:
        for idx, line in enumerate(lines):
            line_norm = normalize_text(line)
            if any(keyword in line_norm for keyword in keywords):
                hit_indices.append(idx)

    snippets = []
    seen = set()

    for idx in hit_indices[:8]:
        start = max(0, idx - 2)
        end = min(len(lines), idx + 3)
        key = (start, end)
        if key in seen:
            continue
        seen.add(key)
        snippet = "\n".join(lines[start:end]).strip()
        if snippet:
            snippets.append(snippet)

    if not snippets:
        snippets.append("\n".join(lines[:12]).strip())

    combined = "\n...\n".join(snippets).strip()
    if len(combined) > max_chars:
        combined = combined[:max_chars].rsplit(" ", 1)[0] + "..."

    return combined


def build_verified_context(metadatas, keywords: list[str], query: str = "") -> str:
    verified_blocks = []
    seen_paths = set()

    by_rel_path, by_basename = build_vault_index()
    candidate_paths: list[str] = []

    # 1) Priorité aux notes explicitement suggérées par la requête utilisateur.
    candidate_paths.extend(find_query_note_paths(query, by_rel_path, by_basename))

    # 2) Ensuite notes candidates remontées par le RAG.
    for meta in metadatas:
        source_path = meta.get("path") or meta.get("source", "")
        vault_rel = source_to_vault_path(source_path)
        if not vault_rel:
            continue
        candidate_paths.append(vault_rel)

    queue = []
    for path in candidate_paths:
        resolved = resolve_note_link(path, by_rel_path, by_basename)
        if resolved and resolved not in queue:
            queue.append(resolved)

    idx = 0
    while idx < len(queue) and len(verified_blocks) < OBSIDIAN_VERIFY_TOP_FILES:
        vault_rel = queue[idx]
        idx += 1

        if vault_rel in seen_paths:
            continue
        seen_paths.add(vault_rel)

        note_text = fetch_obsidian_note(vault_rel)
        if not note_text:
            continue

        passage = extract_passages(note_text, keywords, OBSIDIAN_VERIFY_SNIPPET_CHARS)
        if not passage:
            continue

        verified_blocks.append(
            "---\n"
            f"SOURCE_NOTE_COMPLETE: {vault_rel}\n"
            f"EXTRAITS_VERIFIES:\n{passage}\n"
        )

        # 3) Enrichissement: suivre les wikilinks de 1er niveau (style [[Grand orale]]).
        for link in extract_wikilinks(note_text):
            linked = resolve_note_link(link, by_rel_path, by_basename)
            if linked and linked not in seen_paths and linked not in queue:
                queue.append(linked)

    return "\n".join(verified_blocks)
