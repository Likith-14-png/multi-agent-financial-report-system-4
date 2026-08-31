"""Metric-Aware Deterministic Financial Calculator.

Performs deterministic mathematical calculations with metric-aware semantics:
- Revenue & Volume Growth: ((Current - Prior) / |Prior|) * 100
- Margin Changes: Current Margin % - Prior Margin % (in percentage points)
- Basis Points: (Current Margin % - Prior Margin %) * 100 bps
- Absolute Variances: Current - Prior
- CAGR: ((End / Start)^(1/n) - 1) * 100
- Ratios & Conversions: Numerator / Denominator
Each calculation generates a verifiable CalculationProof with source tracking.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from backend.orchestration.research_state import CalculationProof, FinancialFact


class FinancialCalculator:
    """Deterministic mathematical calculator for financial metrics with strict semantic awareness."""

    PERCENTAGE_METRIC_KEYWORDS = {
        "margin", "rate", "percentage", "yield", "ratio", "roe", "roa", "roic", "cagr",
        "ebitda margin", "gross margin", "operating margin", "net margin", "tax rate", "retention rate",
    }

    @staticmethod
    def is_percentage_metric(metric_name: str) -> bool:
        """Determine whether a metric is a percentage-based rate or monetary volume."""
        m_low = metric_name.lower().strip()
        return any(kw in m_low for kw in FinancialCalculator.PERCENTAGE_METRIC_KEYWORDS)

    @staticmethod
    def parse_numeric_value(raw: Any) -> Optional[float]:
        """Parse numeric values handling parentheses as negative numbers, suffixes, and currency symbols."""
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            return float(raw)

        clean = str(raw).strip()
        if not clean:
            return None

        # Strip leading/trailing currencies and whitespace outside or inside parens
        is_negative = False
        if clean.startswith("$") or clean.startswith("€") or clean.startswith("£") or clean.startswith("¥") or clean.startswith("₹"):
            clean = clean[1:].strip()
        if clean.startswith("(") and clean.endswith(")"):
            is_negative = True
            clean = clean[1:-1].strip()
        elif clean.startswith("-") or clean.startswith("$-") or clean.startswith("-$"):
            is_negative = True
            clean = clean.replace("$-", "").replace("-$", "").replace("-", "").strip()

        clean = clean.replace("$", "").replace("€", "").replace("£", "").replace("¥", "").replace("₹", "").replace(",", "").replace("%", "").strip()
        if clean.endswith("-"):
            is_negative = True
            clean = clean[:-1].strip()

        # Handle magnitude suffixes
        mult = 1.0
        if clean.lower().endswith("billion") or clean.lower().endswith("bn") or clean.lower().endswith("b"):
            mult = 1000.0 if "m" in clean.lower() else 1.0
            clean = re.sub(r"(?i)\s*(?:billion|bn|b)$", "", clean)
        elif clean.lower().endswith("million") or clean.lower().endswith("m"):
            clean = re.sub(r"(?i)\s*(?:million|m)$", "", clean)
        elif clean.lower().endswith("thousand") or clean.lower().endswith("k"):
            mult = 0.001
            clean = re.sub(r"(?i)\s*(?:thousand|k)$", "", clean)

        try:
            val = float(clean) * mult
            return -val if is_negative else val
        except ValueError:
            return None

    @staticmethod
    def calculate_growth_rate(curr: float, prev: float) -> Optional[float]:
        """Calculate percentage growth: ((curr - prev) / abs(prev)) * 100."""
        if prev == 0:
            return None
        return ((curr - prev) / abs(prev)) * 100.0

    @staticmethod
    def calculate_percentage_point_change(curr_pct: float, prev_pct: float) -> float:
        """Calculate change in percentage points: curr_pct - prev_pct."""
        return curr_pct - prev_pct

    @staticmethod
    def calculate_basis_point_change(curr_pct: float, prev_pct: float) -> float:
        """Calculate change in basis points: (curr_pct - prev_pct) * 100.0."""
        return (curr_pct - prev_pct) * 100.0

    @staticmethod
    def calculate_absolute_change(curr: float, prev: float) -> float:
        """Calculate absolute difference: curr - prev."""
        return curr - prev

    @staticmethod
    def calculate_cagr(start_val: float, end_val: float, num_periods: int) -> Optional[float]:
        """Calculate Compound Annual Growth Rate: ((end / start) ** (1 / n) - 1) * 100."""
        if start_val <= 0 or end_val <= 0 or num_periods <= 0:
            return None
        return ((end_val / start_val) ** (1.0 / num_periods) - 1.0) * 100.0

    @staticmethod
    def calculate_margin(numerator: float, denominator: float) -> Optional[float]:
        """Calculate margin percentage: (numerator / denominator) * 100."""
        if denominator == 0:
            return None
        return (numerator / denominator) * 100.0

    @staticmethod
    def calculate_ratio(val_a: float, val_b: float) -> Optional[float]:
        """Calculate simple ratio: val_a / val_b."""
        if val_b == 0:
            return None
        return val_a / val_b

    @staticmethod
    def verify_reported_vs_calculated(calculated: float, reported: float, tolerance: float = 0.5) -> Tuple[bool, str]:
        """Verify if reported growth/margin matches calculated value within tolerance."""
        diff = abs(calculated - reported)
        if diff <= tolerance:
            return True, f"Calculated value ({calculated:.2f}%) matches reported disclosure ({reported:.2f}%)."
        return False, f"Variance detected: Calculated {calculated:.2f}% vs Reported {reported:.2f}% (difference: {diff:.2f}%)."

    @classmethod
    def compute_metric_change_proof(
        cls,
        metric_name: str,
        entity: str,
        curr_val: float,
        prev_val: float,
        curr_period: str = "2025",
        prev_period: str = "2024",
        source_chunk_ids: Optional[List[str]] = None,
        pages: Optional[List[Any]] = None,
        unit: str = "millions",
    ) -> CalculationProof:
        """Metric-aware calculation generator producing an exact audit trail and formatted result."""
        is_pct = cls.is_percentage_metric(metric_name)
        chunks = source_chunk_ids or []
        page_list = pages or []

        if is_pct:
            # Margin / Rate metric: Calculate percentage points and basis points
            pp_change = cls.calculate_percentage_point_change(curr_val, prev_val)
            bps_change = cls.calculate_basis_point_change(curr_val, prev_val)
            direction = "expanded" if pp_change >= 0 else "contracted"
            sign = "+" if pp_change >= 0 else ""
            res_formatted = f"{direction} {abs(bps_change):.0f} basis points ({sign}{pp_change:.2f} percentage points)"
            formula = f"{curr_val:.2f}% - {prev_val:.2f}% = {sign}{pp_change:.2f} percentage points ({sign}{bps_change:.0f} bps)"
            calc_type = "margin_percentage_points"
            res_val = pp_change
        else:
            # Volume / Currency metric: Calculate percentage growth and absolute variance
            growth = cls.calculate_growth_rate(curr_val, prev_val)
            variance = cls.calculate_absolute_change(curr_val, prev_val)
            sign = "+" if (growth is not None and growth >= 0) else ""
            g_str = f"{sign}{growth:.1f}%" if growth is not None else "N/A"
            v_sign = "+" if variance >= 0 else ""
            res_formatted = f"{g_str} ({v_sign}${variance:,.0f} {unit})" if abs(variance) >= 10 else f"{g_str} ({v_sign}${variance:,.2f})"
            formula = f"(({curr_val:,.2f} - {prev_val:,.2f}) / |{prev_val:,.2f}|) * 100 = {g_str}"
            calc_type = "growth_rate"
            res_val = growth if growth is not None else variance

        return CalculationProof(
            calculation_type=calc_type,
            metric_name=metric_name,
            entity=entity,
            period_current=curr_period,
            period_prior=prev_period,
            val_current=curr_val,
            val_prior=prev_val,
            result_val=res_val,
            result_formatted=res_formatted,
            formula_description=formula,
            source_chunk_ids=chunks,
            pages=page_list,
        )

    @staticmethod
    def rank_entities_by_growth(
        facts_by_entity: Dict[str, Dict[str, float]],
        year_curr: str = "2025",
        year_prev: str = "2024",
    ) -> List[Tuple[str, float, float, float]]:
        """Compute growth and return sorted list of (entity, curr_val, prev_val, growth_rate) descending."""
        results = []
        for ent, years_map in facts_by_entity.items():
            if year_curr in years_map and year_prev in years_map:
                c_val = years_map[year_curr]
                p_val = years_map[year_prev]
                g = FinancialCalculator.calculate_growth_rate(c_val, p_val)
                if g is not None:
                    results.append((ent, c_val, p_val, g))
        results.sort(key=lambda x: x[3], reverse=True)
        return results


# Module-level convenience functions for backward compatibility
calculate_growth_rate = FinancialCalculator.calculate_growth_rate
calculate_margin = FinancialCalculator.calculate_margin
calculate_percentage_point_change = FinancialCalculator.calculate_percentage_point_change
calculate_basis_point_change = FinancialCalculator.calculate_basis_point_change
calculate_absolute_change = FinancialCalculator.calculate_absolute_change
calculate_cagr = FinancialCalculator.calculate_cagr
calculate_ratio = FinancialCalculator.calculate_ratio
parse_numeric_value = FinancialCalculator.parse_numeric_value
verify_reported_vs_calculated = FinancialCalculator.verify_reported_vs_calculated
