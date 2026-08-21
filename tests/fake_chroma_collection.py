from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


def _chunk_text(text: str, target_words: int = 100, overlap: int = 15) -> List[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        piece = words[i:i + target_words]
        if piece:
            chunks.append(" ".join(piece))
        i += target_words - overlap
    return chunks


def _guess_section(chunk_text: str) -> str:
    t = chunk_text.lower()
    if any(k in t for k in ["balance sheet", "total assets", "total liabilities"]):
        return "Balance Sheet"
    if any(k in t for k in ["income statement", "net income", "gross profit", "revenue"]):
        return "Income Statement"
    if any(k in t for k in ["cash flow", "operating activities"]):
        return "Cash Flow Statement"
    if any(k in t for k in ["auditor", "qualified opinion", "going concern", "material weakness"]):
        return "Auditor's Report"
    if any(k in t for k in ["risk factor"]):
        return "Risk Factors"
    if any(k in t for k in ["management discussion", "outlook", "md&a"]):
        return "MD&A"
    return "General"


def _score(query: str, text: str) -> float:
    q_words = set(re.findall(r"[a-z]+", query.lower()))
    t_words = set(re.findall(r"[a-z]+", text.lower()))
    if not q_words:
        return 0.0
    return len(q_words & t_words) / len(q_words)


class FakeChromaCollection:
    def __init__(self):
        self._ids: List[str] = []
        self._docs: List[str] = []
        self._metas: List[Dict[str, Any]] = []

    def add_document(self, path: str, company: str, doc_type: str, period: str = ""):
        p = Path(path)
        if not p.is_file():
            root_cand = Path(__file__).resolve().parent.parent / p.name
            data_cand = Path(__file__).resolve().parent.parent / "data" / p.name
            if root_cand.is_file():
                p = root_cand
            elif data_cand.is_file():
                p = data_cand
        text = p.read_text(encoding="utf-8", errors="ignore")
        text = re.sub(r"\s+", " ", text).strip()
        doc_id = str(uuid.uuid4())[:8]
        for idx, chunk in enumerate(_chunk_text(text)):
            self._ids.append(f"{doc_id}-{idx}")
            self._docs.append(chunk)
            self._metas.append({
                "company": company,
                "doc_type": doc_type,
                "section": _guess_section(chunk),
                "source_file": Path(path).name,
                "period": period,
            })

    def query(self, query_texts: List[str], n_results: int = 4, where: Optional[Dict] = None) -> Dict[str, List[List[Any]]]:
        assert len(query_texts) == 1, "this mock only supports single-query calls"
        q = query_texts[0]
        candidates = list(zip(self._ids, self._docs, self._metas))
        if where:
            candidates = [c for c in candidates if all(c[2].get(k) == v for k, v in where.items())]
        scored = sorted(candidates, key=lambda c: _score(q, c[1]), reverse=True)[:n_results]
        return {
            "ids": [[c[0] for c in scored]],
            "documents": [[c[1] for c in scored]],
            "metadatas": [[c[2] for c in scored]],
            "distances": [[round(1 - _score(q, c[1]), 4) for c in scored]],
        }

    def get(self, include: Optional[List[str]] = None) -> Dict[str, Any]:
        return {"ids": self._ids, "documents": self._docs, "metadatas": self._metas}
