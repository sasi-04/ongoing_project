"""Basic de-identification of free text. NOT a substitute for a formal PHI/PII review."""
import re

_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    (re.compile(r"\+?\d[\d\s().-]{7,}\d"), "[PHONE]"),
    (re.compile(r"\b(Mr|Mrs|Ms|Dr|Miss)\.?\s+[A-Z][a-z]+"), "[NAME]"),
    (re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"), "[DATE]"),
]


def scrub(text: str) -> str:
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text
