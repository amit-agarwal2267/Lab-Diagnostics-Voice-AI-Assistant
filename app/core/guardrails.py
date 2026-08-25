from __future__ import annotations
import re

DEFLECTION_MESSAGE = (
    "Sorry, I am an AI assistant and cannot advise on medical conditions "
    "or eligibility for tests. Please consult your doctor for this."
)

_SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(cancer|tumou?r|malignant|chemotherapy|radiation|"
        r"diabetes|diabetic|hypertension|heart\s+attack|stroke|"
        r"kidney\s+failure|liver\s+disease|hiv|aids|pregnant|"
        r"pregnancy|seizure|epilepsy|asthma|copd|lung\s+disease)\b"
        r".{0,80}\b(test|cbc|blood|scan|book|appointment|can\s+i|should\s+i)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(test|cbc|blood|scan|book|appointment|can\s+i|should\s+i)\b"
        r".{0,80}\b(cancer|tumou?r|malignant|chemotherapy|radiation|"
        r"diabetes|diabetic|hypertension|heart\s+attack|stroke|"
        r"kidney\s+failure|liver\s+disease|hiv|aids|pregnant|"
        r"pregnancy|seizure|epilepsy|asthma|copd|lung\s+disease)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    # Recent surgery / operation / procedure timing
    re.compile(
        r"\b(operation|surgery|operated|surgical|procedure|operated\s+on|"
        r"post[\s-]?op|after\s+(my\s+)?(surgery|operation|procedure))\b"
        r".{0,60}\b(test|book|appointment|tomorrow|today|soon|can\s+i)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(test|book|appointment|tomorrow|today|soon|can\s+i)\b"
        r".{0,60}\b(operation|surgery|operated|surgical|procedure|"
        r"post[\s-]?op)\b",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\b(can\s+i\s+take|is\s+it\s+safe|should\s+i\s+(take|do|get)|"
        r"am\s+i\s+allowed|do\s+i\s+need\s+a\s+doctor|"
        r"without\s+(a\s+)?(doctor|prescription)|"
        r"medical\s+advice|diagnose|diagnosis)\b",
        re.IGNORECASE,
    ),
]

def check_medical_guardrail(text: str | None) -> str | None:
    """Return a deflection message if *text* asks for clinical advice, else None.

    Parameters
    ----------
    text:
        The caller's latest utterance (may be None or empty).

    Returns
    -------
    str | None
        Fixed deflection string when the turn must be blocked, otherwise None.
    """
    if not text or not text.strip():
        return None

    normalized = " ".join(text.split())

    for pattern in _SENSITIVE_PATTERNS:
        if pattern.search(normalized):
            return DEFLECTION_MESSAGE

    return None