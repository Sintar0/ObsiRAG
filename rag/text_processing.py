import re
import unicodedata

STOPWORDS = {
    "cest",
    "quoi",
    "quel",
    "quels",
    "quelle",
    "quelles",
    "comment",
    "pourquoi",
    "donne",
    "moi",
    "definition",
    "definir",
    "le",
    "la",
    "les",
    "un",
    "une",
    "des",
    "du",
    "de",
    "d",
    "l",
    "a",
    "au",
    "aux",
    "est",
    "sont",
    "etre",
    "faire",
    "peux",
    "peut",
    "que",
    "qui",
    "dans",
    "sur",
    "avec",
    "sans",
    "par",
    "en",
    "et",
    "ou",
    "ce",
    "cette",
    "ces",
    "cet",
    "se",
    "son",
    "sa",
    "ses",
    "mais",
    "plus",
    "moins",
    "tres",
    "trop",
}


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.lower()
    return re.sub(r"[^a-z0-9\s-]", " ", text)


def extract_keywords(text: str) -> list[str]:
    normalized = normalize_text(text)
    tokens = re.findall(r"[a-z0-9]+", normalized)
    keywords = [token for token in tokens if token not in STOPWORDS and len(token) > 2]
    return list(dict.fromkeys(keywords))


def keyword_hit_count(text: str, keywords: list[str]) -> int:
    if not keywords:
        return 0
    text_norm = normalize_text(text)
    return sum(1 for keyword in keywords if keyword in text_norm)
