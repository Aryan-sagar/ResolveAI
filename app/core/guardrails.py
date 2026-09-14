import re

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules|context)",
    r"disregard\s+(all\s+)?(previous|prior|your)\s*(instructions|rules)?",
    r"reveal\s+(your|the)\s+(system\s+)?prompt",
    r"you\s+are\s+now\s+an?",
    r"(jailbreak|developer\s+mode|dan\s+mode)",
    r"(show|give|print|list)\s+(me\s+)?(all\s+)?(the\s+)?customer\s+(data|records|details)",
]

PII_PATTERNS = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "phone": r"\+?\d[\d\s\-]{8,}\d",
    "card":  r"\b(?:\d[ -]?){13,16}\b",
}

def check_input(text: str) -> dict:
    for p in INJECTION_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return {"blocked": True, "reason": f"prompt_injection:{p}"}
    return {"blocked": False, "reason": None}

def detect_pii(text: str) -> list[str]:
    return [k for k, p in PII_PATTERNS.items() if re.search(p, text)]