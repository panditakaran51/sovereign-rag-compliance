# 🏦 Sovereign RAG — EU Financial Compliance Assistant

> A fully local Retrieval-Augmented Generation (RAG) system for querying EU financial regulations (DORA, EU AI Act, BaFin circulars) — zero data leaves your infrastructure.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![CI](https://github.com/yourusername/sovereign-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/sovereign-rag/actions)

---

## The Problem

DORA (Digital Operational Resilience Act) has been legally binding since January 17, 2025. The EU AI Act's high-risk financial services deadline hits **August 2, 2026**. BaFin is conducting on-site inspections right now.

Compliance officers at German financial institutions spend thousands of hours manually cross-referencing regulatory texts — asking questions like:

- *"Does our third-party ICT vendor contract satisfy Article 30 of DORA?"*
- *"Is our credit-scoring model a high-risk AI system under Annex III of the EU AI Act?"*
- *"Which BaFin circular applies to our cloud infrastructure?"*

This system answers those questions in seconds — **entirely on-premise**, with full source citations, and no data ever sent to a US API.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User (Browser / API)                  │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────┐
│              FastAPI Backend (REST + WebSocket)          │
│  - Query parsing          - Source citation formatting   │
│  - Session management     - Audit logging                │
└────────────┬──────────────────────────┬─────────────────┘
             │                          │
┌────────────▼──────────┐  ┌────────────▼─────────────────┐
│   LangChain / RAG     │  │     Qdrant Vector Database    │
│   Orchestration       │  │   (local Docker container)    │
│   - Query rewriting   │  │   - Chunked regulation docs   │
│   - Hybrid retrieval  │  │   - BM25 + dense embeddings   │
│   - Re-ranking        │  │   - Filtered by source/date   │
└────────────┬──────────┘  └──────────────────────────────┘
             │
┌────────────▼──────────────────────────────────────────┐
│          Mistral 7B / Llama 3 (via Ollama)            │
│          Runs entirely on local hardware              │
│          No outbound API calls                        │
└───────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| LLM | Mistral 7B Instruct (via Ollama) | EU data sovereignty; no external API |
| Embeddings | `nomic-embed-text` (local) | Same sovereignty requirement |
| Vector DB | Qdrant (Docker) | Self-hostable, production-grade, hybrid search |
| RAG Framework | LangChain + LlamaIndex | Best-in-class retrieval pipelines |
| Backend | FastAPI | Async, OpenAPI schema auto-generated |
| Frontend | Streamlit | Fast to iterate; swap for React in production |
| Containerisation | Docker Compose | One-command setup; reproducible environments |
| IaC | Terraform (AWS module included) | Shows production deployment path |
| CI/CD | GitHub Actions | Lint → test → security scan on every push |

---

## Document Corpus

The system is pre-loaded to ingest:

- **DORA** — Regulation (EU) 2022/2554 (full text + RTS/ITS drafts)
- **EU AI Act** — Regulation (EU) 2024/1689 (full text, Annex I–III focus)
- **BaFin BAIT** — Banking Supervisory Requirements for IT (latest circular)
- **BaFin VAIT / ZAIT** — Insurance & payment services equivalents
- **ECB TIBER-EU** — Threat Intelligence-Based Ethical Red Teaming framework

All documents are chunked, embedded, and stored locally. New circulars can be added via the `/ingest` endpoint.

---

## Key Features

### Sovereign by Design
The LLM, embedding model, and vector database all run on your hardware. The system explicitly refuses to route any query to an external API — this is enforced at the network layer in the Docker Compose configuration.

### Hybrid Retrieval
Uses both dense vector search (semantic similarity) and BM25 keyword search (important for legal terms like "Article 30", "RTS", "ICT third-party provider"). Results are fused and re-ranked before being passed to the LLM.

### Cited Answers
Every response includes structured source citations: document name, article number, paragraph, and page reference. Compliance officers can verify every claim against the original regulation.

### Audit Logging
Every query and response is logged with a timestamp and session ID. This is a DORA requirement for AI-assisted systems used in regulated contexts.

### Human-in-the-Loop Ready
High-confidence answers are returned directly. Low-confidence answers (below configurable threshold) are flagged for human expert review before being shown.

---

## Quickstart

**Prerequisites:** Docker Desktop, 8 GB RAM minimum (16 GB recommended for Mistral 7B)

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/sovereign-rag.git
cd sovereign-rag

# 2. Pull the local LLM (this downloads ~4 GB)
ollama pull mistral

# 3. Start all services
docker compose up -d

# 4. Ingest the regulation documents
python scripts/ingest.py --corpus docs/regulations/

# 5. Open the UI
open http://localhost:8501
```

Or hit the API directly:

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the ICT third-party risk requirements under DORA Article 28?"}'
```

---

## Example Query

**Input:**
> *"Our bank uses a US-based SaaS provider for transaction monitoring. Does this create a DORA compliance risk?"*

**Output:**
> Based on DORA Article 28 and RTS on subcontracting, engaging a third-country ICT service provider for a critical or important function requires a written contractual arrangement that ensures the provider can be audited by BaFin and is subject to EU law standards. The absence of an EU-equivalent data protection regime in the provider's country of domicile would constitute a concentration risk that must be disclosed under Article 29...
>
> **Sources:** DORA Art. 28(2)(c), DORA Art. 29, EBA RTS on subcontracting (Draft, Nov 2024)

---

## Project Structure

```
sovereign-rag/
├── backend/
│   ├── api/            # FastAPI routes
│   ├── rag/            # Retrieval & generation pipeline
│   ├── ingestion/      # Document loaders, chunkers, embedders
│   └── audit/          # Query + response logging
├── frontend/
│   └── app.py          # Streamlit UI
├── docs/
│   └── regulations/    # Regulation PDFs (not committed; see ingest script)
├── infra/
│   ├── docker-compose.yml
│   └── terraform/      # AWS deployment (ECS + EFS for Qdrant)
├── tests/
│   ├── unit/
│   └── integration/
├── .github/
│   └── workflows/
│       ├── ci.yml       # Lint, test, security scan
│       └── deploy.yml   # Push to ECR + ECS (on tag)
└── scripts/
    └── ingest.py
```

---

## CI/CD Pipeline

Every push triggers:

1. **Lint** — `ruff` (Python) + `prettier` (frontend)
2. **Unit tests** — `pytest` with mocked LLM and vector DB
3. **Integration tests** — Spins up Qdrant in Docker, runs real retrieval tests
4. **Security scan** — `bandit` for Python vulnerabilities + `trivy` for Docker image CVEs
5. **SBOM generation** — Software Bill of Materials (required for DORA ICT risk documentation)

---

## Deployment (Production)

The `infra/terraform/` directory provisions:

- **AWS ECS Fargate** for the FastAPI backend
- **AWS EFS** (persistent volume) for Qdrant data
- **AWS EC2 GPU instance** for Ollama / LLM inference (g4dn.xlarge)
- **VPC with no public subnets** — all traffic stays within the private network
- **CloudTrail + CloudWatch** for audit logging

For German financial institutions requiring EU data residency, switch the AWS region to `eu-central-1` (Frankfurt).

---

## Regulatory Context

This project directly addresses requirements from:

| Regulation | Relevant Articles | How This System Helps |
|---|---|---|
| DORA (2022/2554) | Art. 28, 29, 30 | ICT third-party risk assessment queries |
| EU AI Act (2024/1689) | Annex III, Art. 9-17 | High-risk AI classification & compliance checks |
| GDPR (2016/679) | Art. 25 (Privacy by Design) | No PII ever leaves the system |
| BaFin BAIT | §4 (IT risk management) | IT architecture compliance queries |

---

## Roadmap

- [x] Core RAG pipeline with local Mistral
- [x] Qdrant integration with hybrid retrieval
- [x] FastAPI backend with audit logging
- [x] Streamlit frontend
- [x] Docker Compose setup
- [ ] Multi-language support (German regulatory texts)
- [ ] Graph-based knowledge retrieval (regulations cross-reference each other)
- [ ] Integration with BaFin's regulatory update RSS feed for automatic re-ingestion
- [ ] Role-based access control (RBAC) for enterprise multi-user deployments

---

## Why This Matters (Business Case)

Large consulting firms (Big 4, BCG, McKinsey) charge €2,000–€5,000/day for DORA compliance advisory. Much of this work is reading, cross-referencing, and summarising regulatory texts — exactly what this system automates. For a mid-sized German bank with 5 compliance officers, this system could realistically save 200+ hours per quarter.

---

## License

MIT — use it, fork it, productionize it.

---

*Built to demonstrate sovereign AI deployment in regulated financial environments. For questions or collaboration, reach out via [GitHub Issues](https://github.com/yourusername/sovereign-rag/issues).*
