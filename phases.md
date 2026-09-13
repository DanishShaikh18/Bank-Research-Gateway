# Refactor Execution Phases

Based on the `NEW_PLAN.MD` document, the refactoring work has been divided into the following 3 manageable phases to ensure iterative progress and stability.

## Phase 1: Terminology and Privacy Fundamentals
**Goal:** Establish the foundational privacy functions, remove unnecessary complexity (TokenVault, Qdrant), and align terminology across the project.
*   **Section 1: Terminology and positioning cleanup:** Rename DLP and RRF references. Update `README.md` to remove the GCP section and add the "Known Limitations" section. Remove Qdrant.
*   **Section 2: PII detection layer:** Update `app/privacy.py` with spaCy `PERSON` detection and additional regexes (PAN, Aadhaar). Implement the `pii_density` function.
*   **Section 4: Reversible tokenization:** Replace the in-memory `TokenVault` class in `app/privacy.py` with stateless `cryptography.fernet.Fernet` functions (`new_session_key`, `encrypt_span`, `decrypt_span`).

## Phase 2: Agent Integration and Ingestion Pipeline
**Goal:** Wire the privacy fundamentals into the application lifecycle (Agent callbacks and ingestion).
*   **Section 3: Ingestion-time PII handling:** Update `scripts/ingest.py` to use `pii_density()` to either redact or quarantine documents before chunking.
*   **Section 5: ADK callback wiring:** Update `app/agent.py` to implement the four required ADK callbacks (`before_model_callback`, `before_tool_callback`, `after_tool_callback`, `after_model_callback`) for PII detection, redaction, and tokenization/detokenization, removing the old ad-hoc wrapper functions.
*   **Section 6: RAG pipeline:** Apply renaming inside `app/rag.py` (RRF -> hybrid weighted score) with no structural changes.

## Phase 3: Testing and Evals
**Goal:** Ensure the system is robust through offline unit tests and a small, targeted evaluation set.
*   **Section 7: Testing (Free tests):** Rewrite `tests/test_privacy.py`, `tests/test_rag.py`, and `tests/test_agent.py` to use pure functions and offline mocks without LLM calls.
*   **Section 7: Testing (Paid tests):** Build the `evals/routing.evalset.json` (8 cases) and configure deterministic metrics in `evals/eval_config.json`. Update `run_privacy_eval.py` to report realistic numbers.
