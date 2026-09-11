import pytest
from app.privacy import TokenVault, sanitize_input, inspect_outbound_payload, inspect_response_and_detokenize

def test_token_vault():
    vault = TokenVault()
    t1 = vault.tokenize("PERSON", "Rahul Sharma")
    assert t1 == "<PERSON_001>"
    
    t2 = vault.tokenize("PERSON", "Rahul Sharma")
    assert t2 == "<PERSON_001>" # Collision free/consistent
    
    t3 = vault.tokenize("PERSON", "Priya Patel")
    assert t3 == "<PERSON_002>"

    detok = vault.detokenize("Hello <PERSON_001> and <PERSON_002>")
    assert detok == "Hello Rahul Sharma and Priya Patel"

def test_sanitize_input():
    vault = TokenVault()
    text = "My ID is EMP-12345. Contact Rahul Sharma at rahul@example.com about 402918239."
    sanitized = sanitize_input(text, vault)
    
    assert "EMP-12345" not in sanitized
    assert "[REDACTED]" in sanitized
    assert "Rahul Sharma" not in sanitized
    assert "<PERSON_001>" in sanitized
    assert "rahul@example.com" not in sanitized
    assert "<EMAIL_001>" in sanitized
    assert "402918239" not in sanitized
    assert "<ACCOUNT_NO_001>" in sanitized

def test_outbound_payload_inspection():
    vault = TokenVault()
    vault.tokenize("PERSON", "Rahul Sharma")
    
    safe, msg = inspect_outbound_payload("Research <PERSON_001> trends.", vault)
    assert safe is True
    
    safe, msg = inspect_outbound_payload("Research Rahul Sharma trends.", vault)
    assert safe is False
    assert "Raw token value found" in msg

    # Unseen PII leaking
    safe, msg = inspect_outbound_payload("Research Priya Patel trends.", vault)
    assert safe is False
    assert "Sensitive data" in msg

def test_response_detokenize():
    vault = TokenVault()
    vault.tokenize("PERSON", "Rahul Sharma")
    
    agent_output = "I found this for <PERSON_001>. Also note Amit Verma is involved."
    final = inspect_response_and_detokenize(agent_output, vault)
    
    assert "Rahul Sharma" in final
    assert "Amit Verma" not in final
    assert "[REDACTED]" in final
