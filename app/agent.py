import uuid
import time
import logging
from typing import Dict, Any, Optional, List

from app.config import config
from app.privacy import (
    detect_sensitive_spans,
    new_session_key,
    encrypt_span,
    decrypt_span,
    REDACT_TYPES,
    TOKENIZE_TYPES
)
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

def before_model_callback(callback_context, llm_request):
    """
    Run PII detection on user input. 
    Tokenize critical entities, redact non-critical ones, and rewrite the request text.
    """
    state = callback_context.session.state
    if "fernet_key" not in state:
        state["fernet_key"] = new_session_key()
    if "pii_tokens" not in state:
        state["pii_tokens"] = {}
    if "pii_counters" not in state:
        state["pii_counters"] = {}
    if "dlp_detected" not in state:
        state["dlp_detected"] = []

    text = getattr(llm_request, 'prompt', str(llm_request))
    spans = detect_sensitive_spans(text)
    
    if not spans:
        return

    for span in spans:
        if span.type not in state["dlp_detected"]:
            state["dlp_detected"].append(span.type)

    result = text
    for span in reversed(spans):
        if span.type in REDACT_TYPES:
            replacement = "[REDACTED]"
        else:
            counters = state["pii_counters"]
            counters[span.type] = counters.get(span.type, 0) + 1
            token = f"<{span.type}_{counters[span.type]:03d}>"
            
            ciphertext = encrypt_span(span.value, state["fernet_key"])
            state["pii_tokens"][token] = ciphertext
            replacement = token
            
        result = result[:span.start] + replacement + result[span.end:]
        
    if hasattr(llm_request, 'prompt'):
        llm_request.prompt = result
    else:
        return result

def before_tool_callback(tool, args, tool_context):
    """
    Re-scan outbound query string. 
    If raw sensitive pattern found, fail closed.
    """
    if getattr(tool, 'name', str(tool)) == "public_research":
        query = str(args)
        spans = detect_sensitive_spans(query)
        if spans:
            return f"BLOCKED: Sensitive data ({spans[0].type}) found in outbound payload."

def _redact_obj(obj):
    if isinstance(obj, str):
        spans = detect_sensitive_spans(obj)
        res = obj
        for span in reversed(spans):
            res = res[:span.start] + "[REDACTED]" + res[span.end:]
        return res
    elif isinstance(obj, dict):
        return {k: _redact_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_redact_obj(x) for x in obj]
    else:
        return obj

def after_tool_callback(tool, args, tool_context, tool_response):
    """
    Scan tool returned text for unexpected PII and redact it before reaching the model.
    """
    return _redact_obj(tool_response)

def after_model_callback(callback_context, llm_response):
    """
    Scan model output for safety net (redact).
    Then detokenize the <TYPE_NNN> tokens back to raw values using the session key and vault dictionary.
    """
    text = getattr(llm_response, 'text', str(llm_response))
    
    # 1. Safety net
    spans = detect_sensitive_spans(text)
    result = text
    for span in reversed(spans):
        result = result[:span.start] + "[REDACTED]" + result[span.end:]
        
    # 2. Detokenization
    state = callback_context.session.state
    if "pii_tokens" in state and "fernet_key" in state:
        tokens = state["pii_tokens"]
        key = state["fernet_key"]
        
        for token, ciphertext in tokens.items():
            if token in result:
                plaintext = decrypt_span(ciphertext, key)
                result = result.replace(token, plaintext)
                
    if hasattr(llm_response, 'text'):
        llm_response.text = result
    else:
        return result

class MockSessionState(dict):
    pass

class MockSession:
    def __init__(self):
        self.state = MockSessionState()

class MockContext:
    def __init__(self):
        self.session = MockSession()

class MockLLMRequest:
    def __init__(self, prompt):
        self.prompt = prompt

class MockAgentResponse:
    def __init__(self, text: str):
        self.text = text

class MockTool:
    def __init__(self, name):
        self.name = name

