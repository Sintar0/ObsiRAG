from rag.answering import generate_answer
from rag.retrieval import search_vault
from rag.styles import Colors


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

            results = search_vault(user_query)
            generate_answer(user_query, results)

        except KeyboardInterrupt:
            print("\n👋 Au revoir !")
            break


if __name__ == "__main__":
    main()
