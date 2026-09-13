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
    elif hasattr(llm_request, 'contents'):
        for content in llm_request.contents:
            if hasattr(content, 'parts'):
                for part in content.parts:
                    if hasattr(part, 'text') and part.text:
                        part_text = part.text
                        part_spans = detect_sensitive_spans(part_text)
                        if part_spans:
                            part_res = part_text
                            for span in reversed(part_spans):
                                if span.type in REDACT_TYPES:
                                    replacement = "[REDACTED]"
                                else:
                                    counters = state["pii_counters"]
                                    counters[span.type] = counters.get(span.type, 0) + 1
                                    token = f"<{span.type}_{counters[span.type]:03d}>"
                                    ciphertext = encrypt_span(span.value, state["fernet_key"])
                                    state["pii_tokens"][token] = ciphertext
                                    replacement = token
                                part_res = part_res[:span.start] + replacement + part_res[span.end:]
                            part.text = part_res
    return None

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
                
    if hasattr(llm_response, 'text') and not hasattr(llm_response, 'candidates'):
        llm_response.text = result
    elif hasattr(llm_response, 'candidates'):
        for cand in llm_response.candidates:
            if hasattr(cand, 'content') and hasattr(cand.content, 'parts'):
                for part in cand.content.parts:
                    if hasattr(part, 'text') and part.text:
                        part_text = part.text
                        for token, ciphertext in tokens.items():
                            if token in part_text:
                                plaintext = decrypt_span(ciphertext, key)
                                part_text = part_text.replace(token, plaintext)
                        part.text = part_text
    return None


class BankResearchGateway:
    def __init__(self):
        self.retriever = ChromaRetriever()
        self.tools = ResearchTools(self.retriever)
        
        from google.adk import Agent
        from google import genai
        
        if not config.google_api_key:
            raise ValueError("google_api_key is required to initialize the agent.")
            
        self.agent = Agent(
            name="bank_gateway",
            instruction=SYSTEM_INSTRUCTION,
            tools=self.tools.get_adk_tools(),
            before_model_callback=before_model_callback,
            before_tool_callback=before_tool_callback,
            after_tool_callback=after_tool_callback,
            after_model_callback=after_model_callback
        )

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
            import asyncio
            from google.adk import Runner
            from google.adk.sessions import InMemorySessionService
            from google.genai import types as genai_types

            session_service = InMemorySessionService()
            runner = Runner(
                agent=self.agent,
                app_name="bank_gateway",
                session_service=session_service,
            )

            async def _run():
                session = await session_service.create_session(
                    app_name="bank_gateway",
                    user_id="employee",
                    session_id=request_id,
                )
                content = genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=employee_prompt)]
                )
                raw_response = ""
                async for event in runner.run_async(
                    user_id="employee",
                    session_id=request_id,
                    new_message=content,
                ):
                    if event.is_final_response() and event.content and event.content.parts:
                        raw_response = "".join(
                            p.text for p in event.content.parts if hasattr(p, "text") and p.text
                        )
                return raw_response

            raw_response = asyncio.run(_run())
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

# Expose agent for ADK CLI
default_gateway = BankResearchGateway()
root_agent = default_gateway.agent
