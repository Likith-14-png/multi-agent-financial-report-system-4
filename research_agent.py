"""
Multi-Agent Financial Research System — Infosys Springboard Virtual
Internship 7.0, Team 4.

Responsibilities (per project README):
  - Answering financial questions
  - Multi-step reasoning
  - Retrieval from ChromaDB
  - Source citations

This module is intentionally decoupled from the other agents' internals: it
takes an already-created, already-populated ChromaDB **Collection** object
(built by the Document Agent — Likith) and never creates or writes to the
collection itself. That's the integration point between agents: whoever
calls ResearchAgent(...) just needs to hand it the shared collection.

------------------------------------------------------------------------
METADATA CONTRACT (agreed with Document Agent / Extraction / Red Flag)
------------------------------------------------------------------------
Every chunk added to the ChromaDB collection is expected to carry this
metadata dict (used here for filtering and building citations):

    {
        "company":     str,   # e.g. "Orion Steelworks Ltd"
        "doc_type":    str,   # e.g. "Annual Report", "10-K", "Earnings Call Transcript"
        "section":     str,   # e.g. "Balance Sheet", "MD&A", "Auditor's Report"
        "source_file": str,   # original filename, for traceability
        "period":      str,   # optional, e.g. "FY2024" — pass "" if unknown
    }

and the chunk's ChromaDB id should be a stable string like "{doc_id}-{idx}".
If a field is missing, ResearchAgent degrades gracefully (shows "unknown").

------------------------------------------------------------------------
USAGE
------------------------------------------------------------------------
    import chromadb
    from chromadb.utils import embedding_functions
    from research_agent import ResearchAgent

    client = chromadb.PersistentClient(path="./chroma_db")
    embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = client.get_or_create_collection(
        name="financial_documents", embedding_function=embed_fn
    )
    # ... Document Agent populates `collection` with chunks + the metadata above ...

    agent = ResearchAgent(collection)
    answer = agent.answer(
        "Which company has the highest debt-to-equity ratio, and does "
        "Nimbus Cloud Technologies have any going concern risk?"
    )
    print(answer.final_answer)
    for c in answer.all_citations():
        print(c)

Optional: route the grounded evidence through an LLM for more fluent prose
instead of the built-in deterministic synthesizer:

    def call_llm(prompt: str) -> str:
        # e.g. call the Anthropic API, OpenAI, or a local HF pipeline here
        ...

    agent.set_llm_generator(call_llm)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Dict, Any


# ------------------------------------------------------------------ #
# Data models
# ------------------------------------------------------------------ #

@dataclass
class Citation:
    company: str
    doc_type: str
    section: str
    source_file: str
    chunk_id: str
    snippet: str
    score: Optional[float] = None   # similarity/distance from ChromaDB, if available

    def __str__(self) -> str:
        return (f"[{self.company} | {self.doc_type} | {self.section} | "
                f"{self.source_file} | chunk {self.chunk_id}]")


@dataclass
class ResearchStep:
    sub_question: str
    citations: List[Citation] = field(default_factory=list)
    findings: str = ""


@dataclass
class ResearchAnswer:
    question: str
    steps: List[ResearchStep]
    final_answer: str

    def all_citations(self) -> List[Citation]:
        seen, out = set(), []
        for step in self.steps:
            for c in step.citations:
                key = (c.company, c.doc_type, c.section, c.chunk_id)
                if key not in seen:
                    seen.add(key)
                    out.append(c)
        return out


# ------------------------------------------------------------------ #
# Research Agent
# ------------------------------------------------------------------ #

_SPLIT_RE = re.compile(r"\?|(?:,?\s+\band\b\s+)|;", re.IGNORECASE)


class ResearchAgent:
    """
    Parameters
    ----------
    collection:
        A ChromaDB Collection object (or anything exposing the same
        `.query(query_texts=[...], n_results=int, where=dict|None)` and
        `.get(include=[...])` interface — this is what lets the agent be
        unit-tested with a mock collection without ChromaDB installed).
    llm_generate:
        Optional callable(prompt: str) -> str. When set, it's used only to
        turn already-retrieved, already-cited evidence into smoother prose —
        it never invents evidence itself. When unset, a deterministic
        template synthesizer is used (works fully offline, cannot
        hallucinate a figure).
    """

    name = "Research Agent"

    def __init__(self, collection: Any, llm_generate: Optional[Callable[[str], str]] = None):
        self.collection = collection
        self._llm_generate = llm_generate
        self._companies_cache: Optional[List[str]] = None

    def set_llm_generator(self, fn: Callable[[str], str]) -> None:
        self._llm_generate = fn

    # -------------------------------------------------------------- #
    # Public entry point
    # -------------------------------------------------------------- #
    def answer(self, question: str, top_k: int = 4,
               company: Optional[str] = None) -> ResearchAnswer:
        """Answer a (possibly multi-part) financial research question.

        Multi-step reasoning: the question is decomposed into sub-questions,
        each is answered independently via retrieval + grounded synthesis
        from ChromaDB, and the per-step findings are then combined into a
        final cited answer.
        """
        sub_questions = self._decompose(question)
        steps = [self._answer_sub_question(sq, top_k, company) for sq in sub_questions]

        if self._llm_generate:
            final = self._llm_generate(self._build_llm_prompt(question, steps))
        else:
            final = self._template_synthesis(question, steps)

        return ResearchAnswer(question=question, steps=steps, final_answer=final)

    # -------------------------------------------------------------- #
    # Step 1: decompose a multi-part question
    # -------------------------------------------------------------- #
    def _decompose(self, question: str) -> List[str]:
        parts = [p.strip(" ,.") for p in _SPLIT_RE.split(question) if p.strip(" ,.")]
        return parts if parts else [question.strip()]

    # -------------------------------------------------------------- #
    # Step 2: retrieval from ChromaDB, per sub-question
    # -------------------------------------------------------------- #
    def _answer_sub_question(self, sub_q: str, top_k: int,
                              company: Optional[str]) -> ResearchStep:
        target_company = company or self._infer_company(sub_q)
        where = {"company": target_company} if target_company else None

        try:
            results = self.collection.query(query_texts=[sub_q], n_results=top_k, where=where)
        except Exception as exc:
            return ResearchStep(sub_question=sub_q,
                                 findings=f"Retrieval failed ({exc}). "
                                          f"Check that the ChromaDB collection is reachable.")

        ids = (results.get("ids") or [[]])[0]
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[None] * len(ids)])[0]

        if not ids:
            return ResearchStep(
                sub_question=sub_q,
                findings="No indexed documents contain evidence for this. "
                         "Upload the relevant filing via the Document Agent first.",
                citations=[],
            )

        citations: List[Citation] = []
        evidence_lines: List[str] = []
        for cid, doc_text, meta, dist in zip(ids, docs, metas, dists):
            meta = meta or {}
            snippet = (doc_text or "")[:220] + ("…" if doc_text and len(doc_text) > 220 else "")
            cit = Citation(
                company=meta.get("company", "unknown"),
                doc_type=meta.get("doc_type", "unknown"),
                section=meta.get("section", "unknown"),
                source_file=meta.get("source_file", "unknown"),
                chunk_id=str(cid),
                snippet=snippet,
                score=dist,
            )
            citations.append(cit)
            evidence_lines.append(f"  - \"{snippet}\"  {cit}")

        findings = f"Top evidence retrieved for \"{sub_q}\":\n" + "\n".join(evidence_lines)
        return ResearchStep(sub_question=sub_q, findings=findings, citations=citations)

    # -------------------------------------------------------------- #
    # Helper: figure out which company a sub-question is about, if any,
    # so retrieval can be scoped with a `where` filter.
    # -------------------------------------------------------------- #
    def _infer_company(self, text: str) -> Optional[str]:
        companies = self._get_companies()
        low = text.lower()
        for c in companies:
            if c.lower() in low:
                return c
        return None

    def _get_companies(self) -> List[str]:
        if self._companies_cache is not None:
            return self._companies_cache
        try:
            got = self.collection.get(include=["metadatas"])
            metas = got.get("metadatas") or []
            companies = sorted({m.get("company") for m in metas if m and m.get("company")})
        except Exception:
            companies = []
        self._companies_cache = companies
        return companies

    def refresh_company_cache(self) -> None:
        """Call this if the Document Agent has indexed new companies since
        this ResearchAgent instance was created."""
        self._companies_cache = None

    # -------------------------------------------------------------- #
    # Step 3: synthesis — grounded, cited, step-by-step
    # -------------------------------------------------------------- #
    def _template_synthesis(self, question: str, steps: List[ResearchStep]) -> str:
        lines = [f"Research question: {question}", ""]
        for i, s in enumerate(steps, 1):
            lines.append(f"Step {i} — {s.sub_question}")
            if s.citations:
                lines.append(f"  Evidence found in {len(s.citations)} source passage(s):")
                for c in s.citations:
                    lines.append(f"    • {c.snippet}")
                    lines.append(f"      Source: {c}")
            else:
                lines.append(f"  {s.findings}")
            lines.append("")
        lines.append("Summary: the findings above are drawn directly from the cited passages "
                      "retrieved from ChromaDB; no figures or claims were added beyond what the "
                      "source documents state.")
        return "\n".join(lines)

    def _build_llm_prompt(self, question: str, steps: List[ResearchStep]) -> str:
        evidence_block = []
        for s in steps:
            evidence_block.append(f"Sub-question: {s.sub_question}")
            for c in s.citations:
                evidence_block.append(f"- Evidence [{c}]: {c.snippet}")
        return (
            "You are a financial research analyst. Using ONLY the evidence below "
            "(never add outside facts), answer the question step by step and cite "
            "sources inline using the bracketed tags exactly as given.\n\n"
            f"Question: {question}\n\nEvidence:\n" + "\n".join(evidence_block)
        )
