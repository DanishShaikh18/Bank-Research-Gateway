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
  IDs, PAN, Aadhaar, email, phone), plus spaCy's NER model for names —
  regex can't reliably catch names, so it isn't used to try.
- **Tokenization**: detected values are encrypted with a session-scoped
  key (`cryptography.fernet`) and stored as `<TYPE_001>`-style tokens.
  Nothing raw is ever kept in memory — only ciphertext plus a key that
  lives for the duration of the conversation.
- **Where it runs**: as ADK callbacks on the agent itself, not as a
  separate wrapper layer sitting outside it:
  - `before_model_callback` — sanitizes the user's input before it
    reaches Gemini.
  - `before_tool_callback` — blocks the outbound web-search call if any
    raw sensitive value is still present (fails closed).
  - `after_tool_callback` — scrubs anything unexpected coming back from
    a tool, especially the external search.
  - `after_model_callback` — checks the model's own output for a leak,
    then swaps tokens back to real values for the final answer.
- **At ingestion**: documents are scanned before being indexed. A document
  with a couple of PII mentions gets those spans redacted and is indexed
  normally. A document that's mostly PII (looks like exported customer
  data rather than a policy doc) is skipped instead of indexed.

## Retrieval

Policy documents are chunked by markdown heading (not fixed-size windows),
so each chunk keeps its section context. Retrieval combines dense vector
similarity (ChromaDB) with a keyword-weighted score, so exact policy codes
(like `AUTH-SEC-042`) rank well even when the wording doesn't closely
match the query.

## Project structure

```
Bank-Research-Gateway/
├── app/
│   ├── config.py     # settings from .env
│   ├── privacy.py    # PII detection, tokenization
│   ├── rag.py         # chunking, embeddings, hybrid search
│   ├── tools.py       # internal_knowledge_search, public_research
│   └── agent.py       # ADK agent, callbacks, runner
├── data/internal_docs/    # sample bank policy documents
├── evals/
│   ├── pii_cases.jsonl
│   ├── rag_cases.jsonl
│   ├── routing.evalset.json      # ADK trajectory eval, 8 cases
│   ├── eval_config.json
│   ├── run_privacy_eval.py
│   └── run_rag_eval.py
├── scripts/ingest.py
├── tests/
├── requirements.txt
└── .env.example
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # .venv\Scripts\activate on Windows

pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Copy `.env.example` to `.env`:

```
GOOGLE_API_KEY=""              # optional — falls back to an offline mock if empty
GEMINI_MODEL="gemini-3.8-flash"
TAVILY_API_KEY=""              # optional — falls back to an offline mock if empty
CHROMA_PERSIST_DIRECTORY="./chroma_db"
```

## Running it

```bash
python scripts/ingest.py     # index the sample policy documents
python -m app.agent          # interactive demo
```

## Testing

Most of the test suite makes no API calls at all, so it's safe to run
constantly during development:

```bash
pytest tests/ -v
python evals/run_privacy_eval.py   # regex + spaCy only, reports real precision/recall/F1
python evals/run_rag_eval.py       # uses the offline mock embedder
```

One eval set does call the live model, since it's checking real agent
behavior. Run it manually before a commit or a demo, not on every change:

```bash
adk eval app evals/routing.evalset.json --config_file_path evals/eval_config.json --print_detailed_results
```

It checks 8 cases (2 per routing path) using deterministic metrics only —
tool-trajectory matching and ROUGE-based response matching, no
LLM-as-judge scoring, so it doesn't cost more than the calls needed to
produce the answers themselves.

## Known limitations

- No authentication or access control — this assumes one trusted user per
  session, not a multi-user deployment.
- No per-document access rules; anything indexed is retrievable by anyone
  using the agent.
- Name detection depends on spaCy's model — it won't catch every name,
  and that's a real limit of NER, not something regex could have solved
  either.
- The token vault is session-scoped and in-memory. Nothing persists after
  the process restarts, and that's intentional for how this runs — it
  hasn't been adapted for a multi-instance deployment.
- Runs locally. There's no cloud deployment step here.