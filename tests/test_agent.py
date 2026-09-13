import pytest
from app.agent import (
    before_model_callback,
    before_tool_callback,
    after_tool_callback,
    after_model_callback,
    MockContext,
    MockLLMRequest,
    MockAgentResponse,
    MockTool
)

def test_before_model_callback():
    ctx = MockContext()
    req = MockLLMRequest("Hi, my name is Priya Patel and my account is 123456789. ID is EMP-12345.")
    before_model_callback(ctx, req)
    
    # Check that prompt was redacted/tokenized
    assert "Priya Patel" not in req.prompt
    assert "123456789" not in req.prompt
    assert "EMP-12345" not in req.prompt
    assert "<PERSON_001>" in req.prompt
    assert "<ACCOUNT_NO_001>" in req.prompt
    assert "[REDACTED]" in req.prompt
    
    # Check session state
    assert "fernet_key" in ctx.session.state
    assert "<PERSON_001>" in ctx.session.state["pii_tokens"]

def test_before_tool_callback():
    tool = MockTool("public_research")
    args = {"query": "Find info on Rahul Sharma"}
    
    res = before_tool_callback(tool, args, None)
    assert res is not None
    assert "BLOCKED" in res
    assert "PERSON" in res

def test_after_tool_callback():
    res = after_tool_callback(None, None, None, "This site mentions Rahul Sharma.")
    assert "Rahul Sharma" not in res
    assert "[REDACTED]" in res

def test_after_model_callback():
    ctx = MockContext()
    req = MockLLMRequest("Priya Patel")
    before_model_callback(ctx, req) # setup tokens
    
    # Model generates response with a token and a raw sensitive value
    res = MockAgentResponse("I found info for <PERSON_001>. Also new PII: 123456789.")
    after_model_callback(ctx, res)
    
    assert "Priya Patel" in res.text
    assert "123456789" not in res.text
    assert "[REDACTED]" in res.text
