import re
from dataclasses import dataclass
from typing import List
import spacy
from cryptography.fernet import Fernet

@dataclass
class Span:
    type: str
    start: int
    end: int
    value: str

# Load the spaCy model once at module level
_nlp = spacy.load("en_core_web_sm")

def new_session_key() -> bytes:
    return Fernet.generate_key()

def encrypt_span(value: str, key: bytes) -> str:
    return Fernet(key).encrypt(value.encode()).decode()

def decrypt_span(ciphertext: str, key: bytes) -> str:
    return Fernet(key).decrypt(ciphertext.encode()).decode()

# Simple deterministic detection
# In a real bank, this would be robust regex + NER rules.
PATTERNS = {
    "EMAIL": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    "PHONE": r"\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
    "EMPLOYEE_ID": r"EMP-\d{5}",
    "ACCOUNT_NO": r"\b\d{9}\b",
    "APPLICATION_ID": r"\b\d{6}\b|LN-\d{4}-\d{4}",
    "PAN_NUMBER": r"[A-Z]{5}[0-9]{4}[A-Z]{1}",
    "AADHAAR_NUMBER": r"\b\d{4}[ \-]?\d{4}[ \-]?\d{4}\b"
}

# Policy rules
REDACT_TYPES = {"EMPLOYEE_ID"} # Types that are always redacted
TOKENIZE_TYPES = {"PERSON", "APPLICATION_ID", "ACCOUNT_NO", "EMAIL", "PHONE", "PAN_NUMBER", "AADHAAR_NUMBER"}

def get_person_spans(text: str) -> List[Span]:
    doc = _nlp(text)
    return [Span("PERSON", ent.start_char, ent.end_char, ent.text)
            for ent in doc.ents if ent.label_ == "PERSON"]

def detect_sensitive_spans(text: str) -> List[Span]:
    regex_spans = []
    # Collect all regex matches
    for entity_type, pattern in PATTERNS.items():
        for match in re.finditer(pattern, text):
            regex_spans.append(Span(type=entity_type, start=match.start(), end=match.end(), value=match.group()))
    
    person_spans = get_person_spans(text)
    
    resolved_spans = list(regex_spans)
    
    # Merge person spans, ensuring regex wins on overlap
    for p_span in person_spans:
        overlap = False
        for r_span in regex_spans:
            if not (p_span.end <= r_span.start or p_span.start >= r_span.end):
                overlap = True
                break
        if not overlap:
            resolved_spans.append(p_span)
            
    # Sort by start position
    resolved_spans.sort(key=lambda x: x.start)
    return resolved_spans

def pii_density(text: str, spans: List[Span]) -> float:
    if not text:
        return 0.0
    covered = sum(s.end - s.start for s in spans)
    return covered / len(text)
