from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


class OfflineAnalyzer:
    """Generate a deterministic red-flag analysis from retrieved document chunks."""

    _RISK_RULES = [
        {
            "category": "Debt",
            "title": "Debt increase",
            "severity": "Medium",
            "description": "Debt or leverage increased materially in the filing.",
            "reason": "Elevated debt can pressure refinancing, covenant headroom, and future financial flexibility.",
            "recommendation": "Review debt maturity, covenant headroom, and financing plans.",
            "patterns": [
                r"\b(?:total debt|borrowings?|debt|leverage|net debt)\b[^.!?]{0,120}\b(?:increas(?:e|ed|ing)|rose|higher|rising|up|climb(?:ed)?)\b",
                r"\b(?:total debt|borrowings?|debt|leverage|net debt)\b[^.!?]{0,40}\b(?:is|was|remains?)\s+(?:higher|elevated|rising)\b",
                r"\b(?:higher|elevated|rising)\s+(?:total\s+)?(?:debt|borrowings?|leverage|net debt)\b",
                r"\b(?:total debt|borrowings?|debt|leverage|net debt)\b[^.!?]{0,120}\$\s*[\d,]+(?:\.\d+)?\s*(?:million|billion|bn|m)"
            ],
            "negations": [
                r"\b(?:no|not|never|none|without)\b[^.!?]{0,80}\b(?:debt|borrowings?|leverage|liability)\b",
                r"\b(?:no|not|never|none)\b[^.!?]{0,80}\b(?:increase|rise|growth|higher)\b[^.!?]{0,80}\b(?:debt|borrowings?|leverage)\b",
            ],
        },
        {
            "category": "Profitability",
            "title": "Margin decline",
            "severity": "High",
            "description": "Operating or profit margins declined versus the prior period.",
            "reason": "Margin deterioration can signal cost inflation, revenue pressure, or weak operating leverage.",
            "recommendation": "Review the underlying cost structure and pricing trends.",
            "patterns": [
                r"\b(?:gross margin|operating margin|net margin|profit margin)\b[^.!?]{0,120}\b(?:declin(?:e|ed|ing)|fell|drop(?:ped)?|reduc(?:e|ed|tion)|down|lower)\b",
                r"\b(?:margin)\b[^.!?]{0,80}\b(?:declin(?:e|ed|ing)|fell|drop(?:ped)?|reduc(?:e|ed|tion)|down|lower)\b",
            ],
            "negations": [
                r"\b(?:no|not|never|none)\b[^.!?]{0,80}\b(?:margin|profitability)\b[^.!?]{0,80}\b(?:declin(?:e|ed|ing)|fell|drop(?:ped)?|reduc(?:e|ed|tion))\b",
            ],
        },
        {
            "category": "Cash Flow",
            "title": "Cash-flow decline",
            "severity": "High",
            "description": "Operating or free cash flow weakened materially.",
            "reason": "Reduced cash generation can limit reinvestment and debt service capacity.",
            "recommendation": "Review operating cash flow conversion and working capital dynamics.",
            "patterns": [
                r"\b(?:operating cash flow|free cash flow|cash flow)\b[^.!?]{0,120}\b(?:declin(?:e|ed|ing)|fell|drop(?:ped)?|down|reduc(?:e|ed|tion)|negative|weakened)\b",
                r"\b(?:cash flow)\b[^.!?]{0,80}\$\s*[\d,]+(?:\.\d+)?\s*(?:million|billion|bn|m)"
            ],
            "negations": [
                r"\b(?:no|not|never|none)\b[^.!?]{0,80}\b(?:cash flow|liquidity)\b[^.!?]{0,80}\b(?:declin(?:e|ed|ing)|fell|drop(?:ped)?|pressure|negative)\b",
            ],
        },
        {
            "category": "Liquidity",
            "title": "Liquidity risk",
            "severity": "Medium",
            "description": "The filing indicates liquidity or working capital pressure.",
            "reason": "Liquidity pressure can impair the company’s ability to meet obligations and fund operations.",
            "recommendation": "Assess current liquidity, covenant headroom, and near-term obligations.",
            "patterns": [
                r"\b(?:liquidity|working capital|current ratio|cash position)\b[^.!?]{0,120}\b(?:pressure|strain|declin(?:e|ed|ing)|fell|drop(?:ped)?|tight|shortfall)\b",
                r"\b(?:working capital|cash)\b[^.!?]{0,120}\b(?:declin(?:e|ed|ing)|fell|drop(?:ped)?|negative|shortfall)\b",
            ],
            "negations": [
                r"\b(?:no|not|never|none)\b[^.!?]{0,80}\b(?:liquidity|working capital|cash)\b[^.!?]{0,80}\b(?:pressure|strain|declin(?:e|ed|ing)|shortfall)\b",
            ],
        },
        {
            "category": "Accounting",
            "title": "Accounting risk",
            "severity": "High",
            "description": "The filing discloses accounting or internal-control issues.",
            "reason": "Accounting weaknesses can impair earnings quality and increase restatement risk.",
            "recommendation": "Review management’s accounting judgment, controls, and MD&A disclosures.",
            "patterns": [
                r"\b(?:material weakness|restat(?:ement|ements)|revenue recognition|accounting policy|internal control)\b",
                r"\b(?:accounting)\b[^.!?]{0,120}\b(?:change|issue|weakness|restat(?:ement|ements)|concern)\b",
            ],
            "negations": [
                r"\b(?:no|not|never|none)\b[^.!?]{0,80}\b(?:material weakness|restat(?:ement|ements)|accounting issue|internal control|revenue recognition)\b",
            ],
        },
        {
            "category": "Legal",
            "title": "Legal risk",
            "severity": "High",
            "description": "The filing discloses litigation, regulatory, or legal exposure.",
            "reason": "Legal or regulatory issues can affect cash flows, reputation, and compliance exposure.",
            "recommendation": "Assess the legal exposure, expected outcomes, and reserves.",
            "patterns": [
                r"\b(?:litigation|regulatory|government investigation|penalty|class action|lawsuit|antitrust|trade dispute)\b",
                r"\b(?:legal)\b[^.!?]{0,100}\b(?:proceeding|matter|claim|investigation|penalty)\b",
            ],
            "negations": [
                r"\b(?:no|not|never|none)\b[^.!?]{0,80}\b(?:litigation|regulatory|government investigation|penalty|lawsuit|claim)\b",
            ],
        },
        {
            "category": "Revenue",
            "title": "Customer concentration",
            "severity": "Medium",
            "description": "The filing indicates customer concentration or revenue concentration risk.",
            "reason": "A highly concentrated customer base can increase sales volatility and counterparty risk.",
            "recommendation": "Review customer concentration and diversification trends.",
            "patterns": [
                r"\b(?:customer concentration|concentrated customer|top customer|significant customer|single customer)\b",
                r"\b(?:customer)\b[^.!?]{0,120}\b(?:concentrat(?:ion|ed)|dependenc(?:e|y))\b",
            ],
            "negations": [
                r"\b(?:no|not|never|none)\b[^.!?]{0,80}\b(?:customer concentration|concentrated customer|single customer)\b",
            ],
        },
        {
            "category": "Market",
            "title": "Currency or FX risk",
            "severity": "Medium",
            "description": "The filing discloses foreign-exchange or currency volatility risk.",
            "reason": "Currency swings can affect reported earnings and operating cash flows.",
            "recommendation": "Assess foreign currency exposure and hedging strategies.",
            "patterns": [
                r"\b(?:currency|foreign exchange|fx|exchange rate)\b[^.!?]{0,120}\b(?:volatility|fluctuation|risk|headwind|depreciat(?:ion|ion))\b",
                r"\b(?:currency)\b[^.!?]{0,80}\b(?:risk|volatility|headwind)\b",
            ],
            "negations": [
                r"\b(?:no|not|never|none)\b[^.!?]{0,80}\b(?:currency|foreign exchange|fx|exchange rate)\b[^.!?]{0,80}\b(?:risk|volatility)\b",
            ],
        },
        {
            "category": "Market",
            "title": "Interest-rate risk",
            "severity": "Medium",
            "description": "The filing discloses interest-rate sensitivity or rising-rate risk.",
            "reason": "Higher rates can raise borrowing costs and compress earnings.",
            "recommendation": "Assess rate sensitivity, hedging, and refinancing exposures.",
            "patterns": [
                r"\b(?:interest rate|rates)\b[^.!?]{0,120}\b(?:increase|higher|rising|volatility|risk|pressure)\b",
                r"\b(?:floating-rate|variable-rate|rate sensitivity)\b",
            ],
            "negations": [
                r"\b(?:no|not|never|none)\b[^.!?]{0,80}\b(?:interest rate|rates)\b[^.!?]{0,80}\b(?:risk|pressure|increase|higher)\b",
            ],
        },
    ]

    def analyze(self, prompt: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not context_chunks:
            return {
                "overall_risk": "Low",
                "total_flags": 0,
                "flags": [],
                "execution_time": 0.0,
                "model_used": "offline-fallback",
            }

        sentences = self._extract_sentences(context_chunks)
        if not sentences:
            return {
                "overall_risk": "Low",
                "total_flags": 0,
                "flags": [],
                "execution_time": 0.0,
                "model_used": "offline-fallback",
            }

        flags: List[Dict[str, Any]] = []
        flag_by_identity: Dict[Tuple[str, str, str], Tuple[Dict[str, Any], float]] = {}
        for rule in self._RISK_RULES:
            for sentence, metadata in sentences:
                if self._sentence_has_negation(sentence, rule["patterns"], rule["negations"]):
                    continue
                if self._sentence_has_nil_or_missing_value(sentence):
                    continue
                matched = any(re.search(pattern, sentence, flags=re.I) for pattern in rule["patterns"])
                if matched and self._is_valid_risk_evidence(rule, sentence) and not self._is_generic_risk_phrase(rule, sentence):
                    source_page = self._resolve_page(metadata)
                    confidence = self._calculate_confidence(rule, sentence, metadata)
                    evidence_strength = self._evidence_strength(rule, sentence, metadata)
                    flag = {
                        "category": rule["category"],
                        "severity": self._calculate_severity(confidence, rule["severity"]),
                        "title": rule["title"],
                        "description": rule["description"],
                        "reason": rule["reason"],
                        "evidence": sentence[:500],
                        "page": source_page,
                        "source_file": self._resolve_source_file(metadata),
                        "source_chunk": self._resolve_source_chunk(metadata),
                        "recommendation": rule["recommendation"],
                        "confidence": confidence,
                    }
                    identity = (rule["category"], rule["title"], self._risk_source_context(metadata))
                    existing = flag_by_identity.get(identity)
                    if existing is None or evidence_strength > existing[1]:
                        flag_by_identity[identity] = (flag, evidence_strength)

        flags = [flag for flag, _ in flag_by_identity.values()]

        if not flags:
            return {
                "overall_risk": "Low",
                "total_flags": 0,
                "flags": [],
                "execution_time": 0.0,
                "model_used": "offline-fallback",
            }

        overall_risk = self._overall_risk(flags)
        return {
            "overall_risk": overall_risk,
            "total_flags": len(flags),
            "flags": flags,
            "execution_time": 0.0,
            "model_used": "offline-fallback",
        }

    @staticmethod
    def _resolve_page(metadata: Any) -> Optional[int]:
        """Resolve the first valid page from direct and nested provenance metadata."""
        if not isinstance(metadata, dict):
            return None
        containers = [metadata]
        for key in ("provenance", "source_metadata", "source"):
            nested = metadata.get(key)
            if isinstance(nested, dict):
                containers.append(nested)
        for field in ("page_number", "source_page", "page_start", "page"):
            for container in containers:
                value = container.get(field)
                if isinstance(value, bool) or value is None:
                    continue
                try:
                    page = float(str(value).strip())
                except (TypeError, ValueError):
                    continue
                if page > 0 and page.is_integer():
                    return int(page)
        return None

    @staticmethod
    def _resolve_source_file(metadata: Any) -> Optional[str]:
        if not isinstance(metadata, dict):
            return None
        containers = [metadata]
        for key in ("provenance", "source_metadata", "source"):
            nested = metadata.get(key)
            if isinstance(nested, dict):
                containers.append(nested)
        for container in containers:
            for field in ("source_file", "source"):
                value = container.get(field)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @staticmethod
    def _resolve_source_chunk(metadata: Any) -> Optional[str]:
        if not isinstance(metadata, dict):
            return None
        containers = [metadata]
        for key in ("provenance", "source_metadata", "source"):
            nested = metadata.get(key)
            if isinstance(nested, dict):
                containers.append(nested)
        for container in containers:
            for field in ("chunk_id", "source_chunk_id", "chunk"):
                value = container.get(field)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return None

    @staticmethod
    def _risk_source_context(metadata: Any) -> str:
        if not isinstance(metadata, dict):
            return ""
        for key in ("section_title", "section", "source_type"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.casefold().strip()
        for key in ("provenance", "source_metadata", "source"):
            nested = metadata.get(key)
            if isinstance(nested, dict):
                for field in ("section_title", "section", "source_type"):
                    value = nested.get(field)
                    if isinstance(value, str) and value.strip():
                        return value.casefold().strip()
        return ""

    @staticmethod
    def _is_valid_risk_evidence(rule: Dict[str, Any], sentence: str) -> bool:
        lowered = sentence.casefold()
        word_count = len(re.findall(r"\b\w+\b", lowered))
        if word_count < 4 and rule["category"] != "Debt":
            return False
        explicit_risk = re.search(
            r"\b(?:risk|pressure|exposure|volatile|volatility|material weakness|restatement|litigation|lawsuit|investigation|penalty|declin(?:e|ed|ing)|fell|drop(?:ped)?|reduc(?:e|ed|tion)|increas(?:e|ed|ing)|rose|higher|rising|negative|shortfall|strain|concentrat(?:ed|ion)|dependenc(?:e|y))\b",
            lowered,
        )
        if not explicit_risk:
            return False
        category = rule["category"]
        if category == "Accounting":
            return bool(re.search(r"material weakness|restatement|internal control|accounting (?:issue|concern)|revenue recognition.{0,60}(?:issue|concern|risk|change)", lowered))
        if category == "Legal":
            return bool(re.search(r"(?:litigation|lawsuit|investigation|penalty|regulatory).{0,100}(?:exposure|risk|claim|proceeding|material|significant|pending|settlement)", lowered))
        if category == "Market":
            return bool(re.search(r"(?:currency|foreign exchange|fx|interest rate|rates).{0,100}(?:risk|volatility|exposure|sensitivity|headwind|pressure|fluctuation)", lowered))
        return True

    @staticmethod
    def _is_generic_risk_phrase(rule: Dict[str, Any], sentence: str) -> bool:
        """Reject a rule label or keyword fragment without source evidence."""
        normalized = re.sub(r"[^a-z0-9]+", " ", sentence.casefold()).strip()
        title = re.sub(r"[^a-z0-9]+", " ", rule["title"].casefold()).strip()
        if normalized == title:
            return True
        generic_terms = {
            "risk", "risks", "increase", "increased", "decline", "declined",
            "concentration", "concentrated", "exposure", "issue", "issues",
        }
        words = normalized.split()
        title_words = set(title.split())
        return len(words) <= 4 and set(words).issubset(title_words | generic_terms)

    @staticmethod
    def _evidence_strength(rule: Dict[str, Any], sentence: str, metadata: Any) -> float:
        lowered = sentence.casefold()
        score = 0.25
        if re.search(r"[$€£₹¥]\s*[\d,]+|\b\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?\s*(?:million|billion|crore|bn|m)\b", lowered):
            score += 0.35
        if re.search(r"\b(?:from|to|versus|compared with|compared to|prior year|previous year|year-over-year|fy\s*\d{2,4})\b", lowered):
            score += 0.2
        if re.search(r"\b(?:material|significant|severe|substantial|major|identified|disclosed|exposed|pressure|drivers?|cause|caused|due to|because)\b", lowered):
            score += 0.2
        if re.search(r"\b(?:declin(?:e|ed|ing)|fell|drop(?:ped)?|reduc(?:e|ed|tion)|increas(?:e|ed|ing)|rose|higher|rising|negative|shortfall|weakened)\b", lowered):
            score += 0.2
        if re.search(r"\b(?:identified|disclosed|reported|exposed|may affect|could affect|unable to|failed|drivers?)\b", lowered):
            score += 0.1
        if OfflineAnalyzer._resolve_page(metadata) is not None or OfflineAnalyzer._resolve_source_chunk(metadata):
            score += 0.05
        return min(score, 1.0)

    @classmethod
    def _calculate_confidence(cls, rule: Dict[str, Any], sentence: str, metadata: Any) -> float:
        return round(cls._evidence_strength(rule, sentence, metadata), 2)

    @staticmethod
    def _calculate_severity(confidence: float, default: str) -> str:
        if confidence >= 0.95:
            return "Critical"
        if confidence >= 0.75:
            return "High"
        if confidence >= 0.55:
            return "Medium"
        return "Low"

    @staticmethod
    def _extract_sentences(context_chunks: List[Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
        sentences: List[Tuple[str, Dict[str, Any]]] = []
        for chunk in context_chunks:
            if not isinstance(chunk, dict):
                continue
            text = chunk.get("document") or ""
            if not text:
                continue
            metadata = chunk.get("metadata") or {}
            for sentence in re.split(r"(?<=[.!?])\s+|\n+", str(text)):
                clean = sentence.strip()
                if not clean or len(clean) < 12:
                    continue
                sentences.append((clean, metadata))
        return sentences

    @staticmethod
    def _sentence_has_nil_or_missing_value(sentence: str) -> bool:
        lowered = sentence.lower()
        nil_patterns = [
            r"\bnil\b", r"\bn/?a\b", r"\bnot available\b", r"\bnot disclosed\b",
            r"\bnone\b", r"\bzero\b", r"(?<![\d.])0(?:\.0+)?%\b",
            r"\bno value\b", r"\bn\.a\.\b",
        ]
        return any(re.search(pattern, lowered) for pattern in nil_patterns) and not any(token in lowered for token in ["noted", "cited", "reported", "indicated", "disclose", "disclosed"])

    @staticmethod
    def _sentence_has_negation(sentence: str, patterns: List[str], negations: List[str]) -> bool:
        lowered = sentence.lower()
        for neg in negations:
            if re.search(neg, sentence, flags=re.I):
                return True
        if any(token in lowered for token in ["no material risk", "no risk", "no material weakness", "no litigation", "no debt increase", "no margin decline", "no cash flow decline", "does not indicate", "was not", "were not"]) and any(re.search(p, sentence, flags=re.I) for p in patterns):
            return True
        return False

    @staticmethod
    def _overall_risk(flags: List[Dict[str, Any]]) -> str:
        severities = [flag.get("severity", "Low") for flag in flags]
        if any(sev == "Critical" for sev in severities):
            return "Critical"
        if any(sev == "High" for sev in severities):
            return "High"
        if any(sev == "Medium" for sev in severities):
            return "Medium"
        return "Low"
