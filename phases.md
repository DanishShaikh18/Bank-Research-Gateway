# Bank Research Gateway — Implementation Phases

This document outlines the four systematic phases for building the **Bank Research Gateway** in accordance with [PLAN.MD](file:///d:/Bank-Research-Gateway/PLAN.MD).

Since live `GOOGLE_API_KEY` and `TAVILY_API_KEY` are not yet populated, all phases will be written cleanly for production using the official `google-adk`, `google-genai`, `qdrant-client`, and `tavily-python` interfaces, paired with comprehensive synthetic/mock test harnesses that run **100% offline without live API keys**. Live keys will plug in seamlessly when ready without code modification.

---

## Phase 1: Deterministic Privacy & DLP Subsystem
**Goal:** Build and thoroughly test the zero-leakage deterministic privacy layer, token vault, and inspection boundary.

### Files
- [`app/privacy.py`](file:///d:/Bank-Research-Gateway/app/privacy.py)
- [`tests/test_privacy.py`](file:///d:/Bank-Research-Gateway/tests/test_privacy.py)
- [`evals/pii_cases.jsonl`](file:///d:/Bank-Research-Gateway/evals/pii_cases.jsonl)
- [`evals/run_privacy_eval.py`](file:///d:/Bank-Research-Gateway/evals/run_privacy_eval.py)

### Scope & Requirements
1. **Deterministic PII/Identifier Detector:**
   - Detects `PERSON`, `APPLICATION_ID`, `ACCOUNT_NO`, `EMPLOYEE_ID`, `EMAIL`, `PHONE`.
   - Uses regex patterns and rule-based recognition returning typed spans: `{"type": str, "start": int, "end": int, "value": str}`.
   - Strictly NO LLM calls for detection.
2. **Policy Engine (Redaction vs Tokenization):**
   - Redacts irrelevant sensitive items (`[REDACTED]`).
   - Tokenizes task-critical identifiers into format `<TYPE_001>` (e.g. `<PERSON_001>`, `<APPLICATION_001>`).
3. **Session/Request TokenVault:**
   - Thread-safe, per-request in-memory dictionary mapping tokens to raw values.
   - Collision-free, consistent mapping within the same request.
   - Detokenizes *only* known generated tokens; never blind replacement.
4. **Outbound DLP Inspector:**
   - Validates outbound payloads before external services (Tavily).
   - Fail-closed: blocks any request containing raw sensitive values.
5. **Response DLP & Detokenization:**
   - Scans final model output; verifies no raw internal leaks.
   - Restores known tokens only inside the trusted boundary.
6. **Testing & Validation:**
   - Unit tests covering all entity types, edge cases, repeated entities, punctuation, and fail-closed blocking.
   - Benchmark runner over `evals/pii_cases.jsonl` reporting Precision, Recall, F1, and Outbound Leakage Rate (Target: 0).

---

## Phase 2: RAG Pipeline with Hybrid Qdrant Retrieval
**Goal:** Implement document ingestion DLP, structure-aware chunking, Gemini Embedding 2 integration, and Qdrant hybrid search.

### Files
- [`app/rag.py`](file:///d:/Bank-Research-Gateway/app/rag.py)
- [`scripts/ingest.py`](file:///d:/Bank-Research-Gateway/scripts/ingest.py)
- [`tests/test_rag.py`](file:///d:/Bank-Research-Gateway/tests/test_rag.py)
- [`evals/rag_cases.jsonl`](file:///d:/Bank-Research-Gateway/evals/rag_cases.jsonl)
- [`evals/run_rag_eval.py`](file:///d:/Bank-Research-Gateway/evals/run_rag_eval.py)

### Scope & Requirements
1. **Ingestion DLP:**
   - Inspects documents before chunking/embedding. Quarantines/rejects docs with confidential PII or customer account numbers.
2. **Structure-Aware Chunking:**
   - Parses Markdown heading hierarchies (`#`, `##`, `###`) and paragraphs.
   - Preserves section context and breadcrumbs (`Policy > Section > Subsection`).
   - Supports configurable token sizes (~300, ~600, ~900 tokens) for empirical comparison.
3. **Embedding Module:**
   - Calls `gemini-embedding-2` via Google GenAI SDK when `GOOGLE_API_KEY` is provided.
   - Provides a deterministic offline vector mock generator for headless testing when keys are absent.
4. **Qdrant Storage & Hybrid Retrieval:**
   - Connects to Qdrant (in-memory `:memory:` or local URL).
   - Upserts dense vector + indexed text payload.
   - Executes hybrid retrieval combining dense vector similarity and keyword search via Reciprocal Rank Fusion (RRF).
5. **Context Privacy Inspection:**
   - Validates retrieved chunks before passing to downstream agent tools.
6. **Testing & Validation:**
   - Ingestion script to build collection from `data/internal_docs/`.
   - Unit tests for chunking, hybrid search ranking, and ingestion DLP.
   - Golden RAG evaluation benchmark measuring Recall@K and MRR on `evals/rag_cases.jsonl`.

---

## Phase 3: Controlled Agent Tools & External DLP Boundary
**Goal:** Build the two exposed tools with strict input/output sanitization, safe Tavily defaults, and graceful error handling.

### Files
- [`app/tools.py`](file:///d:/Bank-Research-Gateway/app/tools.py)
- [`tests/test_tools.py`](file:///d:/Bank-Research-Gateway/tests/test_tools.py)

### Scope & Requirements
1. **`public_research(query: str)`:**
   - Outbound DLP inspection: fails closed if raw sensitive data is present.
   - Tavily API integration with safe defaults: `search_depth="basic"`, `max_results=5`, `include_answer=False`, `include_raw_content=False`.
   - Normalizes raw Tavily output into clean structure: `{"sources": [{"title": ..., "url": ..., "content": ..., "relevance": ...}]}`.
   - External response inspection: scans retrieved content for unexpected sensitive leaks.
   - Failure handling: returns a structured error message if Tavily is unreachable or key is missing (no hallucinations).
2. **`internal_knowledge_search(query: str)`:**
   - Queries Qdrant hybrid retrieval via `app/rag.py`.
   - Formats relevant chunks with document name, section title, and source citation.
   - Failure handling: returns clear message if Qdrant is unreachable (no policy fabrication).
3. **Testing & Validation:**
   - Unit tests with mock Tavily API and in-memory Qdrant.
   - Mock leakage test: asserts 0 raw sensitive values cross the outbound boundary.
   - Tests for malformed responses and network failure fallbacks.

---

## Phase 4: Single ADK ResearchAgent, Observability & Gateway Delivery
**Goal:** Build the single ADK ResearchAgent with Gemini 3.8 Flash, zero-PII observability, full gateway integration, and documentation.

### Files
- [`app/agent.py`](file:///d:/Bank-Research-Gateway/app/agent.py)
- [`tests/test_agent.py`](file:///d:/Bank-Research-Gateway/tests/test_agent.py)
- [`README.md`](file:///d:/Bank-Research-Gateway/README.md)

### Scope & Requirements
1. **Single ADK `ResearchAgent`:**
   - Built using Google ADK (`LlmAgent`) configured with `gemini-3.8-flash`.
   - Strict instructions: knowledge research only, no loan/transaction decisions, explicit citations, concise grounded synthesis.
   - Registers both tools: `public_research` and `internal_knowledge_search`.
2. **Four Agent Execution Paths:**
   - Case A: Direct answer (general knowledge, ~1 turn).
   - Case B: Public research (market/regulatory trends, ~2 turns).
   - Case C: Internal knowledge (bank policies/standards, ~2 turns).
   - Case D: Combined synthesis.
3. **Observability & Callbacks:**
   - ADK callbacks to log: `request_id`, tool chosen, `latency_ms`, `dlp_detected` categories, `blocked` flag, final status.
   - Zero-PII logging guarantee: strictly no raw customer names, IDs, accounts, or vault contents in logs.
4. **End-to-End Gateway Orchestrator:**
   - Public function `process_employee_request(prompt: str) -> dict`.
   - Pipeline: Employee Request -> Input DLP / Token Vault -> ResearchAgent -> Response DLP & Detokenization -> Employee.
5. **Testing & Validation:**
   - Tests validating all 4 routing paths with mock LLM/runner.
   - Verifying blocked requests never invoke tools or leak data.
6. **Documentation (`README.md`):**
   - Architectural principles, data flow diagrams, security boundary explanation.
   - Step-by-step setup, running evaluations, running offline test suites, and switching on live keys.
   - GCP deployment guide (Cloud Run / Vertex AI ready).

---

## Progress Tracking

| Phase | Description | Status |
|---|---|---|
| **Phase 1** | Deterministic Privacy & DLP Subsystem | Pending |
| **Phase 2** | RAG Pipeline with Hybrid Qdrant Retrieval | Pending |
| **Phase 3** | Controlled Agent Tools & Outbound Boundary | Pending |
| **Phase 4** | Single ADK ResearchAgent, Observability & Gateway Delivery | Pending |
