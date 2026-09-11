import pytest
from app.rag import structure_aware_chunk, inspect_document_for_ingestion, generate_embeddings, ChromaRetriever, DocumentChunk

def test_inspect_document_for_ingestion():
    # Safe document
    safe_doc = "This is a bank policy regarding MFA and ABAC."
    assert inspect_document_for_ingestion(safe_doc) is True
    
    # Unsafe document (contains a 9-digit account number)
    unsafe_doc = "This policy applies to account 123456789."
    assert inspect_document_for_ingestion(unsafe_doc) is False

def test_structure_aware_chunk():
    md = """# Header 1
This is a paragraph.
## Header 2
This is another paragraph that is long enough to be its own thing.
"""
    chunks = structure_aware_chunk(md, "test.md", max_tokens=10)
    assert len(chunks) > 0
    assert chunks[0].document_name == "test.md"
    assert chunks[0].section == "Header 1"
    
def test_mock_embeddings():
    emb = generate_embeddings(["hello", "world"])
    assert len(emb) == 2
    assert len(emb[0]) in (768, 3072)

def test_chroma_retriever():
    retriever = ChromaRetriever(collection_name="test_collection")
    chunks = [
        DocumentChunk(id="test_1", document_name="doc.md", section="Auth", content="MFA is required for access."),
        DocumentChunk(id="test_2", document_name="doc.md", section="Cloud", content="Use AWS for cloud storage.")
    ]
    retriever.ingest(chunks)
    
    results = retriever.search_hybrid("MFA access", top_k=1)
    assert len(results) == 1
    assert "MFA" in results[0].content
