from __future__ import annotations
import re

DEFLECTION_MESSAGE = (
    "Sorry, I’m not able to advise on medical conditions, symptoms, or test eligibility. "
    "Please check with a qualified doctor or healthcare professional for that."
)

_MEDICAL_CONDITION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(cancer|tumou?r|malignant|chemotherapy|radiation|"
        r"diabetes|diabetic|hypertension|high\s+blood\s+pressure|"
        r"heart\s+attack|stroke|kidney\s+failure|liver\s+disease|"
        r"hiv|aids|pregnant|pregnancy|seizure|epilepsy|asthma|copd|"
        r"lung\s+disease|infection|fever|covid|flu|thyroid|anemia|anaemia|"
        r"ulcer|fracture|injury)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(operation|surgery|operated|surgical|procedure|post[\s-]?op|"
        r"after\s+(my\s+)?(surgery|operation|procedure)|recovery\s+from\s+(surgery|operation))\b",
        re.IGNORECASE,
    ),
]

_CLINICAL_ADVICE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(can\s+i|could\s+i|should\s+i|is\s+it\s+safe|am\s+i\s+allowed|"
        r"do\s+i\s+need|do\s+i\s+have\s+to|is\s+this\s+serious|"
        r"how\s+urgent|when\s+should\s+i|without\s+(a\s+)?doctor|"
        r"without\s+(a\s+)?prescription|diagnose|diagnosis|medical\s+advice|"
        r"medical\s+guidance|symptom|symptoms)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(eligible|safe|allowed|advised|urgent|wait|delay|can\s+wait|"
        r"should\s+wait)\b",
        re.IGNORECASE,
    ),
]

_BOOKING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(book|booking|appointment|schedule|slot|centre|center|price|cost)\b", re.IGNORECASE),
    re.compile(r"\b(test|cbc|blood\s+test|scan|lab\s+test|profile)\b", re.IGNORECASE),
]


def check_medical_guardrail(text: str | None) -> str | None:
    """
    Return a deflection message if text asks for clinical advice, urgency guidance,
    or medical eligibility. Booking and pricing requests remain allowed unless they
    are paired with medical questions.
    """
    if not text or not text.strip():
        return None

    normalized = " ".join(text.split())
    lower = normalized.lower()

    has_condition = any(pattern.search(lower) for pattern in _MEDICAL_CONDITION_PATTERNS)
    has_clinical_advice = any(pattern.search(lower) for pattern in _CLINICAL_ADVICE_PATTERNS)
    has_booking_intent = any(pattern.search(lower) for pattern in _BOOKING_PATTERNS)

    if has_condition and (has_clinical_advice or has_booking_intent):
        return DEFLECTION_MESSAGE

    if re.search(
        r"\b(after\s+(my\s+)?(surgery|operation|procedure)|post[\s-]?op|"
        r"recovery\s+from\s+(surgery|operation)|can\s+i\s+(take|get|do)|"
        r"is\s+it\s+safe\s+to\s+(take|get|do)|should\s+i\s+(take|get|do)|"
        r"without\s+(a\s+)?doctor)\b",
        lower,
    ) and re.search(r"\b(test|blood|cbc|scan|appointment|book)\b", lower):
        return DEFLECTION_MESSAGE

    if has_clinical_advice and re.search(r"\b(test|blood|cbc|scan|appointment|book)\b", lower):
        return DEFLECTION_MESSAGE

    return None