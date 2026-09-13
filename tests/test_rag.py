import pytest
from app.rag import structure_aware_chunk, generate_embeddings, ChromaRetriever, DocumentChunk

def test_structure_aware_chunk():
    md = """# Header 1\nThis is a paragraph.\n## Header 2\nThis is another paragraph that is long enough to be its own thing.\n"""
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