class MockAgent:
    """Offline mock agent for synthetic testing when API key is missing."""
    def __init__(self, tools, system_instruction):
        self.tools = tools
        self.system_instruction = system_instruction
        
    def generate_response(self, prompt: str) -> MockAgentResponse:
        callback_context = MockContext()
        llm_request = MockLLMRequest(prompt)
        
        # 1. before_model_callback
        res = before_model_callback(callback_context, llm_request)
        if res: llm_request.prompt = res
        
        prompt_lower = llm_request.prompt.lower()
        if "passkeys" in prompt_lower or "trend" in prompt_lower or "web" in prompt_lower:
            # Simulate public research
            tool = MockTool("public_research")
            args = {"query": llm_request.prompt}
            blocked = before_tool_callback(tool, args, None)
            
            if blocked:
                tool_res = blocked
            else:
                tool_res = self.tools[0](llm_request.prompt)
            tool_res = after_tool_callback(tool, args, None, tool_res)
            raw_response = f"Public Research Data for '{llm_request.prompt}': {tool_res}. I found this online."
            
        elif "policy" in prompt_lower or "mfa" in prompt_lower or "internal" in prompt_lower:
            # Simulate internal search
            tool = MockTool("internal_knowledge_search")
            args = {"query": llm_request.prompt}
            blocked = before_tool_callback(tool, args, None)
            
            if blocked:
                tool_res = blocked
            else:
                tool_res = self.tools[1](llm_request.prompt)
            tool_res = after_tool_callback(tool, args, None, tool_res)
            raw_response = f"Internal Policy Data for '{llm_request.prompt}': {tool_res}. According to our policy."
            
        elif "both" in prompt_lower:
            tool1 = MockTool("public_research")
            tool2 = MockTool("internal_knowledge_search")
            
            b1 = before_tool_callback(tool1, {"query": llm_request.prompt}, None)
            if b1: r1 = b1
            else: r1 = after_tool_callback(tool1, {"query": llm_request.prompt}, None, self.tools[0](llm_request.prompt))
            
            b2 = before_tool_callback(tool2, {"query": llm_request.prompt}, None)
            if b2: r2 = b2
            else: r2 = after_tool_callback(tool2, {"query": llm_request.prompt}, None, self.tools[1](llm_request.prompt))
            
            raw_response = f"Combined Data for '{llm_request.prompt}': {r1} and {r2}."
        else:
            raw_response = "I am a direct answer to your general question."
            
        llm_response = MockAgentResponse(raw_response)
        
        # 4. after_model_callback
        res = after_model_callback(callback_context, llm_response)
        if res: llm_response.text = res
        
        self.last_dlp_detected = callback_context.session.state.get("dlp_detected", [])
        return llm_response

class BankResearchGateway:
    def __init__(self, use_mock: bool = False):
        self.retriever = ChromaRetriever()
        self.tools = ResearchTools(self.retriever)
        
        self.use_mock = use_mock or not config.google_api_key
        if self.use_mock:
            self.agent = MockAgent(
                tools=self.tools.get_adk_tools(),
                system_instruction=SYSTEM_INSTRUCTION
            )
        else:
            try:
                from google.adk import Agent
                from google import genai
                
                client = genai.Client(api_key=config.google_api_key)
                
                self.agent = Agent(
                    model=config.gemini_model,
                    client=client,
                    tools=self.tools.get_adk_tools(),
                    system_instruction=SYSTEM_INSTRUCTION,
                    before_model_callback=before_model_callback,
                    before_tool_callback=before_tool_callback,
                    after_tool_callback=after_tool_callback,
                    after_model_callback=after_model_callback
                )
            except Exception as e:
                logger.error(f"Failed to initialize real ADK Agent: {e}")
                self.agent = MockAgent(tools=self.tools.get_adk_tools(), system_instruction=SYSTEM_INSTRUCTION)

    def _log_observability(self, request_id: str, prompt: str, latency: float, dlp_detected: List[str], blocked: bool, status: str):
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
        
        try:
            if hasattr(self.agent, "generate_response"):
                # Mock path handles callbacks internally
                response_obj = self.agent.generate_response(employee_prompt)
                raw_response = response_obj.text
                dlp_categories = getattr(self.agent, "last_dlp_detected", [])
            else:
                from google.adk import Runner
                runner = Runner(agent=self.agent)
                result = runner.run(employee_prompt)
                raw_response = str(result)
                # ADK runner should manage session state, logging empty here for demo
                dlp_categories = []
                
            status = "success"
        except Exception as e:
            logger.error(f"Agent execution failed: {e}")
            raw_response = "I encountered an error processing your request."
            status = "error"
            dlp_categories = []
            
        self._log_observability(
            request_id=request_id,
            prompt="[SANITIZED_BY_CALLBACKS]", 
            latency=time.time() - start_time,
            dlp_detected=dlp_categories,
            blocked=False,
            status=status
        )
        
        return raw_response

def demo():
    gateway = BankResearchGateway(use_mock=True)
    
    print("\n--- Direct Path ---")
    print(gateway.process_request("What is a database?"))
    
    print("\n--- Internal RAG Path ---")
    print(gateway.process_request("What is our MFA policy? My ID is EMP-12345."))
    
    print("\n--- Public Research Path ---")
    print(gateway.process_request("Research web passkeys for Rahul Sharma account 402918239."))

if __name__ == "__main__":
    demo()
