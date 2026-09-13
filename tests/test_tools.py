import pytest
from app.tools import ResearchTools
from app.rag import ChromaRetriever, DocumentChunk

def test_public_research_safe_missing_key(monkeypatch):
    from app.config import config
    from types import SimpleNamespace
    mock_config = SimpleNamespace(**config.__dict__)
    mock_config.tavily_api_key = ""
    monkeypatch.setattr('app.tools.config', mock_config)
    
    retriever = ChromaRetriever(collection_name="test_tools")
    tools = ResearchTools(retriever)
    
    # Safe query, but no key
    res = tools.public_research("What are passkeys?")
    assert "error" in res
    assert "not configured" in res["error"]

def test_internal_knowledge_search():
    retriever = ChromaRetriever(collection_name="test_tools_internal")
    
    chunks = [
        DocumentChunk(id="test_t1", document_name="doc.md", section="Auth", content="MFA is required.")
    ]
    retriever.ingest(chunks)
    
    tools = ResearchTools(retriever)
    res = tools.internal_knowledge_search("MFA")
    
    assert "results" in res
    assert len(res["results"]) > 0
    assert "MFA" in res["results"][0]["content"]
