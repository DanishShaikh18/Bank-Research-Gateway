"""Agent Tools: public_research (Tavily) and internal_knowledge_search (Qdrant hybrid)."""
import logging
from typing import Dict, Any, List

from app.config import config
from app.privacy import TokenVault, inspect_outbound_payload, detect_sensitive_spans
from app.rag import ChromaRetriever

logger = logging.getLogger(__name__)

class ResearchTools:
    def __init__(self, vault: TokenVault, retriever: ChromaRetriever):
        self.vault = vault
        self.retriever = retriever

    def public_research(self, query: str) -> Dict[str, Any]:
        """
        Executes a public web search for current external information.
        
        Args:
            query: The search query to run.
            
        Returns:
            A dictionary containing retrieved sources or an error message.
        """
        # 1. Outbound DLP Inspection
        safe, msg = inspect_outbound_payload(query, self.vault)
        if not safe:
            logger.warning(f"public_research blocked: {msg}")
            return {"error": "Request blocked by outbound DLP.", "details": msg}
            
        # 2. Execute Tavily Search
        if not config.tavily_api_key:
            # Fallback for testing when key is not present
            return {
                "error": "Tavily API key not configured.",
                "sources": []
            }
            
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=config.tavily_api_key)
            
            # Safe defaults as per PLAN.MD
            response = client.search(
                query=query,
                search_depth="basic",
                max_results=5,
                include_answer=False,
                include_raw_content=False
            )
            
            # 3. Normalize Response
            sources = []
            for res in response.get("results", []):
                content = res.get("content", "")
                
                # External response inspection (inbound DLP)
                # If unexpected sensitive data is returned by Tavily, redact it
                spans = detect_sensitive_spans(content)
                for span in reversed(spans):
                    content = content[:span.start] + "[REDACTED]" + content[span.end:]
                    
                sources.append({
                    "title": res.get("title", ""),
                    "url": res.get("url", ""),
                    "content": content,
                    "score": res.get("score", 0.0)
                })
                
            return {"sources": sources}
            
        except Exception as e:
            logger.error(f"public_research failed: {str(e)}")
            return {"error": "External search service unavailable.", "details": str(e)}

    def internal_knowledge_search(self, query: str) -> Dict[str, Any]:
        """
        Executes a hybrid search over internal bank policies and guidelines.
        
        Args:
            query: The search query to run.
            
        Returns:
            A dictionary containing retrieved internal chunks or an error message.
        """
        try:
            chunks = self.retriever.search_hybrid(query, top_k=3)
            
            normalized_chunks = []
            for chunk in chunks:
                normalized_chunks.append({
                    "document": chunk.document_name,
                    "section": chunk.section,
                    "content": chunk.content
                })
                
            return {"results": normalized_chunks}
            
        except Exception as e:
            logger.error(f"internal_knowledge_search failed: {str(e)}")
            return {"error": "Internal knowledge retrieval failed.", "details": str(e)}

    def get_adk_tools(self) -> List[callable]:
        """Returns the list of tool functions to be registered with the agent."""
        return [self.public_research, self.internal_knowledge_search]
