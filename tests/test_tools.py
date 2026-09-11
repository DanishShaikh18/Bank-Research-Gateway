import pytest
from app.tools import ResearchTools
from app.privacy import TokenVault
from app.rag import ChromaRetriever, DocumentChunk

def test_public_research_outbound_block():
    vault = TokenVault()
    vault.tokenize("PERSON", "Rahul Sharma")
    retriever = ChromaRetriever(collection_name="test_tools")
    tools = ResearchTools(vault, retriever)
    
    # This should be blocked
    res = tools.public_research("Search Rahul Sharma on the web")
    assert "error" in res
    assert "blocked" in res["error"].lower()

def test_public_research_safe_missing_key(monkeypatch):
    from app.config import config
    from types import SimpleNamespace
    mock_config = SimpleNamespace(**config.__dict__)
    mock_config.tavily_api_key = ""
    monkeypatch.setattr('app.tools.config', mock_config)
    vault = TokenVault()
    retriever = ChromaRetriever(collection_name="test_tools")
    tools = ResearchTools(vault, retriever)
    
    # Safe query, but no key
    res = tools.public_research("What are passkeys?")
    assert "error" in res
    assert "not configured" in res["error"]

def test_internal_knowledge_search():
    vault = TokenVault()
    retriever = ChromaRetriever(collection_name="test_tools_internal")
    
    chunks = [
        DocumentChunk(id="test_t1", document_name="doc.md", section="Auth", content="MFA is required.")
    ]
    retriever.ingest(chunks)
    
    tools = ResearchTools(vault, retriever)
    res = tools.internal_knowledge_search("MFA")
    
    assert "results" in res
    assert len(res["results"]) > 0
    assert "MFA" in res["results"][0]["content"]
