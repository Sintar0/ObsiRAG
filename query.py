from rag.answering import generate_answer
from rag.editing import (
    build_edit_preview,
    format_last_answer_content,
    parse_edit_request,
    read_note_text,
    resolve_target_file,
    write_edit_to_vault,
)
from rag.retrieval import search_vault
from rag.styles import Colors


def _handle_edit_mode(user_query: str, forced_content: str | None = None) -> None:
    edit_mode = "preview"
    if user_query.lower().startswith("edit!:"):
        edit_mode = "write"

    split_prefix = "edit!:" if edit_mode == "write" else "edit:"
    edit_query = user_query.split(split_prefix, 1)[1].strip()
    if not edit_query:
        print(f"{Colors.WARNING}⚠️ Requête d'édition vide.{Colors.ENDC}")
        return

    intent = parse_edit_request(edit_query)
    if forced_content and forced_content.strip():
        intent["content"] = forced_content.strip()

    if intent["action"] == "unknown":
        print(f"{Colors.WARNING}⚠️ Intention inconnue: écriture bloquée.{Colors.ENDC}")
        return

    candidates = resolve_target_file(intent)

    if len(candidates) > 1:
        print(f"{Colors.WARNING}⚠️ Cible ambiguë ({len(candidates)} candidats). Choisis un fichier explicitement.{Colors.ENDC}")
        for idx, candidate in enumerate(candidates, start=1):
            print(f"  {idx}. {candidate['path']} ({candidate['reason']})")
        return

    if edit_mode == "write" and not candidates and intent["action"] != "create":
        print(f"{Colors.WARNING}⚠️ Aucune cible résolue: écriture bloquée.{Colors.ENDC}")
        return

    selected_candidate = candidates[0] if candidates else None
    if selected_candidate:
        intent["target_file"] = selected_candidate["path"]
    note_text = read_note_text(selected_candidate["path"]) if selected_candidate else ""

    preview = build_edit_preview(note_text=note_text, intent=intent)

    mode_label = "WRITE" if edit_mode == "write" else "PREVIEW-ONLY"
    print(f"{Colors.HEADER}\n🛠️  MODE ÉDITION ({mode_label}){Colors.ENDC}")
    print(f"- action      : {intent['action']}")
    print(f"- cible       : {preview['target_file']}")
    print(f"- confiance   : {intent['metadata'].get('confidence')}")
    print(f"- candidats   : {len(candidates)}")
    if selected_candidate:
        print(f"- candidat #1 : {selected_candidate['path']} ({selected_candidate['reason']})")
    print(f"- mode        : {preview['mode']}")
    print(f"- instruction : {preview['instruction']}")
    print("- avant       :")
    print(preview["before"])
    print("- après       :")
    print(preview["after"])

    if edit_mode != "write":
        print(f"{Colors.WARNING}ℹ️ Dry-run actif: aucun write effectué (utilise 'edit!:' pour écrire).{Colors.ENDC}")
        return

    target_path = intent.get("target_file") or ""
    if not target_path:
        print(f"{Colors.WARNING}⚠️ Chemin cible introuvable: écriture annulée.{Colors.ENDC}")
        return

    confirm = input(f"{Colors.BOLD}Confirmer l'écriture dans '{target_path}' ? (oui/non): {Colors.ENDC}").strip().lower()
    if confirm not in {"oui", "o", "yes", "y"}:
        print(f"{Colors.WARNING}ℹ️ Écriture annulée par l'utilisateur.{Colors.ENDC}")
        return

    ok, message = write_edit_to_vault(intent=intent, target_path=target_path, note_text=note_text)
    color = Colors.GREEN if ok else Colors.FAIL
    print(f"{color}{'✅' if ok else '❌'} {message}{Colors.ENDC}")


def _handle_editlast_mode(user_query: str, last_answer: str) -> None:
    if not last_answer.strip():
        print(f"{Colors.WARNING}⚠️ Aucune réponse précédente à réutiliser.{Colors.ENDC}")
        return

    write_mode = user_query.lower().startswith("editlast!:")
    split_prefix = "editlast!:" if write_mode else "editlast:"
    edit_query = user_query.split(split_prefix, 1)[1].strip()
    if not edit_query:
        print(
            f"{Colors.WARNING}⚠️ Requête vide. Ex: editlast!: Crée TODO-DS-Stats.md{Colors.ENDC}"
        )
        return

    forced_content = format_last_answer_content(last_answer, edit_query)

    rerouted_prefix = "edit!:" if write_mode else "edit:"
    rerouted_query = f"{rerouted_prefix} {edit_query}"
    _handle_edit_mode(rerouted_query, forced_content=forced_content)


def main() -> None:
    last_answer = ""
    while True:
        try:
            print("\n" + "=" * 50)
            user_query = input(
                f"{Colors.BOLD}❓ Ta question (ou 'exit') : {Colors.ENDC}"
            )

            if user_query.lower() in ["exit", "quit", "q"]:
                break

            if not user_query.strip():
                continue

            if user_query.lower().startswith("editlast:") or user_query.lower().startswith("editlast!:"):
                _handle_editlast_mode(user_query, last_answer)
                continue

            if user_query.lower().startswith("edit:") or user_query.lower().startswith("edit!:"):
                _handle_edit_mode(user_query)
                continue

            results = search_vault(user_query)
            last_answer = generate_answer(user_query, results)

        except KeyboardInterrupt:
            print("\n👋 Au revoir !")
            break


if __name__ == "__main__":
    main()
