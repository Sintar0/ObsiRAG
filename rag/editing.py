import re
from pathlib import Path
from typing import Any, TypedDict

from rag.config import VAULT_ROOT


class EditRequest(TypedDict):
    action: str
    target_file: str | None
    content: str | None
    metadata: dict[str, Any]


class EditCandidate(TypedDict):
    path: str
    score: float
    reason: str


class EditPreview(TypedDict):
    mode: str
    target_file: str
    before: str
    after: str
    instruction: str


ACTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "add": ("ajoute", "ajouter", "insere", "insérer", "append"),
    "edit": ("modifie", "modifier", "edite", "éditer", "replace"),
    "create": ("cree", "crée", "creer", "créer", "nouvelle note"),
}

LEADING_ACTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "edit",
        re.compile(r"^\s*(?:modifie|modifier|edite|édite|éditer|editer)\b", flags=re.IGNORECASE),
    ),
    (
        "create",
        re.compile(r"^\s*(?:crée|cree|créer|creer|nouvelle\s+note)\b", flags=re.IGNORECASE),
    ),
    (
        "add",
        re.compile(r"^\s*(?:ajoute(?:-moi)?|ajouter|insere|insérer|append)\b", flags=re.IGNORECASE),
    ),
)


CONTENT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?:ajoute(?:-moi)?|ajouter)\s+(?:dans|sur)\s+[^:]+?\s+(.+)$",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:modifie|modifier|edite|édite|éditer|editer)\s+[^:]+?\s+(?:pour|avec|:)\s+(.+)$",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:crée|cree|créer|creer)\s+[^:]+?\s+(?:avec|pour|:)\s+(.+)$",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"(?:ajoute(?:-moi)?|ajouter|insere|insérer)\s+(.+)$",
        flags=re.IGNORECASE,
    ),
)


def _detect_action(query: str) -> str:
    for action, pattern in LEADING_ACTION_PATTERNS:
        if pattern.search(query):
            return action

    query_lower = query.lower()
    for action, keywords in ACTION_KEYWORDS.items():
        if any(keyword in query_lower for keyword in keywords):
            return action
    return "unknown"


