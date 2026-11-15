"""Exact scoring-only extracts from cell 14; no correction service or model calls."""
import re

WORD_RE = re.compile(r"[а-яёәіңғүұқөһ]+", re.IGNORECASE)

def normalize_text(raw: str) -> str:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    raw = raw.replace("-\n", "")     # join wrapped words
    raw = raw.replace("\n", " ")     # newlines -> space
    raw = re.sub(r"[ \t]+", " ", raw)
    return raw.strip()

def tokenize_kazakh(text: str):
    return WORD_RE.findall(text.lower())
