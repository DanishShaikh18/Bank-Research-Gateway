"""Ingestion entrypoint script for Bank Research Gateway RAG corpus.

Inspects documents for PII/sensitive data (ingestion DLP), chunks them using
structure-aware markdown parsing, embeds with Gemini Embedding 2 (or mock), and upserts into Qdrant.
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.rag import QdrantRetriever, structure_aware_chunk, inspect_document_for_ingestion

def main():
    print("Bank Research Gateway RAG Ingestion Pipeline")
    docs_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'internal_docs')
    
    if not os.path.exists(docs_dir):
        print(f"Error: Directory {docs_dir} not found.")
        return
        
    retriever = QdrantRetriever()
    total_chunks = 0
    
    for filename in os.listdir(docs_dir):
        if not filename.endswith('.md'):
            continue
            
        filepath = os.path.join(docs_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        print(f"Processing {filename}...")
        
        # 1. Ingestion DLP
        if not inspect_document_for_ingestion(content):
            print(f"  -> REJECTED: Sensitive data found in {filename}. Quarantined.")
            continue
            
        # 2. Structure-aware chunking
        chunks = structure_aware_chunk(content, filename)
        print(f"  -> Generated {len(chunks)} chunks.")
        
        # 3. Upsert to Qdrant
        retriever.ingest(chunks)
        total_chunks += len(chunks)
        
    print(f"Ingestion complete. {total_chunks} total chunks indexed.")

if __name__ == "__main__":
    main()
