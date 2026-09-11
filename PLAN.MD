# PLAN.md
# Bank Research Gateway — Privacy-Preserving Enterprise Research Agent

## 1. Project Goal

Build a small but production-minded AI gateway for bank employees.

The system allows an employee to ask research and knowledge questions while enforcing a privacy boundary around sensitive bank information.

The project demonstrates:

- Google ADK
- Gemini 3.8 Flash
- Agent tool calling
- RAG
- Hybrid retrieval
- Gemini Embedding 2
- Qdrant
- Public web research through Tavily
- Deterministic PII/DLP protection
- Tokenization and controlled detokenization
- Guardrails / policy enforcement
- Callbacks
- Evaluation
- Observability
- GCP-ready deployment

The system is NOT intended to make banking decisions, approve loans, access customer banking systems, or replace professional banking software.

It is a controlled research/knowledge gateway.

---

# 2. Core Design Principle

## KEEP THE SYSTEM SMALL

This project must demonstrate engineering depth through good architectural decisions, not through a large amount of code.

Do NOT create unnecessary:

- agents
- classes
- files
- services
- wrappers
- abstraction layers
- cloud services
- databases
- LLM calls
- helper modules

If a requirement can be implemented cleanly in 20 lines, do not turn it into 100 lines.

If ADK provides a capability directly, use ADK rather than recreating it.

Every agent, tool, node, class, function and service must have a clear reason to exist.

The final repository should remain easy to understand by one engineer.

---

# 3. High-Level Architecture

