# Bank Research Gateway

A privacy-preserving enterprise research AI gateway built for bank employees using Google ADK, Gemini 3.8 Flash, Qdrant Hybrid Retrieval, and Tavily Public Search.

## Architecture & Principles
This project strictly follows the **Keep It Small** principle:
- **One ADK Agent**: A single `LlmAgent` handles internal knowledge and public research without unnecessary multi-agent bloat.
- **Deterministic Privacy**: PII detection, redaction, and tokenization are handled through deterministic rules and an in-memory `TokenVault`. An LLM is NEVER used for PII detection.
- **Zero-PII Observability**: Logs strictly capture request IDs, latencies, and category counts without recording raw customer or employee identifiers.
- **Defense in Depth**:
  - *Input DLP*: Tokenizes essential task data, redacts irrelevant data.
  - *Ingestion DLP*: Prevents sensitive internal documents from entering the vector database.
  - *Outbound DLP*: Validates all outgoing external search queries (fail-closed model).
  - *Response DLP*: Restores tokenized identifiers inside the trusted boundary before returning to the employee.

## Quick Start
1. Create a `.env` file from `.env.example`.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the synthetic documents ingestion:
   ```bash
   python scripts/ingest.py
   ```
4. Run the demo script:
   ```bash
   python -m app.agent
   ```

## Testing & Evaluation
Offline test harnesses are provided utilizing deterministic mock vectors and a mock ADK agent to evaluate the pipeline without requiring live API keys.

**Unit Tests:**
```bash
pytest tests/ -v
```

**Evaluations:**
```bash
python evals/run_privacy_eval.py
python evals/run_rag_eval.py
```

## Productionizing for GCP
When migrating from local testing to Google Cloud Platform:
1. Swap the local in-memory `:memory:` Qdrant client for a persistent internal Qdrant cluster.
2. The `BankResearchGateway` orchestrator can be deployed directly into a Cloud Run service as an API endpoint.
3. Manage `GOOGLE_API_KEY` and `TAVILY_API_KEY` via Google Secret Manager.
4. Integrate ADK logs with Google Cloud Logging securely since raw PII is stripped automatically.