import pytest
from app.privacy import (
    detect_sensitive_spans,
    pii_density,
    new_session_key,
    encrypt_span,
    decrypt_span
)

def test_detect_sensitive_spans():
    text = "Rahul Sharma works at example@bank.com. ID EMP-12345, Account 123456789."
    spans = detect_sensitive_spans(text)
    types = [s.type for s in spans]
    
    assert "PERSON" in types
    assert "EMAIL" in types
    assert "EMPLOYEE_ID" in types
    assert "ACCOUNT_NO" in types

def test_span_overlap_regex_wins():
    text = "Contact Rahul Sharma."
    spans = detect_sensitive_spans(text)
    assert len(spans) == 1
    assert spans[0].type == "PERSON"
    assert spans[0].value == "Rahul Sharma"

def test_pii_density():
    text = "Account 123456789"
    spans = detect_sensitive_spans(text)
    # length 17, account is 9. density = 9/17 = 0.529
    density = pii_density(text, spans)
    assert density > 0.5

def test_fernet_roundtrip():
    key = new_session_key()
    original = "Rahul Sharma"
    encrypted = encrypt_span(original, key)
    assert encrypted != original
    decrypted = decrypt_span(encrypted, key)
    assert decrypted == original
