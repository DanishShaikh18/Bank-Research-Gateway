import pytest
from app.agent import BankResearchGateway

def test_direct_path():
    gateway = BankResearchGateway(use_mock=True)
    res = gateway.process_request("What is an API?")
    assert "direct answer" in res

def test_public_research_path():
    gateway = BankResearchGateway(use_mock=True)
    # The term 'web' or 'trend' triggers the public research mock
    res = gateway.process_request("Research web trends for Rahul Sharma.")
    
    # Verify the final response detokenized Rahul Sharma back
    assert "Rahul Sharma" in res
    assert "Public Research Data" in res

def test_internal_rag_path():
    gateway = BankResearchGateway(use_mock=True)
    # The term 'policy' triggers the internal mock
    res = gateway.process_request("What is our MFA policy? Contact Amit Verma.")
    
    assert "Internal Policy Data" in res
    assert "Amit Verma" in res

def test_dlp_redaction_flow():
    gateway = BankResearchGateway(use_mock=True)
    # EMP-12345 should be redacted and never make it back
    res = gateway.process_request("What is an API? My employee id is EMP-12345.")
    
    assert "EMP-12345" not in res
    assert "direct answer" in res