```text
Employee
   |
   v
Input DLP / Privacy Protection
   |
   |-- redact irrelevant sensitive data
   |-- tokenize sensitive data required for task
   |
   v
Sanitized Request
   |
   v
ONE ADK LLM AGENT
ResearchAgent
   |
   |-- direct answer
   |
   |-- public_research(query)
   |       |
   |       v
   |   outbound DLP
   |       |
   |       v
   |     Tavily
   |       |
   |       v
   |   response inspection
   |
   |-- internal_knowledge_search(query)
   |       |
   |       v
   |   Qdrant hybrid retrieval
   |       |
   |       v
   |   context inspection
   |
   v
Agent synthesis
   |
   v
Response DLP
   |
   |-- safe -> detokenize known tokens
   |
   |-- unsafe -> redact/block
   |
   v
Employee

Important:

The ADK agent is the ONLY LLM agent.

Do NOT create:

PII Agent
Security Agent
Research Agent + Summarizer Agent
RAG Agent
Web Agent
Response Agent

The privacy layer is deterministic code.

The ResearchAgent performs reasoning and tool selection.

4. Model Stack

Use current stable Google models available at implementation time.

Target stack:

Main LLM:
gemini-3.8-flash

Embedding:
gemini-embedding-2

Vector database:
Qdrant

External public search:
Tavily Search API

Do not use obsolete embedding models such as:

text-embedding-004
gemini-embedding-001

Do not hardcode old package versions from tutorials.

Before implementation, verify the currently supported versions of:

google-adk
google-genai
Python
Qdrant client
Tavily client/API

Use the current compatible versions.

5. Why Gemini 3.8 Flash + Tavily?

Gemini 3.8 Flash can use Google Search grounding for current information.

Therefore, web search is NOT required because Gemini is incapable of finding current information.

The project intentionally uses Tavily anyway.

Reason:

We want an explicit controlled external boundary:

Agent
  |
  v
public_research()
  |
  v
Outbound DLP
  |
  v
Tavily

This gives us explicit control over:

what leaves the trusted environment
privacy inspection before external transmission
external response inspection
source URLs
source metadata
logging
evaluation
external research behavior

Tavily is therefore an architectural choice for controlled external research, not a workaround for Gemini's capabilities.

6. Agent

Use ONE ADK LlmAgent.

Conceptually:

ResearchAgent
    |
    |-- public_research
    |
    |-- internal_knowledge_search

The agent should decide:

Case A — Direct answer

If it already knows the answer and no current/private information is required:

Agent -> Answer

Approximately one model turn.

Case B — Public research
Agent
  -> public_research()
  -> Agent synthesis
  -> Answer

Approximately two model turns.

Case C — Internal knowledge
Agent
  -> internal_knowledge_search()
  -> Agent synthesis
  -> Answer

Approximately two model turns.

Case D — Both
Agent
  -> tool(s)
  -> Agent synthesis
  -> Answer

Avoid unnecessary sequential tool calls.

The agent should not call a tool simply because a tool exists.

7. Agent Tools

Only expose the capabilities the agent actually needs.

Tool 1: public_research

Agent-facing interface:

public_research(query: str)

Do NOT expose every Tavily parameter to the agent.

The implementation should choose safe defaults.

The agent should provide the research question.

The tool implementation decides:

search depth
max results
topic
time range
domains
raw content behavior

based on safe project defaults.

Tavily Configuration

Initial default behavior:

include_answer = false
include_raw_content = false
max_results = small number, e.g. 5
search_depth = basic/fast by default

Why:

Tavily should retrieve evidence.

Gemini should reason over that evidence.

Do NOT use Tavily's answer generation as another LLM answer layer.

Avoid unnecessary context.

Advanced search can be used when higher precision is justified.

Do not make every request advanced.

Normalize Tavily Response

Do not pass the entire raw Tavily response into the agent.

Normalize it to something like:

{
  "sources": [
    {
      "title": "...",
      "url": "...",
      "content": "...",
      "relevance": 0.82
    }
  ]
}

Only return information needed by the agent.

8. Internal Knowledge Tool

Agent-facing interface:

internal_knowledge_search(query: str)

The tool performs:

query
  |
  v
embedding
  |
  +---- dense retrieval
  |
  +---- lexical retrieval
  |
  v
merge/rank
  |
  v
top relevant chunks

The tool returns:

relevant text
document identifier
section/heading
useful metadata
source reference

Do not return unnecessary database internals.

9. RAG Corpus

Use only synthetic/non-sensitive documents.

Example:

data/
└── internal_docs/
    ├── authentication_policy.md
    ├── employee_security_guide.md
    ├── engineering_standards.md
    └── approved_ai_usage.md

Never use real:

customer data
employee data
account numbers
bank production data
confidential documents

The repository must remain safe to publish as a portfolio project.

10. RAG Pipeline
Documents
   |
   v
Ingestion DLP
   |
   v
Structure-aware chunking
   |
   v
Gemini Embedding 2
   |
   v
Qdrant
   |
   v
Hybrid retrieval
   |
   v
Context privacy inspection
   |
   v
ResearchAgent
11. RAG Ingestion DLP

Documents must be inspected before embedding.

Flow:

document
   |
   v
PII/sensitive-data detector
   |
   +---- unsafe -> reject/quarantine
   |
   +---- safe -> continue

Do not embed sensitive documents by default.

The objective is to prevent sensitive data from entering the vector store accidentally.

12. Chunking Strategy

Do NOT blindly use:

500 tokens
100 overlap

Those numbers are not requirements.

The corpus contains policies, standards and technical documents.

Use structure-aware chunking:

Document
  |
  +-- heading
  |     |
  |     +-- paragraphs
  |
  +-- subsection
        |
        +-- paragraphs

Preserve headings and logical sections where possible.

Only split sections when they exceed the chosen size limit.

Evaluate reasonable candidate sizes, for example:

~300 tokens
~600 tokens
~900 tokens

Use the RAG evaluation dataset to determine which configuration works best.

The final chunk size should be an experimental result, not an arbitrary tutorial value.

Do not build a complicated chunking framework.

A small deterministic chunking function is enough.

13. Embeddings

Use:

Gemini Embedding 2

Generate an embedding for each chunk.

Store:

embedding
document_id
section
heading
chunk text
metadata

Use a sensible embedding dimension supported by the current model/API.

Do not add unnecessary embedding models.

14. Vector Database

Use:

Qdrant

Prefer local Docker/local development initially.

Do NOT introduce:

Kubernetes
distributed Qdrant
separate vector microservice
cloud vector infrastructure

unless there is an actual requirement.

The goal is to demonstrate retrieval engineering, not infrastructure complexity.

15. Retrieval Strategy

Use HYBRID retrieval.

Combine:

Dense semantic retrieval
+
Lexical/keyword retrieval

Why?

Internal bank-style policy documents contain exact identifiers and terminology.

For example:

AUTH-SEC-042
ABAC
MFA
approved_ai_usage

Keyword search can be better for exact terminology.

Semantic search is better for conceptual questions.

Therefore:

dense retrieval
       +
keyword retrieval
       |
       v
merge/rank
       |
       v
top K

The exact ranking/merge strategy should remain simple.

Do not add a separate complex reranking service unless evaluation proves it is necessary.

16. RAG Evaluation

Create a small golden dataset.

Example:

{
  "question": "What authentication methods are approved?",
  "expected_document": "authentication_policy.md",
  "expected_section": "Approved Methods",
  "expected_answer_facts": [
    "MFA is required",
    "approved authentication methods are listed"
  ]
}

Evaluate:

Retrieval
Recall@K
Precision@K where useful
MRR/ranking where useful
Context
context relevance
Answer
correctness
relevance
faithfulness/groundedness
citation/source correctness
Experiments

Compare:

dense only
keyword only
hybrid

Also compare reasonable chunking candidates.

Do not assume hybrid or a particular chunk size is best.

The evaluation should justify the final configuration.

17. Privacy / DLP Architecture

Privacy is deterministic.

DO NOT use an LLM to detect whether input contains PII.

That would defeat the privacy boundary because the sensitive data would already have been sent to an LLM.

Use:

Patterns / regex
+
local NER where useful
+
bank-specific configurable rules

The detector should produce typed spans.

Example:

[
  {
    "type": "PERSON",
    "start": 10,
    "end": 22,
    "value": "Rahul Sharma"
  },
  {
    "type": "APPLICATION_ID",
    "start": 40,
    "end": 46,
    "value": "839201"
  }
]

Detection is separate from policy.

Not every detected entity must automatically be treated as sensitive.

The policy determines which categories are:

redacted
tokenized
allowed
18. Redaction vs Tokenization

Do not tokenize everything.

Use REDACTION when the value is irrelevant to the task.

Example:

Research passkeys.
My employee ID is EMP-92831.

Employee ID is irrelevant.

Sanitized version:

Research passkeys.
My employee ID is [REDACTED].

Use TOKENIZATION when the identity/value is required for the final task.

Example:

Draft an email to Rahul Sharma regarding application 839201.

Sanitized:

Draft an email to <PERSON_001> regarding application <APPLICATION_001>.

Token vault:

PERSON_001       -> Rahul Sharma
APPLICATION_001  -> 839201
19. Token Vault

Use a per-request/session in-memory token vault for the prototype.

Example:

{
    "PERSON_001": "Rahul Sharma",
    "APPLICATION_001": "839201"
}

Requirements:

unique tokens per request/session
same source value can map consistently within that request
different values must not collide
only known generated tokens can be restored
never blindly replace arbitrary <PERSON_001> strings

No database is required for the token vault in the initial project.

20. External Privacy Boundary

Every external call must independently inspect its actual outbound payload.

Do NOT rely only on the first input scan.

Example:

Agent/tool request
      |
      v
Outbound DLP
      |
      +---- unsafe -> BLOCK
      |
      +---- safe -> Tavily

This is defense in depth.

The external service must never receive raw sensitive values.

21. External Response Inspection

External responses must also be inspected.

Tavily response
      |
      v
Response DLP
      |
      +---- unsafe -> redact/block
      |
      +---- safe -> Agent

If unexpected PII appears in the external response, do not blindly pass it through.

22. Final Response Protection

Before returning the final answer:

Agent response
     |
     v
Response DLP
     |
     +---- unsafe -> redact/block
     |
     +---- safe
            |
            v
     detokenize known tokens
            |
            v
        employee

Detokenization happens only inside the trusted boundary.

Never restore arbitrary token-looking strings.

23. Privacy Evaluation

Create a labelled synthetic dataset.

Approximately:

100–300 examples

depending on implementation time.

Example:

{
  "text": "Contact Rahul Sharma at rahul@example.com.",
  "entities": [
    {
      "type": "PERSON",
      "value": "Rahul Sharma"
    },
    {
      "type": "EMAIL",
      "value": "rahul@example.com"
    }
  ]
}

Measure:

precision
recall
F1
false positives
false negatives
outbound leakage rate
tokenization correctness
restoration correctness

Test edge cases:

multiple people
repeated people
different people
punctuation
unusual spacing
email
phone
IDs
application IDs
mixed PII
false-positive names
text that should be redacted
text that should be tokenized
24. Outbound Leakage Test

Use a fake/mock external service.

The mock service captures the exact payload that would have been sent.

Tests should assert:

raw sensitive value NOT present

Example:

Input:
"Research Rahul Sharma's application 839201."

Outbound payload:
"Research <PERSON_001>'s application <APPLICATION_001>."

Assert:

"Rahul Sharma" not in outbound_payload
"839201" not in outbound_payload

Target for the controlled test suite:

0 outbound leakage

Do NOT claim that the system provides mathematically guaranteed zero leakage in the real world.

25. RAG Privacy

Privacy must also exist in the RAG pipeline.

Ingestion
document
 -> DLP
 -> safe?
 -> embed

Unsafe documents are rejected/quarantined.

Retrieval

Retrieved chunks are inspected before being supplied to downstream components.

External Research

If internal RAG content is ever included in an external research request:

RAG context
   |
   v
Outbound DLP
   |
   v
external service

Never assume internal content is safe simply because it came from Qdrant.

Final response

Response DLP remains mandatory.

26. Guardrails / Policy

Use deterministic policy checks where possible.

Examples:

block unsafe external requests
prevent sensitive outbound data
prevent unauthorized categories of requests
validate tool inputs
validate tool outputs
validate final response

Do not create a separate "guardrail agent".

Use normal Python checks and ADK callbacks/tool wrappers where appropriate.

27. ADK Callbacks

Use callbacks only where they provide real value.

Useful areas:

request/execution tracing
tool invocation logging
policy enforcement
validation
observability

Do not create callbacks for every tiny operation.

Keep callback logic small.

28. Observability

Record useful operational information without recording sensitive data.

Capture:

request_id
timestamp
agent execution
selected tool
tool latency
tool success/failure
DLP category/count
blocked request
response validation result
final status

Never log:

raw PII
raw employee identifiers
raw customer identifiers
token vault contents
sensitive document contents

Example:

{
  "request_id": "req_123",
  "tool": "public_research",
  "latency_ms": 742,
  "dlp_detected": ["PERSON", "APPLICATION_ID"],
  "blocked": false,
  "status": "success"
}
29. Logging Philosophy

Logs should answer:

What happened?
Which tool was selected?
Was the request blocked?
How long did it take?
Did DLP trigger?
Did the tool fail?
Did final validation pass?

Logs should NOT answer:

What was the user's actual private value?
What was the customer's account number?
What was inside the token vault?

Privacy is more important than verbose debugging logs.

30. Testing Strategy

Keep tests focused.

Minimum useful groups:

tests/
├── test_privacy.py
├── test_rag.py
├── test_tools.py
└── test_agent.py

Do not create one test file for every function.

Privacy tests

Test:

detection
policy
redaction
tokenization
restoration
outbound blocking
response inspection
RAG tests

Test:

ingestion
chunking
embedding
retrieval
hybrid ranking
expected document retrieval
Tool tests

Test:

Tavily response normalization
external payload sanitization
tool failure behavior
malformed response handling

Use mocks for external APIs.

Do not require real Tavily calls for every test.

Agent tests

Test representative paths:

direct answer
public research
internal RAG
combined request
blocked sensitive request

Do not build hundreds of agent tests.

31. Project Structure

Keep the repository compact.

Preferred structure:

bank-research-gateway/
│
├── app/
│   ├── agent.py
│   ├── privacy.py
│   ├── rag.py
│   ├── tools.py
│   └── config.py
│
├── data/
│   └── internal_docs/
│       ├── authentication_policy.md
│       ├── employee_security_guide.md
│       ├── engineering_standards.md
│       └── approved_ai_usage.md
│
├── evals/
│   ├── pii_cases.jsonl
│   └── rag_cases.jsonl
│
├── tests/
│   ├── test_privacy.py
│   ├── test_rag.py
│   ├── test_tools.py
│   └── test_agent.py
│
├── scripts/
│   └── ingest.py
│
├── .env.example
├── requirements.txt / pyproject.toml
├── README.md
└── PLAN.md

This is a target, not a requirement.

If two modules can be cleanly combined, combine them.

Do NOT split files merely to make the architecture diagram look bigger.

32. File Responsibilities
agent.py

Contains:

the single ResearchAgent
agent instructions
tool registration
minimal ADK setup

Do not put DLP implementation here.

privacy.py

Contains the compact privacy subsystem:

detection
policy
redaction
tokenization
detokenization
outbound inspection
response inspection

These can be simple functions/classes.

Do NOT create six separate files for six conceptual components.

rag.py

Contains:

document loading
structure-aware chunking
embedding
Qdrant storage
retrieval
hybrid retrieval logic

Keep ingestion and retrieval understandable.

tools.py

Contains:

public_research()
internal_knowledge_search()

The tool functions should be thin.

Complex privacy behavior belongs in privacy.py.

config.py

Only configuration.

Examples:

model names
Qdrant URL
Tavily configuration
environment variables

Do not create a giant configuration framework.

scripts/ingest.py

One simple entry point to build/update the Qdrant collection.

No separate ingestion microservice.

33. Dependencies

Use only dependencies that solve actual problems.

Expected categories:

Google ADK / Google GenAI
Qdrant client
Tavily client or HTTP client
local NER library if actually needed
tokenization utilities if needed
pytest

Do not add libraries just because they are popular.

For example:

Do not add:

LangChain
LlamaIndex
CrewAI

unless there is a specific reason.

This project is specifically demonstrating Google ADK.

34. No Framework Stacking

Do not build:

ADK
+
LangChain
+
LlamaIndex
+
CrewAI
+
custom agent framework

ADK should be the primary agent/orchestration framework.

Python handles deterministic application logic.

35. LLM Call Discipline

Avoid unnecessary LLM calls.

Preferred:

DLP -> Agent -> Answer

rather than:

DLP
 -> classifier LLM
 -> planner LLM
 -> researcher LLM
 -> summarizer LLM
 -> security LLM
 -> answer

The system should use the model because reasoning is needed, not because an LLM can technically be inserted.

36. Example Requests
Direct
What is the difference between authentication and authorization?

Expected:

DLP
 -> ResearchAgent
 -> answer
Public research
What are the latest passkey adoption trends among banks?

Expected:

DLP
 -> ResearchAgent
 -> public_research()
 -> Tavily
 -> ResearchAgent synthesis
 -> response DLP
 -> answer with sources
Internal knowledge
What does our authentication policy require for employee access?

Expected:

DLP
 -> ResearchAgent
 -> internal_knowledge_search()
 -> Qdrant hybrid retrieval
 -> ResearchAgent synthesis
 -> response DLP
 -> answer with internal source
Privacy-aware public research

Input:

Research whether Rahul Sharma's application 839201 is affected by the new policy.

If those identifiers are unnecessary for public research, sanitize them.

External query should NOT contain:

Rahul Sharma
839201

The public search should receive only the information actually needed to research the public policy.

37. Source Handling

Public research responses should preserve useful source information:

title
URL
relevant content
relevance score if useful

The agent should cite/mention sources appropriately in the final response.

Internal RAG responses should identify the source document/section.

Do not dump raw retrieval objects into the final response.

38. Failure Handling

Keep failure handling simple and explicit.

Examples:

Tavily unavailable

Return a clear message that current public research could not be completed.

Do not hallucinate current information.

Qdrant unavailable

Return a clear internal knowledge retrieval failure.

Do not fabricate internal policy information.

DLP failure

Fail closed for external transmission.

If privacy inspection cannot determine whether an outbound payload is safe:

BLOCK
Invalid tool output

Do not blindly pass malformed tool output to the agent.

39. Evaluation Matrix

Final evaluation should cover four major areas.

A. Privacy
PII precision
PII recall
PII F1
outbound leakage rate
tokenization correctness
round-trip restoration
false-positive behavior
B. RAG
Recall@K
Precision@K where useful
MRR where useful
context relevance
answer correctness
faithfulness
source correctness
C. Agent
correct tool selection
successful tool execution
appropriate direct-answer behavior
correct synthesis
failure handling
D. System
latency
tool latency
failure rate
blocked request count
LLM call count

The evaluation should produce a small report/table.

Do not build a giant evaluation platform.

40. Evaluation Dataset Philosophy

Use small but meaningful datasets.

The objective is not:

10,000 examples

The objective is:

enough representative cases to expose architectural weaknesses

Use synthetic data because this is a portfolio project.

For every evaluation dataset, document:

what is being tested
expected behavior
metric
result
conclusion
41. Local Development First

Development order:

1. Basic ADK agent
2. Tool calling
3. Privacy layer
4. RAG ingestion
5. Qdrant retrieval
6. Hybrid retrieval
7. Tavily integration
8. External DLP boundary
9. Response protection
10. Evaluation
11. Observability
12. GCP deployment

Do not start by building the cloud architecture.

First make the local system correct.

42. GCP

Use GCP where it provides real value.

Potential responsibilities:

Gemini API
deployment/runtime
logging/observability
secret management
optional storage

Do not introduce unnecessary services.

Do not build:

GKE
Cloud Run
Pub/Sub
Cloud Functions
Cloud SQL
BigQuery
Firestore
Redis
Load Balancer
API Gateway

all at once.

Only use a service if the project actually needs it.

For the portfolio version, a simple ADK-compatible deployment target is sufficient.

Verify the current ADK deployment options at implementation time.

43. Secrets

Never commit:

TAVILY_API_KEY
GOOGLE_API_KEY
service account credentials
Qdrant credentials

Use:

.env

locally and the appropriate secret mechanism in deployment.

Provide:

.env.example

with variable names only.

44. Security Boundary

Trusted:

Employee
Application
Privacy layer
Token vault
Internal RAG
Qdrant
Agent runtime

Untrusted/external:

Tavily
Public websites
External research results

The key architectural property is:

No raw sensitive data crosses the external boundary.
45. What This Project Demonstrates

An interviewer should be able to see:

ADK
LlmAgent
tool calling
callbacks
sessions/state where useful
evaluation
observability
deployment
AI Engineering
agentic routing
tool selection
RAG
embeddings
hybrid retrieval
structured tool outputs
grounded generation
evaluation
Privacy Engineering
deterministic PII detection
policy-based handling
redaction
tokenization
controlled detokenization
outbound inspection
response inspection
privacy evaluation
Production Thinking
failure handling
logging
secret management
test strategy
measurable evaluation
controlled external integrations
46. Explicit Anti-Overengineering Rules

These rules are mandatory.

Rule 1

ONE agent.

Rule 2

Minimal number of tools.

Rule 3

No LLM-based PII detection.

Rule 4

No external LLM tool.

Gemini itself is the reasoning model.

Rule 5

No LangChain/LlamaIndex/CrewAI.

Rule 6

No FAISS.

Use Qdrant.

Rule 7

No arbitrary chunk-size magic numbers.

Evaluate chunking.

Rule 8

No unnecessary reranker.

Only add one if evaluation justifies it.

Rule 9

No unnecessary microservices.

Rule 10

No unnecessary cloud infrastructure.

Rule 11

No unnecessary abstraction classes.

Prefer simple functions when sufficient.

Rule 12

No raw PII in logs.

Rule 13

No real banking/customer data.

Rule 14

Do not add features simply because ADK supports them.

Use an ADK capability only when it solves an actual project requirement.

Rule 15

Do not optimize for line count.

Optimize for:

correctness
clarity
security
measurable behavior
maintainability

The smallest correct implementation is preferred.

47. Definition of Done

The project is complete when:

 One ADK ResearchAgent works
 Direct questions work
 Public research tool works
 Internal RAG tool works
 Gemini 3.8 Flash is used
 Gemini Embedding 2 is used
 Qdrant is used
 Hybrid retrieval works
 Structure-aware chunking works
 RAG evaluation exists
 Deterministic PII detection exists
 Redaction works
 Tokenization works
 Controlled detokenization works
 Outbound DLP works
 External response inspection works
 RAG ingestion DLP works
 Final response DLP works
 Privacy evaluation exists
 Mock external leakage test exists
 Tool failures are handled
 Sensitive data is excluded from logs
 Basic observability exists
 Tests cover the major paths
 README explains architecture and tradeoffs
 Local execution works
 GCP deployment path is documented/validated
 No unnecessary framework/service/agent has been introduced
48. Final Implementation Philosophy

This is an AI engineering portfolio project.

Its strength should come from the decisions:

ONE agent
+
small number of tools
+
deterministic privacy boundary
+
real RAG
+
hybrid retrieval
+
current embedding model
+
controlled web research
+
measurable evaluation
+
useful observability

not from:

many agents
+
many files
+
many services
+
many LLM calls
+
large amounts of boilerplate

When choosing between two implementations:

Prefer the simpler implementation if it satisfies the requirement equally well.

When adding a component, ask:

"What concrete requirement does this component solve?"

If there is no strong answer:

Do not add it.

The final codebase should feel like a thoughtful engineer built exactly what was required — not like an architecture diagram was converted into hundreds of lines of unnecessary code.