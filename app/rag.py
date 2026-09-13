from dataclasses import dataclass
from typing import List, Dict
import chromadb
from app.config import config
from app.privacy import detect_sensitive_spans

# In a real setup, we would use a real tokenizer (like tiktoken for openAI or equivalent for Gemini).
# We approximate token count as len(text) / 4 for simplicity.
def approx_token_count(text: str) -> int:
    return len(text) // 4

@dataclass
class DocumentChunk:
    id: str
    document_name: str
    section: str
    content: str
    metadata: Dict = None

def inspect_document_for_ingestion(content: str) -> bool:
    """Returns True if document is safe to ingest, False if sensitive data is found."""
    spans = detect_sensitive_spans(content)
    unsafe_types = {"PERSON", "ACCOUNT_NO", "APPLICATION_ID", "PHONE"}
    for span in spans:
        if span.type in unsafe_types:
            return False
    return True

def structure_aware_chunk(markdown_text: str, document_name: str, max_tokens: int = 600) -> List[DocumentChunk]:
    """Splits markdown by headings, preserving section context."""
    chunks = []
    lines = markdown_text.split('\n')
    current_section = "General"
    current_content = []
    current_tokens = 0
    chunk_idx = 0
    
    def add_chunk():
        nonlocal chunk_idx, current_content, current_tokens
        if current_content:
            text = '\n'.join(current_content).strip()
            if text:
                chunks.append(DocumentChunk(
                    id=f"{document_name}_{chunk_idx}",
                    document_name=document_name,
                    section=current_section,
                    content=text,
                    metadata={}
                ))
                chunk_idx += 1
            current_content = []
            current_tokens = 0

    for line in lines:
        if line.startswith('#'):
            # New heading, usually forces a new chunk if we already have content
            add_chunk()
            current_section = line.strip('# ').strip()
            current_content.append(line)
            current_tokens += approx_token_count(line)
        else:
            line_tokens = approx_token_count(line)
            if current_tokens + line_tokens > max_tokens and current_tokens > 0:
                add_chunk()
            current_content.append(line)
            current_tokens += line_tokens
            
    add_chunk()
    return chunks

_embedding_model_instance = None

def get_embedding_model():
    global _embedding_model_instance
    if _embedding_model_instance is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model_instance = SentenceTransformer(config.embedding_model)
    return _embedding_model_instance

def generate_embeddings(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()

class ChromaRetriever:
    def __init__(self, collection_name: str = "internal_knowledge"):
        self.collection_name = collection_name
        self.client = chromadb.PersistentClient(path=config.chroma_persist_directory)
        self._ensure_collection()
        
    def _ensure_collection(self):
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    def ingest(self, chunks: List[DocumentChunk]):
        if not chunks: return
        
        texts = [c.content for c in chunks]
        embeddings = generate_embeddings(texts)
        ids = [str(hash(c.id)) for c in chunks] # Chroma uses string IDs
        metadatas = [{"document_name": c.document_name, "section": c.section} for c in chunks]
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )

    def search_hybrid(self, query: str, top_k: int = 5) -> List[DocumentChunk]:
        """Hybrid search combining semantic vector search and simple keyword filtering/scoring."""
        query_vector = generate_embeddings([query])[0]
        
        # 1. Dense Search
        dense_results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k * 2
        )
        
        if not dense_results["ids"] or not dense_results["ids"][0]:
            return []
            
        # 2. Simple Reciprocal Rank Fusion / Keyword Boost
        query_words = set(query.lower().split())
        scored_chunks = []
        
        ids = dense_results["ids"][0]
        documents = dense_results["documents"][0]
        metadatas = dense_results["metadatas"][0]
        
        for i in range(len(ids)):
            dense_score = 1.0 / (i + 1) # hybrid weighted score dense component
            
            content_lower = documents[i].lower()
            keyword_matches = sum(1 for w in query_words if w in content_lower and len(w) > 3)
            lexical_score = keyword_matches * 0.5 
            
            final_score = dense_score + lexical_score
            scored_chunks.append((final_score, i))
            
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_indices = [item[1] for item in scored_chunks[:top_k]]
        
        return [DocumentChunk(
            id=ids[i],
            document_name=metadatas[i]["document_name"],
            section=metadatas[i]["section"],
            content=documents[i]
        ) for i in top_indices]

