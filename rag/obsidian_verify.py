import os
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
from .text_processing import normalize_text


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


def build_verified_context(metadatas, keywords: list[str]) -> str:
    verified_blocks = []
    seen_paths = set()

    for meta in metadatas:
        source_path = meta.get("path") or meta.get("source", "")
        vault_rel = source_to_vault_path(source_path)
        if not vault_rel or vault_rel in seen_paths:
            continue
        seen_paths.add(vault_rel)

        note_text = fetch_obsidian_note(vault_rel)
        if not note_text:
            continue

        passage = extract_passages(note_text, keywords, OBSIDIAN_VERIFY_SNIPPET_CHARS)
        if not passage:
            continue

        verified_blocks.append(
            f"---\nSOURCE_NOTE_COMPLETE: {vault_rel}\nEXTRAITS_VERIFIES:\n{passage}\n"
        )

        if len(verified_blocks) >= OBSIDIAN_VERIFY_TOP_FILES:
            break

    return "\n".join(verified_blocks)