def _normalize_note_name(raw_target: str) -> str:
    cleaned = raw_target.strip().strip("\"'").strip()
    cleaned = re.sub(
        r"^(ajoute(?:-moi)?|ajouter|modifie|modifier|edite|édite|éditer|editer|crée|cree|créer|creer)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^(la|le|les|mon|ma|mes)\s+(note|fichier)\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" .,;:")
    if not cleaned.lower().endswith(".md"):
        cleaned = f"{cleaned}.md"
    return cleaned


def _extract_target_file(query: str) -> str | None:
    md_patterns = (
        re.compile(r"(?:dans|fichier|note)\s+[\"']?([^\"']+?\.md)[\"']?(?:\s|$)", flags=re.IGNORECASE),
        re.compile(r"[\"']([^\"']+?\.md)[\"']", flags=re.IGNORECASE),
        re.compile(r"\b([\w\-./ ]+?\.md)\b", flags=re.IGNORECASE),
    )

    for pattern in md_patterns:
        match = pattern.search(query)
        if match:
            return _normalize_note_name(match.group(1))

    implicit_patterns = (
        re.compile(r"(?:crée|cree|créer|creer|nouvelle note)\s+[\"']?([^\"']+?)[\"']?(?:\s+(?:avec|pour|:)|$)", flags=re.IGNORECASE),
        re.compile(r"(?:modifie|modifier|edite|édite|éditer|editer)\s+[\"']?([^\"']+?)[\"']?(?:\s+(?:pour|avec|:)|$)", flags=re.IGNORECASE),
    )

    for pattern in implicit_patterns:
        match = pattern.search(query)
        if match:
            return _normalize_note_name(match.group(1))

    return None


def _extract_content(query: str) -> str | None:
    for pattern in CONTENT_PATTERNS:
        match = pattern.search(query)
        if match:
            extracted = match.group(1).strip(" \"'.")
            return extracted or None

    separators = (" pour ", " de ", " : ")
    query_lower = query.lower()

    for sep in separators:
        index = query_lower.find(sep)
        if index != -1:
            content = query[index + len(sep) :].strip(" \"'.")
            return content or None

    fallback = re.sub(r"^(ajoute(?:-moi)?|ajouter|modifie|modifier|edite|édite|éditer|editer|crée|cree|créer|creer)\s+", "", query, flags=re.IGNORECASE)
    fallback = fallback.strip(" \"'.")
    if fallback == query.strip(" \"'."):
        return None
    return fallback or None


def _find_local_candidates(target_file: str, limit: int = 3) -> list[EditCandidate]:
    vault_root = Path(VAULT_ROOT)
    if not vault_root.exists():
        return []

    normalized_target = target_file.strip()
    direct_path = vault_root / normalized_target
    if direct_path.exists() and direct_path.is_file():
        return [
            {
                "path": str(direct_path),
                "score": 1.0,
                "reason": "fichier trouvé exactement dans le vault",
            }
        ]

    basename_target = Path(normalized_target).name.lower()
    candidates: list[EditCandidate] = []
    for path in vault_root.rglob("*.md"):
        if path.name.lower() == basename_target:
            candidates.append(
                {
                    "path": str(path),
                    "score": 0.85,
                    "reason": "correspondance de nom dans le vault",
                }
            )
            if len(candidates) >= limit:
                break

    return candidates


def _compute_confidence(action: str, target_file: str | None, content: str | None) -> float:
    confidence = 0.2
    if action != "unknown":
        confidence += 0.3
    if target_file:
        confidence += 0.3
    if content:
        confidence += 0.2
    return min(confidence, 1.0)


def read_note_text(path: str) -> str:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return ""

    try:
        return file_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def parse_edit_request(query: str) -> EditRequest:
    """
    Parse une requête d'édition naturelle en JSON structuré.
    
    Exemples :
    - "Ajoute-moi dans mon fichier TODO.md une tâche pour faire les courses"
    - "Crée une note 'Projet X' avec une checklist"
    - "Modifie la note 'Réunion' pour ajouter le point sur le budget"
    
    Returns:
        dict avec keys: action, target_file, content, metadata
    """
    action = _detect_action(query)
    target_file = _extract_target_file(query)
    content = _extract_content(query)

    confidence = _compute_confidence(action=action, target_file=target_file, content=content)

    return {
        "action": action,
        "target_file": target_file,
        "content": content,
        "metadata": {
            "raw_query": query,
            "confidence": confidence,
            "stage": "skeleton",
            "todo": "Brancher RAG+MCP pour la résolution cible",
        },
    }




def resolve_target_file(intent: EditRequest) -> list[EditCandidate]:
    """
    Résout le chemin du fichier cible à partir de la requête.
    """
    target = intent.get("target_file")
    if not target:
        return []

    local_candidates = _find_local_candidates(target_file=target)
    if local_candidates:
        return local_candidates

    return [
        {
            "path": target,
            "score": 0.5,
            "reason": "cible détectée, fichier non résolu localement",
        }
    ]



def build_edit_preview(note_text: str, intent: EditRequest) -> EditPreview:
    """
    Construit l'instruction d'édition à partir du texte de la note et de l'intention.
    """
    action = intent.get("action", "unknown")
    target_file = intent.get("target_file") or "<cible-inconnue>.md"
    payload = intent.get("content") or "<contenu-non-détecté>"

    mode_map = {
        "add": "append",
        "edit": "replace_segment",
        "create": "create_file",
        "unknown": "noop",
    }
    mode = mode_map.get(action, "noop")

    before = note_text.strip()[:200] if note_text.strip() else ""
    if mode == "append":
        after = f"{before}\n{payload}" if before else payload
    elif mode == "create_file":
        after = payload
    elif mode == "replace_segment":
        after = payload
    else:
        after = before or "<aucune modification calculée>"

    if not before:
        before = "<note vide/non chargée>"

    return {
        "mode": mode,
        "target_file": target_file,
        "before": before,
        "after": after,
        "instruction": payload,
    }



def apply_edit(note_text: str, instruction: str) -> str:
    """
    Applique l'instruction d'édition au texte de la note.
    """
    raise NotImplementedError("TODO V1-alpha: implémenter apply_edit")


