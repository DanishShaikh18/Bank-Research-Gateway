# Bank Research Gateway

A Google ADK agent that answers bank-employee questions by pulling from
internal policy documents, public web search, or both — while making sure
raw personal data (names, account numbers, PAN/Aadhaar numbers) never
reaches an external tool call, and is only restored in the final answer.

Built with Google ADK, Gemini, ChromaDB, and Tavily.

## What it does

An employee asks a question. The agent decides how to answer it:

- **Direct answer** — general questions that don't need a lookup.
- **Internal search** — questions about bank policy, answered from a local
  ChromaDB index of policy documents.
- **External search** — questions about outside topics (industry trends,
  advisories), answered via Tavily.
- **Both** — questions that need internal policy compared against external
  context.

Before any of this happens, the user's input is scanned for sensitive
entities. Anything critical (a name, account number, etc.) is swapped for
a placeholder token before it goes to the model or any external tool, and
swapped back to the real value only in the final response shown to the
employee.

## How the privacy part works

- **Detection**: regex for structured entities (account numbers, employee
  IDs, PAN, Aadhaar, email, phone), plus spaCy's NER model for names.
- **Tokenization**: detected values are encrypted with a session-scoped
  key (`cryptography.fernet`) and stored as `<TYPE_001>`-style tokens.
  Nothing raw is ever kept in memory — only ciphertext plus a key that
  lives for the duration of the conversation.
- **Where it runs**: as ADK callbacks on the agent itself:
  - `before_model_callback` — sanitizes the user's input before it reaches Gemini.
  - `before_tool_callback` — blocks the outbound web-search call if any raw sensitive value is still present.
  - `after_tool_callback` — scrubs anything unexpected coming back from a tool.
  - `after_model_callback` — checks the model's own output for a leak, then swaps tokens back to real values.
- **At ingestion**: documents are scanned before being indexed. A document
  with a couple of PII mentions gets those spans redacted and is indexed
  normally. A document that's mostly PII is skipped entirely.

## Retrieval

Policy documents are chunked by markdown heading (not fixed-size windows),
so each chunk keeps its section context. Retrieval combines dense vector
similarity (ChromaDB, using a local `BAAI/bge-small-en-v1.5` embedding
model) with a keyword-weighted score, so exact policy codes like
`AUTH-SEC-042` rank well even when the wording doesn't closely match.

Embeddings run entirely locally — **zero Gemini API calls** for search.

## Project structure

```
Bank-Research-Gateway/
├── app/
│   ├── config.py       # settings from .env
│   ├── privacy.py      # PII detection, tokenization, Fernet crypto
│   ├── rag.py          # chunking, local embeddings, hybrid search
│   ├── tools.py        # internal_knowledge_search, public_research
│   └── agent.py        # ADK agent, callbacks, runner
├── data/               # bank policy documents (markdown)
├── evals/
│   ├── pii_cases.jsonl         # PII detection test cases
│   ├── rag_cases.jsonl         # RAG retrieval test cases
│   ├── run_privacy_eval.py     # offline privacy evaluation
│   └── run_rag_eval.py         # offline RAG evaluation
├── frontend/
│   └── index.html      # web chat UI
├── scripts/
│   └── ingest.py       # index policy documents into ChromaDB
├── tests/              # pytest unit tests
├── server.py           # FastAPI server
├── requirements.txt
└── .env.example
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows

pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Copy `.env.example` to `.env` and fill in your keys:

```
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5   # runs locally, no API key needed
TAVILY_API_KEY=your_tavily_api_key
CHROMA_PERSIST_DIRECTORY=./chroma_db
```

## Running it

```bash
# 1. Index the policy documents (only needed once, or after adding new docs)
python scripts/ingest.py

# 2. Start the server
$env:PYTHONPATH="."; uvicorn server:app --host 0.0.0.0 --port 8000 --reload

# 3. Open http://localhost:8000 in your browser
```

## Testing

```bash
pytest tests/ -v

# Offline evals (no API calls, fast)
python evals/run_privacy_eval.py
python evals/run_rag_eval.py
```

## Known limitations

- No authentication or access control — one trusted user per session.
- No per-document access rules; anything indexed is retrievable by anyone.
- Name detection depends on spaCy's model — it won't catch every name.
- The token vault is session-scoped and in-memory. Nothing persists after
  the process restarts.
- Runs locally. No cloud deployment step.