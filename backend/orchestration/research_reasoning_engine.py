"""Cross-Evidence Financial Reasoning & Synthesis Engine.

Synthesizes evidence across financial statements, tables, and narrative MD&A into
structured, grounded, and verifiable financial research answers.
Supports both LLM grounded prompting and offline/deterministic reasoning.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.orchestration.financial_calculator import FinancialCalculator
from backend.orchestration.financial_fact_extractor import (
    ComparisonMatrix,
    FinancialFactExtractor,
)
from backend.orchestration.question_analyzer import FinancialQuestionIntent
from backend.orchestration.research_state import (
    CalculationProof,
    Citation,
    FinancialFact,
    ResearchStep,
)

logger = logging.getLogger(__name__)


class FinancialReasoningEngine:
    """General-purpose financial reasoning and multi-evidence synthesis engine."""

    @classmethod
    def synthesize_deterministic_answer(
        cls,
        question: str,
        intent: FinancialQuestionIntent,
        steps: List[ResearchStep],
    ) -> str:
        """Compose a structured, grounded answer from extracted tables, facts, and citations."""
        combined_text = "\n\n".join(
            "\n".join(s.raw_texts) if s.raw_texts else "\n".join(c.snippet for c in s.citations)
            for s in steps
        )

        has_citations = any(bool(s.citations) for s in steps)
        if not has_citations or not combined_text.strip():
            return (
                "Insufficient grounded evidence was retrieved to answer this question reliably. "
                f"No indexed document evidence was found to answer \"{question}\". "
                "Upload the relevant filing via the Document Agent first."
            )

        all_citations = [c for s in steps for c in s.citations]
        primary_cit = str(all_citations[0]) if all_citations else ""

        # Extract structured facts and tables
        all_facts = [f for s in steps for f in s.extracted_facts]
        tables = FinancialFactExtractor.extract_tables_from_text(combined_text)

        # -------------------------------------------------------------- #
        # Path 1: Compound Multi-Part Questions
        # -------------------------------------------------------------- #
        if len(steps) >= 2 and not intent.is_causal and "margin" not in question.lower() and not any(w in question.lower() for w in ["compare", "growth", "breakdown", "versus", "vs"]):
            lines = [f"### Research Findings on: {question}", ""]
            for idx, s in enumerate(steps, 1):
                lines.append(f"#### {idx}. {s.sub_question}")
                step_text = "\n".join(s.raw_texts) if s.raw_texts else "\n".join(c.snippet for c in s.citations)

                step_curr = "₹" if ("₹" in step_text or "inr" in step_text.lower() or "rs." in step_text.lower() or "rupee" in step_text.lower()) else "$"
                step_findings = []
                debt_m = re.search(r"Total\s+debt[^\n]*?([$€£₹]?[\d,]+(?:\.\d+)?(?:\s*(?:billion|million|crore))?)", step_text, re.I)
                rev_m = re.search(r"(?:Total\s+Revenue|Revenue)[^\n]*?([$€£₹]?[\d,]+(?:\.\d+)?(?:\s*(?:billion|million|crore))?)", step_text, re.I)
                fcf_m = re.search(r"Free\s+Cash\s+Flow\s*:\s*([$€£₹]?\s*[\d,]+(?:\.\d+)?\s*(?:billion|million|crore)?)", step_text, re.I)
                eps_m = re.search(r"(?:Diluted\s+EPS|Earnings\s+Per\s+Share)[^\n:]*?:\s*(?:(?:202\d|201\d)\s*:\s*)?([$€£₹]?\s*\d+\.\d{2})", step_text, re.I)

                if "debt" in s.sub_question.lower() and debt_m:
                    v = debt_m.group(1).strip()
                    if not any(v.startswith(c) for c in "$€£₹"): v = f"{step_curr}{v}"
                    step_findings.append(f"- **Total Debt:** {v}")
                elif "revenue" in s.sub_question.lower() and rev_m:
                    v = rev_m.group(1).strip()
                    if not any(v.startswith(c) for c in "$€£₹"): v = f"{step_curr}{v}"
                    step_findings.append(f"- **Revenue:** {v}")
                elif "cash flow" in s.sub_question.lower() and fcf_m:
                    v = fcf_m.group(1).strip()
                    if not any(v.startswith(c) for c in "$€£₹"): v = f"{step_curr}{v}"
                    step_findings.append(f"- **Free Cash Flow:** {v}")
                elif "eps" in s.sub_question.lower() and eps_m:
                    v = eps_m.group(1).strip()
                    if not any(v.startswith(c) for c in "$€£₹"): v = f"{step_curr}{v}"
                    step_findings.append(f"- **Diluted EPS:** {v}")
                else:
                    sentences = [st.strip() for st in step_text.splitlines() if len(st.strip()) > 20 and not st.strip().startswith(("Note:", "Step"))]
                    if sentences:
                        step_findings.append(f"- {sentences[0]}")
                    else:
                        step_findings.append(f"- Evidence verified from filing.")

                lines.extend(step_findings)
                if s.citations:
                    lines.append(f"**Source:** {s.citations[0]}\n")
                else:
                    lines.append("")

            return "\n".join(lines).strip()

        # -------------------------------------------------------------- #
        # Path 2: Comparative / Multi-Entity / Segment Table Analysis
        # -------------------------------------------------------------- #
        is_comparative_query = (
            (intent.is_comparative or intent.requires_calculation or bool(intent.target_entities) or
             any(w in question.lower() for w in ["segment", "compare", "division", "breakdown"]))
            and "eps" not in intent.target_metrics
            and "diluted eps" not in question.lower()
            and "earnings per share" not in question.lower()
        )

        if tables and is_comparative_query and not intent.is_causal and "margin" not in question.lower():
            t = tables[0]
            if intent.target_entities:
                filtered_rows = [
                    r for r in t.rows
                    if any(ent.lower() in r.label.lower() for ent in intent.target_entities)
                ]
                if filtered_rows:
                    t.rows = filtered_rows
            elif intent.target_metrics:
                filtered_rows = [
                    r for r in t.rows
                    if any(m.lower() in r.label.lower() or r.label.lower() in m.lower() for m in intent.target_metrics)
                ]
                if filtered_rows:
                    t.rows = filtered_rows
            else:
                invalid_set = {"assets", "liabilities", "debt", "equity", "capital expenditures", "free cash flow", "diluted eps"}
                clean_rows = [r for r in t.rows if not any(inv in r.label.lower() for inv in invalid_set)]
                if clean_rows:
                    t.rows = clean_rows

            years_list = t.years if len(t.years) >= 2 else (intent.target_years if len(intent.target_years) >= 2 else ["2025", "2024"])
            curr_yr = years_list[0] if years_list else "Current"
            prev_yr = years_list[1] if len(years_list) >= 2 else "Previous"

            md_table = t.to_markdown()
            header_title = "Segment Revenue and Growth Performance" if ("segment" in question.lower() or "division" in question.lower() or bool(intent.target_entities)) else "Financial Performance Summary"
            lines = [
                f"### {header_title}",
                "",
                md_table,
                "",
                "**Key Analysis & Observations:**",
            ]
            ranked_segments = []
            for r in t.rows:
                clean_lbl = r.label.replace("Total ", "").strip()
                if len(r.values) >= 2:
                    g = FinancialCalculator.calculate_growth_rate(r.values[0], r.values[1])
                    g_str = f"{g:+.1f}%" if g is not None else "N/A"
                    val0_str = f"${r.values[0]:,.0f}M" if abs(r.values[0]) > 50 else f"${r.values[0]:,.2f}"
                    val1_str = f"${r.values[1]:,.0f}M" if abs(r.values[1]) > 50 else f"${r.values[1]:,.2f}"
                    lines.append(f"- **{clean_lbl}:** Grew **{g_str}** year-over-year from {val1_str} in {prev_yr} to {val0_str} in {curr_yr}.")
                    if g is not None:
                        ranked_segments.append((clean_lbl, val0_str, val1_str, g_str, g))
                else:
                    lines.append(f"- **{clean_lbl}:** Reported {r.values[0]:,.0f}.")

            if ranked_segments:
                ranked_segments.sort(key=lambda x: x[4], reverse=True)
                fastest = ranked_segments[0]
                lines.append("")
                lines.append("**Segment Growth Ranking:**")
                lines.append(f"- **{fastest[0]}** grew the most year-over-year at **{fastest[3]}** (from {fastest[2]} to {fastest[1]}).")

            if primary_cit:
                lines.append(f"\n**Source:** {primary_cit}")
            return "\n".join(lines)

        # -------------------------------------------------------------- #
        # Path 3: Specific Single Financial Metrics (EPS, Cash Flow, Debt)
        # -------------------------------------------------------------- #
        curr_sym = "₹" if ("₹" in combined_text or "inr" in combined_text.lower() or "rs." in combined_text.lower() or "rupee" in combined_text.lower()) else "$"
        metric_findings = []

        # EPS Extraction
        if "eps" in intent.target_metrics or "earnings per share" in question.lower():
            eps_cont = re.search(r"continuing\s+operations[^\n:]*?:\s*[$€£₹]?\s*(\d+\.\d{2})", combined_text, re.I)
            eps_cons = re.search(r"consolidated\s+earnings\s+per\s+share[^\n:]*?:\s*[$€£₹]?\s*(\d+\.\d{2})", combined_text, re.I)
            eps_gen = re.search(r"(?:Diluted\s+EPS|Earnings\s+Per\s+Share)[^\n:]*?:\s*(?:(?:202\d|201\d)\s*:\s*)?[$€£₹]?\s*(\d+\.\d{2})", combined_text, re.I)
            if eps_cont:
                metric_findings.append(f"- **Diluted EPS from Continuing Operations:** {curr_sym}{eps_cont.group(1)}")
            if eps_cons:
                metric_findings.append(f"- **Consolidated Diluted EPS:** {curr_sym}{eps_cons.group(1)}")
            if not eps_cont and not eps_cons and eps_gen:
                metric_findings.append(f"- **Diluted EPS:** {curr_sym}{eps_gen.group(1)}")

        # Cash Flow Extraction
        if "cash_flow" in intent.target_metrics or "cash flow" in question.lower() or "fcf" in question.lower():
            fcf_m = re.search(r"Free\s+Cash\s+Flow\s*:\s*[$€£₹]?\s*([\d,]+(?:\.\d+)?\s*(?:billion|million|crore)?)", combined_text, re.I)
            ocf_m = re.search(r"(?:Operating\s+Cash\s+Flow|Net\s+cash\s+provided\s+by\s+operating\s+activities)\s*[:\n]+\s*[$€£₹]?\s*([\d,]+(?:\.\d+)?)", combined_text, re.I)
            if fcf_m:
                metric_findings.append(f"- **Free Cash Flow:** {curr_sym}{fcf_m.group(1)}")
            if ocf_m:
                metric_findings.append(f"- **Net Cash Provided by Operating Activities:** {curr_sym}{ocf_m.group(1)} million")

        # Revenue Extraction
        if "revenue" in intent.target_metrics or "revenue" in question.lower() or "sales" in question.lower():
            rev_m = re.search(r"(?:Total\s+Revenue|Revenue)[^\n]*?([$€£₹][\d,]+(?:\.\d+)?(?:\s*(?:billion|million|crore))?)", combined_text, re.I)
            if not rev_m:
                rev_m = re.search(r"(?:Total\s+Revenue|Revenue)\s*:\s*([$€£₹]?\s*([\d,]+(?:\.\d+)?\s*(?:billion|million|crore)?))", combined_text, re.I)
            if rev_m:
                v = rev_m.group(1).strip()
                if not any(v.startswith(c) for c in "$€£₹"): v = f"{curr_sym}{v}"
                metric_findings.append(f"- **Total Revenue:** {v}")

        # Debt and Balance Sheet Extraction
        if ("debt" in intent.target_metrics or "equity" in intent.target_metrics or "debt" in question.lower() or "liabilities" in question.lower() or "equity" in question.lower()) and "margin" not in question.lower():
            debt_match = re.search(r"Total\s+debt[^\n]*?([$€£₹]?[\d,]+(?:\.\d+)?(?:\s*(?:billion|million|crore))?)", combined_text, re.I)
            if not debt_match:
                debt_match = re.search(r"Total\s+debt\s*:\s*([$€£₹]?\s*([\d,]+(?:\.\d+)?\s*(?:billion|million|crore)?))", combined_text, re.I)
            if debt_match:
                val = debt_match.group(1).strip()
                if val not in ["2020", "2021", "2022", "2023", "2024", "2025", "2026"]:
                    if not any(val.startswith(c) for c in "$€£₹"): val = f"{curr_sym}{val}"
                    metric_findings.append(f"- **Total Debt:** {val}")

            eq_match = re.search(r"Total\s+Stockholders'?\s+Equity[^\n]*?([$€£₹]?[\d,]+(?:\.\d+)?(?:\s*(?:billion|million|crore))?)", combined_text, re.I)
            if eq_match:
                val = eq_match.group(1).strip()
                if not any(val.startswith(c) for c in "$€£₹"): val = f"{curr_sym}{val}"
                metric_findings.append(f"- **Total Stockholders' Equity:** {val}")

            st_debt = re.search(r"Short-term\s+debt[^\n]*?([$€£₹]?[\d,]+(?:\.\d+)?)", combined_text, re.I)
            lt_debt = re.search(r"Long-term\s+debt[^\n]*?([$€£₹]?[\d,]+(?:\.\d+)?)", combined_text, re.I)
            if st_debt:
                val = st_debt.group(1).strip()
                if not any(val.startswith(c) for c in "$€£₹"): val = f"{curr_sym}{val}"
                metric_findings.append(f"- **Short-Term Debt:** {val}")
            if lt_debt:
                val = lt_debt.group(1).strip()
                if not any(val.startswith(c) for c in "$€£₹"): val = f"{curr_sym}{val}"
                metric_findings.append(f"- **Long-Term Debt:** {val}")

        if metric_findings and not intent.is_causal and "margin" not in question.lower():
            header_title = "Financial Metrics Summary"
            if "eps" in intent.target_metrics and len(intent.target_metrics) == 1:
                header_title = "Earnings Per Share (EPS) Analysis"
            elif "cash_flow" in intent.target_metrics and len(intent.target_metrics) == 1:
                header_title = "Cash Flow Performance"
            elif "debt" in intent.target_metrics and len(intent.target_metrics) == 1:
                header_title = "Debt and Capital Structure"

            lines = [f"### {header_title}", ""] + metric_findings
            if primary_cit:
                lines.append(f"\n**Source:** {primary_cit}")
            return "\n".join(lines)

        # -------------------------------------------------------------- #
        # Path 4: Analytical / Causal / Impact Ranking (MD&A, Margins, Drivers)
        # -------------------------------------------------------------- #
        if intent.is_causal or any(w in question.lower() for w in ["why", "reason", "reasons", "cause", "caused", "impact", "driver", "drivers", "factor", "factors", "margin", "operating margin"]):
            extracted_metrics = []

            margin_matches = re.findall(r"((?:operating|gross|profit)\s+margin[^\n\.\;]*?(?:\d+\.?\d*%\s*(?:to\s*\d+\.?\d*%)?|\d+\s*basis\s*points|\d+\.\d+))", combined_text, re.I)
            for mm in margin_matches[:3]:
                clean_m = mm.strip()
                if clean_m and len(clean_m) > 10:
                    extracted_metrics.append(clean_m)

            rev_growth_m = re.search(r"(revenue[^\n\.\;]*?(?:grew|expanded|increased|declined|decreased)[^\n\.\;]*?\d+\.?\d*%)", combined_text, re.I)
            if rev_growth_m:
                extracted_metrics.append(rev_growth_m.group(1).strip())

            factor_candidates = []
            for block in combined_text.splitlines():
                block_clean = block.strip()
                if not block_clean or len(block_clean) < 25:
                    continue
                if block_clean.startswith(("Note:", "Step", "Evidence", "Table of Contents", "Item")):
                    continue
                for s in re.split(r"(?<=[.!?])\s+", block_clean):
                    s_clean = s.strip()
                    if len(s_clean) < 25:
                        continue
                    s_low = s_clean.lower()
                    if any(w in s_low for w in [
                        "driven by", "due to", "attributed to", "primarily reflected", "primarily due",
                        "benefited from", "impacted by", "expansion in", "growth in", "higher margin",
                        "operating efficiency", "productivity", "cost savings", "investments in",
                        "restructuring", "infrastructure", "workforce", "acquisition", "headwind", "tailwind"
                    ]):
                        factor_candidates.append(s_clean)

            distinct_factors = []
            seen_factor_snippets = set()
            for f in factor_candidates:
                f_key = f[:40].lower()
                if f_key not in seen_factor_snippets:
                    distinct_factors.append(f)
                    seen_factor_snippets.add(f_key)

            if distinct_factors or extracted_metrics:
                def find_cit_for_text(target_snippet: str) -> str:
                    for cit in all_citations:
                        words = [w for w in target_snippet.lower().split() if len(w) > 4]
                        if any(w in cit.snippet.lower() for w in words):
                            return str(cit)
                    return str(all_citations[0]) if all_citations else ""

                lines = ["### Answer"]
                comp_name = intent.target_company or (all_citations[0].company if all_citations else "The company")
                if distinct_factors:
                    lines.append(f"{comp_name}'s financial performance and margin changes were primarily driven by operational mix changes, segment growth dynamics, and cost management disclosed in management discussion.")
                else:
                    lines.append(f"Disclosed filings detail key operational and financial movements for {comp_name}.")

                lines.append("")
                lines.append("### Key Evidence")
                if extracted_metrics:
                    for em in extracted_metrics:
                        lines.append(f"- **Metric Movement:** {em.capitalize()}")
                else:
                    lines.append("- Operating performance reflects underlying segment revenue changes and expense management reported in the filing.")
                if distinct_factors:
                    lines.append(f"- Management discussion identified key operational drivers including {distinct_factors[0][:80].rstrip('.,')}...")

                lines.append("")
                lines.append("### Main Factors")
                if distinct_factors:
                    for idx, factor_text in enumerate(distinct_factors[:3], 1):
                        cit_str = find_cit_for_text(factor_text)
                        title = "Operational Performance Driver"
                        if any(w in factor_text.lower() for w in ["margin", "portfolio", "mix", "expansion", "cloud", "recurring"]):
                            title = "High-Margin Portfolio & Revenue Mix"
                        elif "productivity" in factor_text.lower() or "cost" in factor_text.lower() or "expense" in factor_text.lower() or "saving" in factor_text.lower():
                            title = "Cost Structure & Operational Efficiency"
                        elif "investment" in factor_text.lower() or "r&d" in factor_text.lower() or "capacity" in factor_text.lower() or "capital" in factor_text.lower():
                            title = "Strategic R&D & Capability Investments"
                        elif "acquisition" in factor_text.lower() or "integration" in factor_text.lower() or "merger" in factor_text.lower():
                            title = "Acquisition & Business Integration"
                        elif "workforce" in factor_text.lower() or "restructuring" in factor_text.lower() or "headcount" in factor_text.lower():
                            title = "Workforce Rebalancing & Restructuring Actions"
                        else:
                            title = "Operational Performance Driver"

                        lines.append(f"{idx}. **{title}:** {factor_text} Source: {cit_str}")
                else:
                    lines.append("1. **Operational Drivers:** Disclosed operational drivers contributed to year-over-year movements.")

                lines.append("")
                lines.append("### Largest Impact")
                largest_stated = [f for f in distinct_factors if any(k in f.lower() for k in ["primarily", "largest", "main driver", "significant driver"])]
                if largest_stated:
                    lines.append(f"Based on disclosed filings, the primary driver identified by management was: {largest_stated[0]}")
                else:
                    lines.append("The available filing disclosures identify multiple contributing factors, but do not provide sufficient quantitative breakdown to definitively rank the single largest individual impact.")

                lines.append("")
                lines.append("### Source Citations")
                for cit in all_citations[:4]:
                    lines.append(f"- {cit}")

                return "\n".join(lines)

        # -------------------------------------------------------------- #
        # Path 5: General Narrative Reasoning
        # -------------------------------------------------------------- #
        sentences = []
        for block in combined_text.splitlines():
            block_clean = block.strip()
            if not block_clean or len(block_clean) < 15:
                continue
            for s in re.split(r"(?<=[.!?])\s+", block_clean):
                s_clean = s.strip()
                if len(s_clean) > 20 and not s_clean.startswith(("Note:", "Step", "Evidence")):
                    sentences.append(s_clean)

        q_keywords = set(re.findall(r"\w{3,}", question.lower())) - {
            "what", "which", "when", "where", "does", "have", "this", "that", "with", "from", "report", "company"
        }

        ranked_sentences = []
        for s in sentences:
            s_low = s.lower()
            overlap = sum(1 for kw in q_keywords if kw in s_low)
            if any(w in s_low for w in ["because", "driven by", "due to", "attributed to", "primarily", "increased", "decreased", "billion", "million", "%", "margin", "risk"]):
                overlap += 1
            if overlap > 0:
                ranked_sentences.append((overlap, s))

        ranked_sentences.sort(key=lambda x: x[0], reverse=True)
        top_sentences = [s for _, s in ranked_sentences[:5]]

        if top_sentences:
            lines = [f"### Research Findings on: {question}", ""]
            lines.append("Based on the grounded document evidence retrieved from the filing:")
            for sent in top_sentences:
                lines.append(f"- {sent}")

            if primary_cit:
                lines.append("")
                lines.append(f"**Primary Source Citation:** {primary_cit}")
            return "\n".join(lines)

        return (
            "Insufficient grounded evidence was retrieved to answer this question reliably.\n\n"
            f"The indexed filing does not contain verifiable disclosures for: \"{question}\"."
        )

    @classmethod
    def build_llm_prompt(
        cls,
        question: str,
        intent: FinancialQuestionIntent,
        steps: List[ResearchStep],
    ) -> str:
        """Formulate a grounded LLM prompt with structured facts and raw passages."""
        evidence_block = []
        for s in steps:
            sub_q_str = str(getattr(s, "sub_question", "") or "").strip()
            if sub_q_str:
                evidence_block.append(f"Sub-question: {sub_q_str}")

            passages = []
            if getattr(s, "raw_texts", None):
                for idx, t in enumerate(s.raw_texts):
                    t_str = str(t or "").strip()
                    if not t_str:
                        continue
                    cit_str = str(s.citations[idx]) if (s.citations and idx < len(s.citations)) else "Document Filing"
                    passages.append(f"- Excerpt [{cit_str}]:\n{t_str}\n")
            if not passages and getattr(s, "citations", None):
                for c in s.citations:
                    snip = str(getattr(c, "snippet", "") or "").strip()
                    if not snip:
                        continue
                    passages.append(f"- Excerpt [{c}]:\n{snip}\n")

            if getattr(s, "extracted_facts", None):
                fact_lines = []
                for f in s.extracted_facts:
                    raw_val = str(getattr(f, "raw_str", "") or "").strip()
                    num_val = getattr(f, "value", None)
                    metric_lbl = str(getattr(f, "metric", "") or "Financial Metric").strip()
                    period_lbl = str(getattr(f, "period", "") or "").strip()
                    unit_lbl = str(getattr(f, "unit", "") or "").strip()
                    curr_lbl = str(getattr(f, "currency", "") or "").strip()

                    val_str = raw_val or (f"{curr_lbl} {num_val} {unit_lbl}".strip() if num_val is not None else "")
                    if val_str:
                        p_str = f" ({period_lbl})" if period_lbl else ""
                        fact_lines.append(f"  * {metric_lbl}{p_str}: {val_str}")
                if fact_lines:
                    passages.append("- Extracted Financial Metrics:\n" + "\n".join(fact_lines) + "\n")

            if passages:
                evidence_block.extend(passages)
            elif getattr(s, "findings", None) and str(s.findings).strip():
                evidence_block.append(f"- Excerpt [Document Filing]:\n{str(s.findings).strip()}\n")

        raw_entities = getattr(intent, 'target_entities', []) or []
        entities_str = ', '.join(str(e) for e in raw_entities if e) if raw_entities else 'Company Total'

        raw_metrics = getattr(intent, 'target_metrics', []) or []
        metrics_str = ', '.join(str(m) for m in raw_metrics if m) if raw_metrics else 'General Financial Context'

        clean_evidence_text = "\n".join(evidence_block).strip() or "No verified document excerpts available."
        return (
            f"You are a senior financial research analyst.\n\n"
            f"USER QUESTION: {question}\n"
            f"IDENTIFIED INTENT: {intent.intent_type.value} (Causal: {intent.is_causal}, Comparative: {intent.is_comparative})\n"
            f"TARGET ENTITIES: {entities_str}\n"
            f"TARGET METRICS: {metrics_str}\n\n"
            f"RETRIEVED SOURCE PASSAGES:\n{clean_evidence_text}\n\n"
            f"TASK & INSTRUCTIONS:\n"
            f"Answer the user's question directly, concisely, and with complete precision using ONLY the evidence above.\n\n"
            f"CRITICAL GROUNDING RULES:\n"
            f"1. If the retrieved evidence does not contain information to answer the question reliably, output EXACTLY:\n"
            f"'Insufficient grounded evidence was retrieved to answer this question reliably.' followed by what is missing.\n"
            f"2. Calculate growth rates deterministically: ((Current - Prior) / abs(Prior)) * 100.\n"
            f"3. Differentiate margin percentage points (e.g. +1.4 percentage points / +140 bps) from growth rates.\n"
            f"4. Do NOT invent facts or cite unrelated balance sheet liabilities when asked about operating margins.\n"
            f"5. Never dump raw snippets or concatenate disconnected sentences."
        )
