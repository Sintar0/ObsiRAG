import re
from pathlib import Path
from typing import Any, TypedDict

import ollama

from rag.config import GENERATION_MODEL, VAULT_ROOT


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
    base = note_text.rstrip("\n")
    if not base:
        return instruction
    return f"{base}\n{instruction}"


def _extract_meaningful_lines(answer_text: str, max_items: int = 16) -> list[str]:
    lines = [line.strip() for line in answer_text.splitlines() if line.strip()]
    items: list[str] = []

    for line in lines:
        if line.startswith("SOURCE:") or line.startswith("--- Fin"):
            continue

        cleaned = line
        cleaned = re.sub(r"^#{1,6}\s*", "", cleaned)
        cleaned = re.sub(r"^[-*•]\s+", "", cleaned)
        cleaned = re.sub(r"^\d+[\.)]\s+", "", cleaned)
        cleaned = cleaned.strip(" -:\t")

        if len(cleaned) < 4:
            continue

        if cleaned.lower().startswith(("d'après", "points clés", "ce sont")):
            continue

        if cleaned not in items:
            items.append(cleaned)
        if len(items) >= max_items:
            break

    return items


def format_answer_as_todo(answer_text: str, max_items: int = 12) -> str:
    items = _extract_meaningful_lines(answer_text=answer_text, max_items=max_items)

    if not items:
        fallback = answer_text.strip()
        if not fallback:
            return "- [ ] TODO"
        short = fallback[:300].replace("\n", " ")
        return f"- [ ] {short}"

    return "\n".join(f"- [ ] {item}" for item in items)


def format_answer_as_summary(answer_text: str, max_items: int = 8) -> str:
    items = _extract_meaningful_lines(answer_text=answer_text, max_items=max_items)
    if not items:
        return answer_text.strip() or "Résumé indisponible."
    bullets = "\n".join(f"- {item}" for item in items)
    return f"## Résumé\n{bullets}"


def _truncate_words(text: str, max_words: int = 12) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).rstrip(".,;:") + "..."


def _postprocess_checklist(text: str, max_items: int, compact: bool) -> str:
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    items: list[str] = []

    for line in raw_lines:
        cleaned = re.sub(r"^[-*]\s*(?:\[[ xX]\])?\s*", "", line)
        cleaned = re.sub(r"^\d+[\.)]\s+", "", cleaned)
        cleaned = cleaned.strip(" -\t")
        cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)

        if not cleaned:
            continue

        if compact and ("\\" in cleaned or len(cleaned) > 120):
            continue

        if compact:
            cleaned = _truncate_words(cleaned, max_words=11)

        if cleaned not in items:
            items.append(cleaned)

        if len(items) >= max_items:
            break

    if not items:
        return text.strip()
    return "\n".join(f"- [ ] {item}" for item in items)


