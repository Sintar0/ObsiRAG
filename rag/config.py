import os

from dotenv import load_dotenv

load_dotenv()

DB_PATH = "./chroma_db"
COLLECTION_NAME = "obsidian-vault"
EMBEDDING_MODEL = "nomic-embed-text"
GENERATION_MODEL = "qwen3.5:9b"

# RAG tuning
MAX_DOCS = 15
MAX_DOC_CHARS = 1500
MAX_CONTEXT_CHARS = 15000
KEYWORD_WEIGHT = 60

# Obsidian direct verification
VAULT_ROOT = os.path.abspath(
    os.path.expanduser(os.getenv("VAULT_PATH", "~/Obsidian"))
)
OBSIDIAN_HOST = os.getenv("OBSIDIAN_HOST", "127.0.0.1")
OBSIDIAN_PORT = int(os.getenv("OBSIDIAN_PORT", "27124"))
OBSIDIAN_API_KEY = os.getenv("OBSIDIAN_API_KEY", "")
OBSIDIAN_VERIFY_TOP_FILES = 3
OBSIDIAN_VERIFY_SNIPPET_CHARS = 1200
