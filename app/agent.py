import uuid
import time
import logging
from typing import Dict, Any, Optional, List

from app.config import config
from app.privacy import TokenVault, sanitize_input, inspect_response_and_detokenize
from app.rag import ChromaRetriever
from app.tools import ResearchTools

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """
You are the Bank Research Gateway Assistant.
Your purpose is to answer employee questions regarding internal bank policies,
standards, and public external market research.

Rules:
1. You are NOT authorized to approve loans, modify accounts, execute trades, or make banking decisions.
2. Rely strictly on the tools provided: 'public_research' for external data, and 'internal_knowledge_search' for internal bank policies.
3. If a tool fails, inform the user you cannot answer that part. Do not hallucinate policies or market trends.
4. Always cite your sources when using tool data.
"""

class MockAgentResponse:
    def __init__(self, text: str):
        self.text = text

class MockAgent:
    """Offline mock agent for synthetic testing when API key is missing."""
    def __init__(self, tools, system_instruction):
        self.tools = tools
        self.system_instruction = system_instruction
        
    def generate_response(self, prompt: str) -> MockAgentResponse:
        # Simple rule-based mock for testing 4 paths
        prompt_lower = prompt.lower()
        if "passkeys" in prompt_lower or "trend" in prompt_lower or "web" in prompt_lower:
            # Simulate public research
            res = self.tools[0](prompt)
            return MockAgentResponse(f"Public Research Data for '{prompt}': {res}. I found this online.")
        elif "policy" in prompt_lower or "mfa" in prompt_lower or "internal" in prompt_lower:
            # Simulate internal search
            res = self.tools[1](prompt)
            return MockAgentResponse(f"Internal Policy Data for '{prompt}': {res}. According to our policy.")
        elif "both" in prompt_lower:
            r1 = self.tools[0](prompt)
            r2 = self.tools[1](prompt)
            return MockAgentResponse(f"Combined Data for '{prompt}': {r1} and {r2}.")
        else:
            return MockAgentResponse("I am a direct answer to your general question.")

class BankResearchGateway:
    def __init__(self, use_mock: bool = False):
        self.vault = TokenVault()
        self.retriever = ChromaRetriever()
        self.tools = ResearchTools(self.vault, self.retriever)
        
        # Setup ADK Agent
        self.use_mock = use_mock or not config.google_api_key
        if self.use_mock:
            self.agent = MockAgent(
                tools=self.tools.get_adk_tools(),
                system_instruction=SYSTEM_INSTRUCTION
            )
        else:
            # Setup real ADK Agent
            try:
                from google.adk import Agent
                from google import genai
                
                # Setup genai client
                client = genai.Client(api_key=config.google_api_key)
                
                # Initialize Agent
                self.agent = Agent(
                    model=config.gemini_model,
                    client=client,
                    tools=self.tools.get_adk_tools(),
                    system_instruction=SYSTEM_INSTRUCTION
                )
            except Exception as e:
                logger.error(f"Failed to initialize real ADK Agent: {e}")
                self.agent = MockAgent(tools=self.tools.get_adk_tools(), system_instruction=SYSTEM_INSTRUCTION)

    def _log_observability(self, request_id: str, prompt: str, latency: float, dlp_detected: List[str], blocked: bool, status: str):
        """Zero-PII observability logging."""
        log_entry = {
            "request_id": request_id,
            "latency_ms": int(latency * 1000),
            "dlp_detected": dlp_detected,
            "blocked": blocked,
            "status": status
        }
        logger.info(f"Gateway Audit: {log_entry}")

    def process_request(self, employee_prompt: str) -> str:
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # 1. Input DLP
        from app.privacy import detect_sensitive_spans
        spans = detect_sensitive_spans(employee_prompt)
        dlp_categories = [span.type for span in spans]
        
        sanitized_prompt = sanitize_input(employee_prompt, self.vault)
        
        # 2. Agent Execution
        try:
            if hasattr(self.agent, "generate_response"):
                # Mock or simple interface
                response_obj = self.agent.generate_response(sanitized_prompt)
                raw_response = response_obj.text
            else:
                # Real ADK execution (typically through a Runner or direct call)
                from google.adk import Runner
                runner = Runner(agent=self.agent)
                # ADK Runner typically returns a response string or object
                result = runner.run(sanitized_prompt)
                raw_response = str(result)
                
            status = "success"
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            raw_response = "I encountered an error processing your request."
            status = "error"
            
        # 3. Response DLP & Detokenization
        final_response = inspect_response_and_detokenize(raw_response, self.vault)
        
        # 4. Log Observability
        self._log_observability(
            request_id=request_id,
            prompt=sanitized_prompt, # Log sanitized prompt, NEVER raw
            latency=time.time() - start_time,
            dlp_detected=dlp_categories,
            blocked=False,
            status=status
        )
        
        return final_response

def demo():
    gateway = BankResearchGateway(use_mock=False)
    
    print("\n--- Direct Path ---")
    print(gateway.process_request("What is a database?"))
    
    print("\n--- Internal RAG Path ---")
    print(gateway.process_request("What is our MFA policy? My ID is EMP-12345."))
    
    print("\n--- Public Research Path ---")
    print(gateway.process_request("Research web passkeys for Rahul Sharma account 402918239."))

if __name__ == "__main__":
    demo()