def _extract_key_concepts(answer_text: str, max_concepts: int = 8) -> list[str]:
    """Première étape : extraire les concepts clés du texte source."""
    source = answer_text.strip()[:4000]
    
    prompt = (
        "EXTRAIS les concepts clés et idées principales du texte suivant. "
        "Retourne UNIQUEMENT une liste de concepts, un par ligne, sans numérotation. "
        "Chaque concept doit être formulé brièvement (5-10 mots max). "
        f"Limite-toi à {max_concepts} concepts maximum.\n\n"
        f"TEXTE SOURCE:\n{source}\n\n"
        "CONCEPTS CLÉS (un par ligne):"
    )
    
    try:
        response = ollama.chat(
            model=GENERATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.message.content.strip()
        
        # Parser les concepts
        concepts = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            # Retirer numérotation
            line = re.sub(r"^\d+[.\)-]\s*", "", line)
            line = re.sub(r"^[-*•]\s*", "", line)
            if line and len(line) > 3:
                concepts.append(line)
        return concepts[:max_concepts]
    except Exception:
        return []


def _format_concepts(concepts: list[str], format_type: str) -> str:
    """Deuxième étape : formater les concepts selon le type demandé."""
    if not concepts:
        return "- Aucun concept extrait"
    
    concepts_text = "\n".join(f"- {c}" for c in concepts)
    
    prompt = (
        f"Tu dois transformer cette liste de concepts en {format_type.upper()}.\n\n"
        f"CONCEPTS À TRANSFORMER:\n{concepts_text}\n\n"
        f"INSTRUCTIONS POUR {format_type.upper()}:\n"
    )
    
    if "todo" in format_type.lower() or "checklist" in format_type.lower():
        prompt += (
            "Transforme chaque concept en item actionnable et concret. "
            "Utilise le format '- [ ] action à faire'. "
            "Chaque item doit être une tâche réalisable, pas juste un concept."
        )
    elif "résumé" in format_type.lower() or "synthèse" in format_type.lower():
        prompt += (
            "Crée un résumé structuré avec les points essentiels. "
            "Privilégie la clarté et la concision. "
            "Utilise des puces ou une structure adaptée."
        )
    else:
        prompt += (
            "Organise ces concepts de manière claire et utile. "
            "Choisis la structure la plus pertinente."
        )
    
    try:
        response = ollama.chat(
            model=GENERATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return str(response.message.content or "").strip()
    except Exception:
        return "\n".join(f"- {c}" for c in concepts)


def _format_last_answer_with_llm(answer_text: str, edit_query: str) -> str | None:
    """Transforme la réponse via une approche en 2 étapes: extraction puis formatage."""
    source_text = answer_text.strip()
    if not source_text:
        return None

    query_lower = edit_query.lower()
    checklist_markers = ("todo", "to-do", "checklist", "check-list", "tâche", "tache")
    synth_markers = ("synthétique", "synthetique", "bref", "court", "compact")
    wants_checklist = any(marker in query_lower for marker in checklist_markers)
    wants_synth = any(marker in query_lower for marker in synth_markers)
    max_items = 6 if wants_synth else 12

    # Étape 1: Extraire les concepts clés
    concepts = _extract_key_concepts(answer_text, max_concepts=max_items)
    if not concepts:
        return None

    # Étape 2: Formater selon le type demandé
    if wants_checklist:
        return _format_concepts(concepts, "TODO checklist")
    elif wants_synth:
        return _format_concepts(concepts, "résumé synthétique")
    else:
        # Détecter si c'est une liste ou autre chose
        list_markers = ("liste", "points", "enum", "item")
        if any(marker in query_lower for marker in list_markers):
            return _format_concepts(concepts, "liste structurée")
        return _format_concepts(concepts, "format adapté")


def format_last_answer_content(answer_text: str, edit_query: str) -> str:
    llm_content = _format_last_answer_with_llm(answer_text=answer_text, edit_query=edit_query)
    if llm_content:
        return llm_content

    query_lower = edit_query.lower()
    todo_markers = ("todo", "to-do", "checklist", "check-list", "tâche", "tache")
    summary_markers = ("résumé", "resume", "résumer", "resumer", "synthèse", "synthese")
    keep_context_markers = ("contexte", "discussion", "complet", "tel quel")

    if any(marker in query_lower for marker in todo_markers):
        return format_answer_as_todo(answer_text)

    if any(marker in query_lower for marker in summary_markers):
        return format_answer_as_summary(answer_text)

    if any(marker in query_lower for marker in keep_context_markers):
        return answer_text.strip()

    return format_answer_as_summary(answer_text)


def _is_safe_vault_path(target_path: Path) -> bool:
    vault_root = Path(VAULT_ROOT).resolve()
    try:
        resolved_target = target_path.resolve()
    except OSError:
        return False
    return str(resolved_target).startswith(str(vault_root) + str(Path("/"))) or resolved_target == vault_root


def write_edit_to_vault(intent: EditRequest, target_path: str, note_text: str) -> tuple[bool, str]:
    action = intent.get("action", "unknown")
    payload = (intent.get("content") or "").strip()

    if action not in {"create", "add"}:
        return False, "Action non supportée en écriture pour le moment (support: create/add)."

    if not payload:
        return False, "Contenu vide: écriture annulée."

    target = Path(target_path)
    if not target.is_absolute():
        target = (Path(VAULT_ROOT) / target).resolve()

    if not _is_safe_vault_path(target):
        return False, "Chemin cible hors vault: écriture bloquée."

    target.parent.mkdir(parents=True, exist_ok=True)

    if action == "create":
        if target.exists():
            return False, "La note existe déjà: create annulé."
        target.write_text(payload + "\n", encoding="utf-8")
        return True, f"Note créée: {target}"

    updated = apply_edit(note_text=note_text, instruction=payload)
    target.write_text(updated + "\n", encoding="utf-8")
    return True, f"Note mise à jour: {target}"


