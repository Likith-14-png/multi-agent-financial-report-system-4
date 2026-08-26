"""
Evidence Validator
Validates every important claim before synthesis per Master Requirements §21

11-point validation checklist:
1. Correct document?
2. Correct company?
3. Correct year?
4. Correct metric?
5. Correct value?
6. Correct currency?
7. Correct unit?
8. Correct page?
9. Correct chunk?
10. Evidence actually supports claim?
11. No negation error?
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ValidationResult:
    """Result of validating a single claim."""
    valid: bool
    claim: str
    issues: List[str]
    evidence_sentence: Optional[str] = None
    confidence: float = 0.0
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "claim": self.claim,
            "issues": self.issues,
            "evidence_sentence": self.evidence_sentence,
            "confidence": self.confidence,
            "metadata": self.metadata or {},
        }


class EvidenceValidator:
    """
    Validates financial claims against source evidence.

    Used after Research Synthesis to catch hallucinations or misattributions
    before publishing to Report Agent.
    """

    def __init__(self):
        pass

    def validate_financial_value(
        self,
        claim: Dict[str, Any],
        source_evidence: Dict[str, Any],
        document_metadata: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate a single financial value claim against source evidence.

        Args:
            claim: {"metric": "Revenue", "value": 520, "currency": "USD", "year": "2025", "unit": "million"}
            source_evidence: {"snippet": "...", "source_file": "...", "page": ..., "chunk_id": "...", "company": "..."}
            document_metadata: {"company_name": "ABC", "report_year": "2025", ...}

        Returns:
            ValidationResult with validity status and specific issues
        """
        issues: List[str] = []
        confidence = 1.0
        evidence_sentence = source_evidence.get("snippet", "")
        metadata = document_metadata or {}

        # 1. Correct document?
        claim_company = claim.get("company", "").strip()
        metadata_company = metadata.get("company_name", "").strip()
        evidence_company = source_evidence.get("company", "").strip()

        if claim_company and metadata_company and claim_company.lower() != metadata_company.lower():
            issues.append(f"Company mismatch: claim '{claim_company}' vs metadata '{metadata_company}'")
            confidence -= 0.3

        # 2. Correct company in evidence?
        if evidence_company and claim_company and evidence_company.lower() != claim_company.lower():
            issues.append(f"Evidence company mismatch: claim '{claim_company}' vs evidence '{evidence_company}'")
            confidence -= 0.2

        # 3. Correct year?
        claim_year = str(claim.get("year", "")).strip()
        metadata_year = str(metadata.get("report_year", "")).strip()
        if claim_year and metadata_year and claim_year != metadata_year:
            issues.append(f"Year mismatch: claim '{claim_year}' vs metadata '{metadata_year}'")
            confidence -= 0.25

        # 4. Correct metric?
        claim_metric = claim.get("metric", "").strip().lower()
        evidence_text = evidence_sentence.lower()
        if claim_metric and claim_metric not in evidence_text:
            issues.append(f"Metric '{claim_metric}' not found in evidence snippet")
            confidence -= 0.2

        # 5. Correct value?
        claim_value = claim.get("value")
        if claim_value is not None:
            value_str = str(claim_value)
            # Try to find the value in evidence (with some tolerance for formatting)
            if not self._value_in_evidence(value_str, evidence_text):
                issues.append(f"Value '{value_str}' not found in evidence snippet")
                confidence -= 0.3

        # 6. Correct currency?
        claim_currency = claim.get("currency", "").strip()
        if claim_currency:
            currency_symbols = self._get_currency_symbols(claim_currency)
            currency_found = any(sym in evidence_text for sym in currency_symbols)
            if not currency_found and claim_currency not in evidence_text:
                issues.append(f"Currency '{claim_currency}' not explicitly mentioned in evidence")
                confidence -= 0.15

        # 7. Correct unit?
        claim_unit = claim.get("unit", "").strip().lower()
        if claim_unit and claim_unit not in ("", "none"):
            unit_variants = self._get_unit_variants(claim_unit)
            unit_found = any(variant in evidence_text for variant in unit_variants)
            if not unit_found:
                issues.append(f"Unit '{claim_unit}' not found in evidence")
                confidence -= 0.15

        # 8. Correct page?
        claim_page = claim.get("page")
        metadata_page = source_evidence.get("page")
        if claim_page is not None and metadata_page is not None:
            if str(claim_page).strip() != str(metadata_page).strip():
                issues.append(f"Page mismatch: claim page {claim_page} vs evidence page {metadata_page}")
                confidence -= 0.1

        # 9. Correct chunk?
        claim_chunk = claim.get("chunk_id", "").strip()
        evidence_chunk = source_evidence.get("chunk_id", "").strip()
        if claim_chunk and evidence_chunk and claim_chunk != evidence_chunk:
            issues.append(f"Chunk ID mismatch: claim '{claim_chunk}' vs evidence '{evidence_chunk}'")
            confidence -= 0.1

        # 10. Evidence actually supports claim?
        if not evidence_sentence or not evidence_sentence.strip():
            issues.append("No evidence snippet provided")
            confidence -= 0.4
        elif len(evidence_sentence.strip()) < 20:
            issues.append(f"Evidence snippet too brief: '{evidence_sentence}'")
            confidence -= 0.2

        # 11. No negation error?
        if self._has_negation_error(evidence_text, claim_metric):
            issues.append(f"Evidence contains negation of '{claim_metric}' (e.g., 'no', 'not', 'did not', 'was not')")
            confidence -= 0.5

        # Determine validity
        confidence = max(0.0, confidence)
        is_valid = confidence >= 0.6 and len(issues) == 0

        return ValidationResult(
            valid=is_valid,
            claim=str(claim),
            issues=issues,
            evidence_sentence=evidence_sentence,
            confidence=confidence,
            metadata={
                "company": claim_company or metadata_company or evidence_company,
                "year": claim_year or metadata_year,
                "metric": claim_metric,
            },
        )

    def validate_research_answer(
        self,
        answer: str,
        citations: List[Dict[str, Any]],
        question: str,
        document_metadata: Optional[Dict[str, Any]] = None,
    ) -> ValidationResult:
        """
        Validate research answer has proper evidence support.

        Args:
            answer: The synthesized answer text
            citations: List of citation dicts with {"snippet": "...", "source_file": "...", etc}
            question: The original question
            document_metadata: Metadata about the document

        Returns:
            ValidationResult indicating whether answer is well-grounded
        """
        issues: List[str] = []
        confidence = 1.0

        # Check citations exist
        if not citations:
            issues.append("No citations provided for research answer")
            confidence -= 0.5

        # Check evidence snippets are not empty
        empty_snippets = sum(1 for c in citations if not (c.get("snippet", "").strip()))
        if empty_snippets > 0:
            issues.append(f"{empty_snippets} citation(s) have empty snippets")
            confidence -= 0.1 * empty_snippets

        # Check answer references key concepts from question
        question_terms = set(word.lower() for word in question.split() if len(word) > 3)
        answer_lower = answer.lower()
        matching_terms = sum(1 for term in question_terms if term in answer_lower)
        if matching_terms == 0:
            issues.append("Answer does not reference key terms from the question")
            confidence -= 0.3

        # Check answer is not claiming insufficient evidence when citations exist
        has_evidence = any(c.get("snippet", "").strip() for c in citations)
        insufficient_text = "insufficient grounded evidence" in answer_lower
        if insufficient_text and has_evidence:
            issues.append("Answer claims insufficient evidence but citations are provided")
            confidence -= 0.4

        # Check metadata consistency
        if document_metadata:
            company = document_metadata.get("company_name", "").lower()
            if company and company not in answer_lower:
                issues.append(f"Answer does not mention document company '{company}'")
                confidence -= 0.15

        confidence = max(0.0, confidence)
        is_valid = confidence >= 0.6

        return ValidationResult(
            valid=is_valid,
            claim=answer[:100] + ("..." if len(answer) > 100 else ""),
            issues=issues,
            evidence_sentence=f"{len(citations)} citations provided",
            confidence=confidence,
        )

    @staticmethod
    def _value_in_evidence(value_str: str, evidence_text: str) -> bool:
        """Check if a value appears in evidence (handles formatting variants)."""
        # Remove formatting and search
        clean_value = value_str.replace(",", "").strip()
        if clean_value in evidence_text.replace(",", ""):
            return True

        # Try as integer if possible
        try:
            val_int = int(float(value_str))
            if str(val_int) in evidence_text:
                return True
        except (ValueError, TypeError):
            pass

        # Try as float
        try:
            val_float = float(value_str)
            if str(val_float) in evidence_text:
                return True
            # Also try with 1-2 decimal places
            for decimals in [1, 2]:
                if f"{val_float:.{decimals}f}" in evidence_text:
                    return True
        except (ValueError, TypeError):
            pass

        return False

    @staticmethod
    def _get_currency_symbols(currency_code: str) -> List[str]:
        """Get common symbols and codes for a currency."""
        symbols = {
            "USD": ["$", "USD"],
            "INR": ["₹", "INR", "Rs"],
            "EUR": ["€", "EUR"],
            "GBP": ["£", "GBP"],
            "JPY": ["¥", "JPY"],
            "CNY": ["¥", "CNY"],
        }
        return symbols.get(currency_code.upper(), [currency_code])

    @staticmethod
    def _get_unit_variants(unit: str) -> List[str]:
        """Get variants of a unit name."""
        unit_lower = unit.lower().strip()
        variants = {
            "million": ["million", "m", "mn", "(in millions)", "(in million)"],
            "billion": ["billion", "b", "bn"],
            "crore": ["crore", "cr"],
            "lakh": ["lakh", "l"],
            "thousand": ["thousand", "k", "ths"],
            "percent": ["percent", "%", "percentage"],
            "per_share": ["per share", "per-share", "eps", "diluted", "basic"],
            "basis_points": ["basis points", "bps"],
        }
        return variants.get(unit_lower, [unit_lower])

    @staticmethod
    def _has_negation_error(evidence_text: str, metric: str) -> bool:
        """Check if evidence contains negation of the metric."""
        if not metric or not evidence_text:
            return False

        metric_lower = metric.lower().strip()
        text_lower = evidence_text.lower()

        # Find negation patterns
        negation_patterns = [
            rf"(?:no|not|did not|was not|is not|has not|have not|without)\s+(?:.*?\s)?{re.escape(metric_lower)}",
            rf"(?:no|not|did not|was not|is not)\s+.*?{re.escape(metric_lower)}",
            rf"{re.escape(metric_lower)}\s+(?:was not|is not|has not|did not|were not)",
        ]

        for pattern in negation_patterns:
            if re.search(pattern, text_lower):
                return True

        return False
