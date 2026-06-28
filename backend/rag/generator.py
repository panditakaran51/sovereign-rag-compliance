"""
Generator — produces cited answers from retrieved chunks.

Two models used:
- qwen3.6:27b (dense 27B): generates the answer. Quality matters here.
- qwen3:30b-a3b (MoE, 3B active): scores confidence. Simple 1-5 task.

Streaming: generation yields tokens as they arrive so the caller can
display them progressively. This converts a 90-second wait into a
live typing experience — critical for demo usability.
"""
from dataclasses import dataclass, field
from typing import List, Generator

import ollama

from backend.rag.retriever import RetrievedChunk
from backend.config import settings


_SYSTEM_PROMPT = """You are a specialist EU financial regulation compliance assistant.
You answer questions strictly from the regulatory passages provided to you.

Rules you must follow:
1. Cite the source document and page number for every factual claim you make.
   Format: (Source: <filename>, p.<page>)
2. If the provided passages do not contain enough information to answer, say exactly:
   "The provided documents do not contain sufficient information to answer this question."
   Do not speculate or use knowledge outside the passages.
3. Be precise. Compliance officers will act on your answers.
4. Answer in the same language the question was asked in.
5. Where relevant, name the specific Article number if the passage is part of a numbered article."""


_CONFIDENCE_PROMPT = """Rate how well the answer below is supported by the provided regulatory passages.

Scale:
1 = Not supported / the answer contradicts or ignores the passages
2 = Weakly supported — some overlap but key claims lack evidence
3 = Reasonably supported — main points covered, minor gaps
4 = Well supported — all major claims traceable to passages
5 = Fully supported — every claim has a direct citation

Passages provided: {n_chunks} chunks from {sources}
Answer excerpt: {answer_excerpt}

Respond with ONLY a single digit 1-5."""


def _build_context(chunks: List[RetrievedChunk]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, 1):
        article_note = f" article='{','.join(chunk.articles)}'" if chunk.articles else ""
        parts.append(
            f"<passage id='{i}' source='{chunk.source_file}' "
            f"page='{chunk.page_number}'{article_note}>\n"
            f"{chunk.text}\n"
            f"</passage>"
        )
    return "\n\n".join(parts)


@dataclass
class Answer:
    text: str
    sources: List[RetrievedChunk]
    confidence: int = 0
    flagged: bool = False
    model: str = field(default_factory=lambda: settings.ollama_llm_model)


def generate_streaming(
    question: str,
    chunks: List[RetrievedChunk],
) -> Generator[str, None, Answer]:
    """
    Stream answer tokens as they arrive, then yield the final Answer object.

    Usage:
        gen = generate_streaming(q, chunks)
        for token in gen:
            print(token, end="", flush=True)
        answer = gen.value  # not available with yield-based generators

    Callers should use the helper `stream_and_collect` instead.
    """
    context = _build_context(chunks)
    user_message = (
        f"Regulatory passages:\n\n{context}\n\n---\n\n"
        f"Question: {question}\n\n"
        f"Answer based only on the passages above. "
        f"Cite sources inline as (Source: filename, p.N)."
    )

    client = ollama.Client(host=settings.ollama_base_url)
    full_text = []

    stream = client.chat(
        model=settings.ollama_llm_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        stream=True,
        options={"temperature": 0.1},
    )

    for chunk in stream:
        token = chunk["message"]["content"]
        full_text.append(token)
        yield token

    answer_text = "".join(full_text)
    confidence = _score_confidence(answer_text, chunks, client)

    return Answer(
        text=answer_text,
        sources=chunks,
        confidence=confidence,
        flagged=confidence < settings.confidence_threshold,
    )


def _score_confidence(
    answer_text: str,
    chunks: List[RetrievedChunk],
    client: ollama.Client,
) -> int:
    """Ask the fast MoE model to rate answer confidence 1–5."""
    sources = ", ".join(sorted({c.source_file for c in chunks}))
    prompt = _CONFIDENCE_PROMPT.format(
        n_chunks=len(chunks),
        sources=sources,
        answer_excerpt=answer_text[:600],
    )
    try:
        response = client.generate(
            model=settings.ollama_rewrite_model,
            prompt=prompt,
            options={"temperature": 0.0, "num_predict": 3},
        )
        digit = response["response"].strip()[:1]
        score = int(digit)
        return score if 1 <= score <= 5 else 3
    except Exception:
        return 3


def stream_and_collect(
    question: str,
    chunks: List[RetrievedChunk],
    on_token=None,
) -> Answer:
    """
    Run generation, call on_token(token) for each streamed token,
    and return the final Answer with confidence score.
    """
    context = _build_context(chunks)
    user_message = (
        f"Regulatory passages:\n\n{context}\n\n---\n\n"
        f"Question: {question}\n\n"
        f"Answer based only on the passages above. "
        f"Cite sources inline as (Source: filename, p.N)."
    )

    client = ollama.Client(host=settings.ollama_base_url)
    full_text = []

    stream = client.chat(
        model=settings.ollama_llm_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        stream=True,
        options={"temperature": 0.1},
    )

    for chunk in stream:
        token = chunk["message"]["content"]
        full_text.append(token)
        if on_token:
            on_token(token)

    answer_text = "".join(full_text)
    confidence = _score_confidence(answer_text, chunks, client)

    return Answer(
        text=answer_text,
        sources=chunks,
        confidence=confidence,
        flagged=confidence < settings.confidence_threshold,
    )
