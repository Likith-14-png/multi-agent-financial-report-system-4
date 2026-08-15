from __future__ import annotations

import json
import re
from typing import Any, Dict, List


class OfflineAnalyzer:
    """Generate a deterministic red-flag analysis from retrieved document chunks."""

    def analyze(self, prompt: str, context_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        combined_text = "\n".join(chunk.get("document", "") for chunk in context_chunks if chunk.get("document"))
        lowered = combined_text.lower()

        flags: List[Dict[str, Any]] = []
        if re.search(r"(declin|drop|fell|down|reduced)", lowered):
            flags.append(
                {
                    "category": "performance",
                    "severity": "High",
                    "title": "Revenue or profitability decline",
                    "description": "The retrieved evidence mentions a decline in financial performance.",
                    "reason": "Declining indicators should be treated as a material risk signal.",
                    "evidence": combined_text[:240],
                    "page": None,
                    "recommendation": "Review management commentary and cash flow drivers in detail.",
                    "confidence": 0.82,
                }
            )
        if re.search(r"(borrow|debt|liability|leverag)", lowered):
            flags.append(
                {
                    "category": "capital_structure",
                    "severity": "Medium",
                    "title": "Rising leverage or debt burden",
                    "description": "The evidence references borrowings, debt, or higher liabilities.",
                    "reason": "Higher leverage can increase refinancing and solvency risk.",
                    "evidence": combined_text[:240],
                    "page": None,
                    "recommendation": "Assess debt maturity and covenant headroom.",
                    "confidence": 0.78,
                }
            )
        if re.search(r"(cash flow|liquidity|working capital)", lowered):
            flags.append(
                {
                    "category": "liquidity",
                    "severity": "Medium",
                    "title": "Liquidity pressure",
                    "description": "The evidence mentions cash flow or liquidity concerns.",
                    "reason": "Weak liquidity can impair the ability to fund operations.",
                    "evidence": combined_text[:240],
                    "page": None,
                    "recommendation": "Inspect operating cash flow and near-term obligations.",
                    "confidence": 0.75,
                }
            )
        if not flags:
            flags.append(
                {
                    "category": "general",
                    "severity": "Low",
                    "title": "No clear red flag detected",
                    "description": "The retrieved evidence did not contain explicit risk signals.",
                    "reason": "The offline analyzer is conservative when no clear risk indicators are present.",
                    "evidence": combined_text[:240],
                    "page": None,
                    "recommendation": "Review the source material for additional context.",
                    "confidence": 0.6,
                }
            )

        overall_risk = "High" if any(flag["severity"] == "High" for flag in flags) else "Medium" if len(flags) > 1 else "Low"
        return {
            "overall_risk": overall_risk,
            "total_flags": len(flags),
            "flags": flags,
            "execution_time": 0.0,
            "model_used": "offline-fallback",
        }
