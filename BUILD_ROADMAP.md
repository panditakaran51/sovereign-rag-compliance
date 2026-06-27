# Sovereign RAG — Build Roadmap

A practical, milestone-by-milestone guide to building the project from scratch. Each phase produces something runnable and demonstrable.

---

## Phase 1: Foundation (Week 1–2)
*Goal: A working local RAG loop from the command line.*

### 1.1 Environment Setup
- Install [Ollama](https://ollama.com) and pull `mistral` (7B)
- Install [Qdrant](https://qdrant.tech) via Docker: `docker run -p 6333:6333 qdrant/qdrant`
- Create a Python virtual environment with:
  ```
  langchain, langchain-community, langchain-qdrant
  llama-index (optional, for comparison)
  qdrant-client
  sentence-transformers (for local embeddings)
  pypdf, python-docx (document loaders)
  ```

### 1.2 Document Ingestion Script
Download the source documents (all publicly available PDFs):
- DORA full text: [EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32022R2554)
- EU AI Act full text: [EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689)
- BaFin BAIT circular: [BaFin website](https://www.bafin.de)

Build `scripts/ingest.py`:
1. Load PDFs with `PyPDFLoader`
2. Chunk with `RecursiveCharacterTextSplitter` (chunk size: 512, overlap: 64)
3. Embed with `nomic-embed-text` via Ollama
4. Upsert to Qdrant with metadata: `{source, article, page, date_ingested}`

**Deliverable:** Run a query from the Python REPL and get cited chunks back.

---

## Phase 2: RAG Pipeline (Week 2–3)
*Goal: A proper retrieval pipeline with hybrid search and re-ranking.*

### 2.1 Hybrid Retrieval
Replace pure dense search with hybrid:
- Dense: `nomic-embed-text` embeddings → Qdrant ANN search
- Sparse: BM25 via `rank_bm25` library over the same corpus
- Fusion: Reciprocal Rank Fusion (RRF) to merge the two result lists

This is critical for legal text — keyword matches on "Article 28(2)(c)" matter as much as semantic similarity.

### 2.2 Query Rewriting
Before retrieval, rewrite the user's question using the LLM:
```
"Does our SaaS vendor cause a DORA problem?" 
→ "ICT third-party service provider concentration risk DORA Article 28 contractual requirements"
```
Use a `QueryRewritingChain` — one small prompt before the retrieval call.

### 2.3 Prompting
Craft the system prompt carefully. Key requirements:
- Instruct the LLM to cite article numbers in every claim
- Instruct it to say "I cannot find this in the provided documents" rather than hallucinating
- Include the retrieved chunks in the prompt as structured XML blocks for clarity

### 2.4 Confidence Scoring
After generation, run a simple self-consistency check: ask the LLM to rate its own confidence (1–5) based on whether the retrieved context actually supported the answer. Flag anything below 3 for human review.

**Deliverable:** A Python function `query(question: str) -> Answer` that returns structured JSON with `{answer, sources, confidence}`.

---

## Phase 3: Backend API (Week 3–4)
*Goal: A production-style REST API wrapping the RAG pipeline.*

### 3.1 FastAPI App
Structure:
```python
POST /query          # Main query endpoint
POST /ingest         # Add new documents
GET  /sources        # List ingested documents
GET  /health         # Health check (for Docker/k8s)
GET  /audit-log      # Return paginated query history
```

### 3.2 Pydantic Models
Define strict input/output schemas:
```python
class QueryRequest(BaseModel):
    question: str
    filters: dict | None = None  # e.g., {"regulation": "DORA"}
    session_id: str | None = None

class Source(BaseModel):
    document: str
    article: str
    page: int
    excerpt: str

class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]
    confidence: int
    flagged_for_review: bool
    query_id: str
    timestamp: datetime
```

### 3.3 Audit Logging
Every query/response pair is written to a local SQLite DB (swap for Postgres in production). This satisfies DORA's requirement for logging AI-assisted decisions.

**Deliverable:** `curl` commands work against the local API. Swagger UI at `/docs`.

---

## Phase 4: Frontend (Week 4)
*Goal: A usable UI that looks professional in a demo.*

### 4.1 Streamlit App
Keep it clean:
- Text input for the question
- Optional regulation filter (DORA / EU AI Act / BaFin BAIT)
- Response card: answer text, confidence badge, expandable sources list
- Sidebar: session history, "flagged for review" queue

### 4.2 Demo-Ready Queries
Pre-load 5 example questions in the UI (buttons) that showcase the system's depth:
1. "What logging requirements does DORA impose on AI systems?"
2. "Is a credit-scoring model a high-risk AI system under the EU AI Act?"
3. "What must a DORA ICT incident report to BaFin contain?"
4. "Does GDPR Article 25 apply to our internal transaction monitoring system?"
5. "What are the BAIT requirements for cloud outsourcing?"

**Deliverable:** Screen recording of the UI answering all 5 questions with cited sources. Use this as the GIF in your README.

---

## Phase 5: Production Engineering (Week 5–6)
*Goal: The project signals "production-ready" to a technical recruiter.*

### 5.1 Docker Compose
`docker-compose.yml` with three services:
- `ollama` — local LLM inference
- `qdrant` — vector database (with persistent volume)
- `backend` — FastAPI app
- `frontend` — Streamlit app

One command to start everything: `docker compose up -d`

### 5.2 GitHub Actions CI
`.github/workflows/ci.yml`:
```yaml
on: [push, pull_request]
jobs:
  quality:
    steps:
      - ruff check .              # linting
      - pytest tests/unit/        # unit tests (mocked LLM)
      - bandit -r backend/        # security scan
      - trivy image sovereign-rag # Docker CVE scan
```

### 5.3 Terraform (IaC)
`infra/terraform/` — AWS deployment:
- Variables: `aws_region` (default: `eu-central-1`), `instance_type`
- Resources: ECS cluster, EFS volume, EC2 GPU instance (g4dn.xlarge for Ollama), VPC
- Outputs: Load balancer URL, Qdrant endpoint

Even if you never deploy it, having this file demonstrates you know how the project *would* be deployed.

### 5.4 Tests
- **Unit:** Test the chunking logic, query rewriting, confidence scorer
- **Integration:** Spin up a real Qdrant container in CI, ingest 3 test documents, run 5 known queries, assert that expected article numbers appear in sources

---

## Phase 6: Polish (Week 6–7)
*Goal: A portfolio piece that speaks for itself.*

### 6.1 README
Follow the structure already defined in `README.md`. Critical elements:
- GIF demo at the top (record with Loom or Kap)
- Architecture diagram (use Mermaid in the README — renders on GitHub)
- "Business case" section explaining the real cost savings

### 6.2 German Language Support
Add a second Ollama model: `mistral` with a German-language system prompt. Ingest the German versions of DORA and BaFin circulars (BaFin publishes in German). This is a major differentiator for German employers.

### 6.3 Blog Post (Optional but High-Impact)
Write a 1,500-word post on Medium or dev.to titled:
*"How I Built a GDPR-Compliant AI Compliance Assistant for DORA — With Zero Data Leaving the Server"*

Link it from your README and LinkedIn. German compliance communities on LinkedIn will share it.

---

## Architecture Decision Record (ADR)

Document why you chose each technology. Recruiters love this — it shows you think like a senior engineer.

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| LLM | Mistral 7B (local) | GPT-4 / Claude API | Data sovereignty; no PII to US APIs |
| Vector DB | Qdrant | Chroma, Pinecone | Self-hostable; production-grade; hybrid search |
| Embeddings | nomic-embed-text | OpenAI text-embedding-3 | Same sovereignty requirement |
| Framework | LangChain | Raw LLM calls | Faster iteration; well-known to hiring managers |
| Backend | FastAPI | Flask, Django | Async; auto-generates OpenAPI schema |
| IaC | Terraform | None / manual | Shows production mindset; portability |

---

## Estimated Time Investment

| Phase | Time | Output |
|---|---|---|
| Phase 1 | ~10 hrs | Working CLI RAG loop |
| Phase 2 | ~12 hrs | Hybrid retrieval + cited answers |
| Phase 3 | ~8 hrs | REST API |
| Phase 4 | ~6 hrs | Streamlit UI |
| Phase 5 | ~12 hrs | Docker, CI, Terraform |
| Phase 6 | ~8 hrs | Polish, German support |
| **Total** | **~56 hrs** | **Production-grade portfolio project** |

Spread over 6–7 weeks at ~8 hrs/week, this is completely achievable alongside other commitments.
