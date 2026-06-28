"""
Query rewriter — expands the user's question before retrieval.

Uses qwen3:30b-a3b (MoE, only 3B active params) because:
- This is a pre-processing step where speed matters more than depth
- The rewrite is a simple expansion task, not complex legal reasoning
- Saving the full qwen3.6:27b for generation where quality counts
"""
import ollama

from backend.config import settings

_REWRITE_PROMPT = """You are a regulatory document retrieval assistant.

Your task: rewrite the user's question as an optimised search query for EU financial regulation documents.

Rules:
- Include the regulation name if implied or stated (DORA, EU AI Act, BaFin BAIT, VAIT, GDPR)
- Include article numbers if referenced or implied
- Expand acronyms into their full legal terms (e.g. ICT → information and communication technology)
- Add relevant legal terminology that would appear in the regulation text
- Return ONLY the rewritten query — no explanation, no preamble

Examples:
Q: Does our SaaS vendor create a DORA problem?
A: ICT third-party service provider contractual requirements DORA Article 28 concentration risk critical functions

Q: Is our credit scoring AI high-risk?
A: credit scoring model high-risk artificial intelligence system EU AI Act Annex III classification financial services

Q: What must a DORA incident report contain?
A: major ICT-related incident report notification contents requirements DORA Article 19 Article 20

Now rewrite this question:
Q: {question}
A:"""


def rewrite(question: str) -> str:
    """
    Rewrite a natural-language question into a retrieval-optimised query.
    Returns the rewritten query string, falls back to the original on error.
    """
    client = ollama.Client(host=settings.ollama_base_url)
    try:
        response = client.generate(
            model=settings.ollama_rewrite_model,
            prompt=_REWRITE_PROMPT.format(question=question),
            options={"temperature": 0.0, "num_predict": 80},
        )
        rewritten = response["response"].strip()
        # Sanity check: if the model returned something very long or empty, fall back
        if not rewritten or len(rewritten) > 400:
            return question
        return rewritten
    except Exception:
        return question
