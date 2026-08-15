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
(built by the Document Agent) and never creates or writes to the
collection itself. That's the integration point between agents: whoever
calls ResearchAgent(...) just needs to hand it the shared collection.

------------------------------------------------------------------------
METADATA CONTRACT (canonical + backwards-compatible fields)
------------------------------------------------------------------------
The canonical metadata contract used by the Document Agent is:

    {
        "analysis_id": str,
        "document_id": str,
        "company_name": str,   # canonical field used by the workflow
        "report_year": str | int,
        "report_type": str,
        "section_title": str,
        "source": str,
        "chunk_id": str,
    }

For backwards compatibility, ResearchAgent continues to support legacy keys
that many older fixtures still emit:

    {
        "company": str,
        "doc_type": str,
        "section": str,
        "source_file": str,
        "period": str,
    }

These legacy fields are treated as aliases, not as the primary contract.
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
        best_by_chunk: Dict[str, Citation] = {}
        for step in self.steps:
            for c in step.citations:
                key = str(c.chunk_id or "").strip()
                if not key:
                    key = (c.company, c.doc_type, c.section, c.snippet)
                    if key in best_by_chunk:
                        continue
                    best_by_chunk[str(key)] = c
                    continue
                existing = best_by_chunk.get(key)
                if existing is None:
                    best_by_chunk[key] = c
                    continue
                current_score = c.score if isinstance(c.score, (int, float)) else None
                existing_score = existing.score if isinstance(existing.score, (int, float)) else None
                if current_score is not None and (existing_score is None or current_score > existing_score):
                    best_by_chunk[key] = c
        return list(best_by_chunk.values())


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

    @staticmethod
    def _infer_section_from_text(text: Optional[str]) -> Optional[str]:
        if not isinstance(text, str) or not text.strip():
            return None
        patterns = [
            (r"(?im)^\s*(?:\d+[.)]\s*)?Management Discussion and Analysis\b", "Management Discussion and Analysis"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Liquidity and Capital Resources\b", "Liquidity and Capital Resources"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Risk Factors\b", "Risk Factors"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Balance Sheet\b", "Balance Sheet"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Income Statement\b", "Income Statement"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Cash Flow Statement\b", "Cash Flow Statement"),
            (r"(?im)^\s*(?:\d+[.)]\s*)?Notes to the Financial Statements\b", "Notes to the Financial Statements"),
        ]
        for pattern, title in patterns:
            if re.search(pattern, text):
                return title
        return None

    @staticmethod
    def _normalize_company_name(value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        text = re.sub(r"\s+", " ", text)
        return text.casefold()

    @staticmethod
    def _is_missing_metadata_value(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned == "":
                return True
            lowered = cleaned.lower()
            return lowered in {"unknown", "n/a", "na", "not available", "unavailable", "none", "null"}
        return False

    @staticmethod
    def _metadata_value(metadata: Optional[Dict[str, Any]], *keys: str) -> Any:
        if not isinstance(metadata, dict):
            return None
        for key in keys:
            value = metadata.get(key)
            if not ResearchAgent._is_missing_metadata_value(value):
                return value
        return None

    @classmethod
    def _matches_company_name(cls, target_company: Optional[str], metadata: Optional[Dict[str, Any]]) -> bool:
        if not target_company:
            return True
        target_norm = cls._normalize_company_name(target_company)
        if not target_norm:
            return True
        candidates = [
            cls._metadata_value(metadata, "company_name"),
            cls._metadata_value(metadata, "company"),
        ]
        for candidate in candidates:
            if cls._normalize_company_name(candidate) == target_norm:
                return True
        return False

    @staticmethod
    def _rows_from_query_results(results: Optional[Dict[str, Any]]) -> List[tuple[str, str, Dict[str, Any], Optional[float]]]:
        if not results:
            return []
        ids = (results.get("ids") or [[]])[0]
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[None] * len(ids)])[0]
        rows: List[tuple[str, str, Dict[str, Any], Optional[float]]] = []
        for cid, doc_text, meta, dist in zip(ids, docs, metas, dists):
            rows.append((str(cid), doc_text or "", meta or {}, dist))
        return rows

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

        best_by_chunk: Dict[str, Citation] = {}
        for step in steps:
            for citation in step.citations:
                chunk_key = str(citation.chunk_id or "").strip()
                if not chunk_key:
                    continue
                existing = best_by_chunk.get(chunk_key)
                if existing is None:
                    best_by_chunk[chunk_key] = citation
                    continue
                current_score = citation.score if isinstance(citation.score, (int, float)) else None
                existing_score = existing.score if isinstance(existing.score, (int, float)) else None
                if current_score is not None and (existing_score is None or current_score > existing_score):
                    best_by_chunk[chunk_key] = citation

        for step in steps:
            step.citations = [citation for citation in step.citations if str(citation.chunk_id or "").strip() in best_by_chunk and best_by_chunk[str(citation.chunk_id or "").strip()] is citation]

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
        rows: List[tuple[str, str, Dict[str, Any], Optional[float]]] = []

        if target_company and self.collection is not None:
            for where in ({"company_name": target_company}, {"company": target_company}):
                try:
                    results = self.collection.query(query_texts=[sub_q], n_results=top_k, where=where)
                except Exception:
                    results = None
                candidate_rows = self._rows_from_query_results(results)
                if candidate_rows:
                    rows = candidate_rows
                    break
            if not rows:
                try:
                    results = self.collection.query(query_texts=[sub_q], n_results=top_k)
                except Exception as exc:
                    return ResearchStep(sub_question=sub_q,
                                         findings=f"Retrieval failed ({exc}). "
                                                  f"Check that the ChromaDB collection is reachable.")
                rows = self._rows_from_query_results(results)
                rows = [r for r in rows if self._matches_company_name(target_company, r[2])]
        else:
            try:
                results = self.collection.query(query_texts=[sub_q], n_results=top_k) if self.collection is not None else None
            except Exception as exc:
                return ResearchStep(sub_question=sub_q,
                                     findings=f"Retrieval failed ({exc}). "
                                              f"Check that the ChromaDB collection is reachable.")
            rows = self._rows_from_query_results(results)

        if not rows:
            return ResearchStep(
                sub_question=sub_q,
                findings="No indexed documents contain evidence for this. "
                         "Upload the relevant filing via the Document Agent first.",
                citations=[],
            )

        citations: List[Citation] = []
        evidence_lines: List[str] = []
        seen_chunk_ids: Dict[str, Citation] = {}
        for cid, doc_text, meta, dist in rows:
            meta = meta or {}
            snippet = (doc_text or "")[:220] + ("…" if doc_text and len(doc_text) > 220 else "")
            company_name = self._metadata_value(meta, "company_name", "company") or "unknown"
            doc_type = self._metadata_value(meta, "doc_type", "report_type") or "unknown"
            section = self._metadata_value(meta, "section_title", "section")
            if self._is_missing_metadata_value(section):
                inferred_section = self._infer_section_from_text(doc_text)
                section = inferred_section or "Unknown"

            if section == "Unknown" and not self._infer_section_from_text(doc_text):
                continue

            source_file = self._metadata_value(meta, "source_file", "source") or "unknown"
            chunk_id = self._metadata_value(meta, "chunk_id") or str(cid)
            cit = Citation(
                company=str(company_name),
                doc_type=str(doc_type),
                section=str(section),
                source_file=str(source_file),
                chunk_id=str(chunk_id),
                snippet=snippet,
                score=dist,
            )

            existing = seen_chunk_ids.get(str(chunk_id))
            if existing is None:
                seen_chunk_ids[str(chunk_id)] = cit
                continue

            current_score = float(cit.score) if isinstance(cit.score, (int, float)) else None
            existing_score = float(existing.score) if isinstance(existing.score, (int, float)) else None
            if current_score is not None and (existing_score is None or current_score > existing_score):
                seen_chunk_ids[str(chunk_id)] = cit

        citations = list(seen_chunk_ids.values())
        for cit in citations:
            evidence_lines.append(f"  - \"{cit.snippet}\"  {cit}")

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
            companies = []
            for m in metas:
                if not isinstance(m, dict):
                    continue
                candidate = self._metadata_value(m, "company_name", "company")
                if candidate:
                    companies.append(str(candidate))
            companies = sorted(set(companies), key=lambda s: s.casefold())
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
