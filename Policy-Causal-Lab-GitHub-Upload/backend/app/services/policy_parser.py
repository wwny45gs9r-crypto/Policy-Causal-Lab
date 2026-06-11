from pathlib import Path
from .document_parser import extract_text


def parse_policy(path: str) -> dict:
    file = Path(path)
    text = extract_text(path)
    return {"policy_text": text, "summary": text[:2000], "variable_hints": [], "filename": file.name}
