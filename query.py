from rag.answering import generate_answer
from rag.editing import (
    build_edit_preview,
    parse_edit_request,
    read_note_text,
    resolve_target_file,
)
from rag.retrieval import search_vault
from rag.styles import Colors


def _handle_edit_mode(user_query: str) -> None:
    edit_query = user_query.split("edit:", 1)[1].strip()
    if not edit_query:
        print(f"{Colors.WARNING}⚠️ Requête d'édition vide.{Colors.ENDC}")
        return

    intent = parse_edit_request(edit_query)
    candidates = resolve_target_file(intent)

    selected_candidate = candidates[0] if candidates else None
    if selected_candidate:
        intent["target_file"] = selected_candidate["path"]
    note_text = read_note_text(selected_candidate["path"]) if selected_candidate else ""

    preview = build_edit_preview(note_text=note_text, intent=intent)

    print(f"{Colors.HEADER}\n🛠️  MODE ÉDITION (preview-only){Colors.ENDC}")
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
    print(f"{Colors.WARNING}ℹ️ Aucun write effectué (V1-alpha preview).{Colors.ENDC}")


def main() -> None:
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

            if user_query.lower().startswith("edit:"):
                _handle_edit_mode(user_query)
                continue

            results = search_vault(user_query)
            generate_answer(user_query, results)

        except KeyboardInterrupt:
            print("\n👋 Au revoir !")
            break


if __name__ == "__main__":
    main()
