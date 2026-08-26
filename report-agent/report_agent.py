from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from compare import ComparisonResult
from formatter import format_financial_value


class ReportAgent:
    """Aggregate verified upstream outputs into the canonical final report."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def _as_metadata_dict(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not metadata:
            return {}
        return {
            "analysis_id": metadata.get("analysis_id"),
            "document_id": metadata.get("document_id"),
            "company_name": metadata.get("company_name"),
            "report_year": metadata.get("report_year"),
            "chunk_id": metadata.get("chunk_id"),
        }

    @staticmethod
    def _normalize_metric_value(value: Any) -> Any:
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip()
        if not text or text.lower() in {"n/a", "na", "not available", "unavailable", "none", "null"}:
            return None
        return text


    @staticmethod
    def _is_valid_metric_value(record: Dict[str, Any]) -> bool:
        """Check if a metric record has a displayable value (not a raw dict without numeric data)."""
        value = record.get("value")
        if value is None or value == "":
            return False
        if isinstance(value, dict):
            # Only allow dicts that have been processed into display_value (has actual content)
            # Reject raw structural dicts like {'numeric_value': 42, 'unit_multiplier': 1}
            if value.get("display_value"):
                return True
            return False
        return True

    @staticmethod
    def _metric_records_from_extraction(extraction: Dict[str, Any], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        metrics = extraction.get("metrics") if isinstance(extraction, dict) and isinstance(extraction.get("metrics"), list) else []
        if metrics:
            for metric in metrics:
                if not isinstance(metric, dict):
                    continue
                name = metric.get("metric") or metric.get("name")
                if not name:
                    continue
                display_value = metric.get("display_value")
                records.append({

                    "metric": name,
                    "value": display_value if display_value is not None else next((metric.get(key) for key in ("value", "amount", "current_value") if metric.get(key) is not None), None),
                    "unit": metric.get("unit") or metric.get("unit_scale") or "unitless",
                    "currency": metric.get("currency"),
                    "year": metric.get("year") or metric.get("report_year") or metadata.get("report_year"),
                    "source": metric.get("source") or extraction.get("source"),
                    "source_page": metric.get("source_page") or metric.get("page"),
                    "evidence": metric.get("evidence"),
                    "chunk_id": metric.get("chunk_id") or extraction.get("chunk_id") or metadata.get("chunk_id"),
                    "source_chunks": metric.get("source_chunks") or ([extraction.get("chunk_id")] if extraction.get("chunk_id") else []),
                })
            return [r for r in records if ReportAgent._is_valid_metric_value(r)]

        financial_values = extraction.get("financial_values") if isinstance(extraction.get("financial_values"), dict) else {}
        candidates = list(financial_values.items())
        excluded = {"metrics", "financial_values", "company_name", "report_year", "analysis_id", "document_id", "source", "source_file", "source_text", "chunk_id", "source_chunks", "status", "error", "yearly_metrics", "segment_metrics", "accounting_information", "risk_related_metrics", "income_statement", "balance_sheet", "cash_flow_statement", "observations", "detailed_metrics", "traceability", "financial_value_conflicts", "cash_reconciliation"}
        candidates.extend((key, value) for key, value in extraction.items() if key not in financial_values and key not in excluded)
        seen: set[str] = set()
        for key_name, value in candidates:
            if key_name in seen or value is None or value == "":
                continue
            seen.add(key_name)
            metric_label = str(key_name).replace("_", " ").title()
            value_dict = value if isinstance(value, dict) else {}
            display_value = value_dict.get("display_value")
            records.append({
                "metric": metric_label,
                "value": display_value if display_value is not None else value,
                "unit": value_dict.get("unit") or value_dict.get("unit_scale") or ReportAgent._extract_unit_from_value(value),
                "currency": value_dict.get("currency"),
                "year": value_dict.get("period") or extraction.get("report_year") or metadata.get("report_year"),
                "source": value_dict.get("source_file") or extraction.get("source"),
                "source_page": value_dict.get("source_page"),
                "evidence": value_dict.get("evidence"),
                "chunk_id": value_dict.get("source_chunk") or extraction.get("chunk_id") or metadata.get("chunk_id"),
                "source_chunks": [value_dict.get("source_chunk")] if value_dict.get("source_chunk") else ([extraction.get("chunk_id")] if extraction.get("chunk_id") else []),
            })
        return [r for r in records if ReportAgent._is_valid_metric_value(r)]

    @staticmethod
    def _numerical_metric_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return value
        text = str(value).strip()
        if not text or text.lower() in {"n/a", "na", "not available", "unavailable", "none", "null"}:
            return None
        return text

    @staticmethod
    def _extract_unit_from_value(value: Any) -> str:
        """Extract unit from a value string like '$15.3 billion'."""
        if value is None or value == "":
            return "unitless"
        text = str(value).strip().lower()
        if "billion" in text:
            return "billion"
        elif "million" in text:
            return "million"
        elif "thousand" in text:
            return "thousand"
        elif "%" in text:
            return "percent"
        return "unitless"

    @staticmethod
    def _comparison_payload(comparison: Any) -> ComparisonResult:
        if isinstance(comparison, dict):
            records = comparison.get("records") or comparison.get("rows") or comparison.get("data") or []
            payload = {
                "comparison_type": comparison.get("comparison_type") or "single_year",
                "records": list(records),
                "summary": comparison.get("summary") or {},
                "metadata": comparison.get("metadata") or {},
            }
            return ComparisonResult(payload)
        if hasattr(comparison, "to_dict"):
            rows = comparison.to_dict(orient="records")
            return ComparisonResult({"comparison_type": "year_over_year", "records": rows, "summary": {}})
        if isinstance(comparison, list):
            return ComparisonResult({"comparison_type": "single_year", "records": comparison, "summary": {}})
        return ComparisonResult({"comparison_type": "single_year", "records": [], "summary": {}})

    @staticmethod
    def _normalize_source_chunks(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        elif not isinstance(value, list):
            value = list(value) if isinstance(value, tuple) else [value]
        cleaned: List[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                cleaned.append(text)
        return list(dict.fromkeys(cleaned))

    @staticmethod
    def _research_findings(research: Dict[str, Any]) -> List[Dict[str, Any]]:
        answer = research.get("answer") or ""
        sources = research.get("sources") or research.get("evidence") or []
        findings: List[Dict[str, Any]] = []
        answer_source_chunks = ReportAgent._normalize_source_chunks(research.get("source_chunks"))
        if answer:
            findings.append({
                "finding": answer,
                "evidence": answer,
                "source_chunks": answer_source_chunks,
            })
        for source in sources:
            if not isinstance(source, dict):
                continue
            snippet = source.get("snippet") or source.get("section") or source.get("source_file") or "Evidence available."
            source_chunks = ReportAgent._normalize_source_chunks(source.get("source_chunks"))
            if not source_chunks and source.get("chunk_id"):
                source_chunks = [str(source.get("chunk_id"))]
            findings.append({
                "finding": answer or snippet,
                "evidence": snippet,
                "source": source.get("source_file") or source.get("source"),
                "source_page": source.get("source_page") or source.get("page"),
                "citation": source.get("citation"),
                "source_chunks": source_chunks,
            })
        return findings

    @staticmethod
    def _risk_assessment(red_flags: Dict[str, Any]) -> Dict[str, Any]:
        flags = red_flags.get("flags") if isinstance(red_flags, dict) else []
        if not isinstance(flags, list):
            flags = []
        risk_assessment = {
            "overall_risk": red_flags.get("overall_risk") if isinstance(red_flags, dict) else "Low",
            "total_flags": int(red_flags.get("total_flags", len(flags))) if isinstance(red_flags, dict) else len(flags),
            "flags": flags,
            "model_used": red_flags.get("model_used") if isinstance(red_flags, dict) else None,
            "execution_time": red_flags.get("execution_time") if isinstance(red_flags, dict) else None,
        }
        return risk_assessment

    @staticmethod
    def _recommendations(red_flags: Dict[str, Any]) -> List[str]:
        flags = red_flags.get("flags") if isinstance(red_flags, dict) else []
        if not isinstance(flags, list):
            flags = []
        recommendations: List[str] = []
        for item in flags:
            if not isinstance(item, dict):
                continue
            recommendation = item.get("recommendation")
            if recommendation:
                text = str(recommendation)
                if text not in recommendations:
                    recommendations.append(text)
        if recommendations:
            return recommendations
        return []

    @staticmethod
    def _evidence(research: Dict[str, Any], red_flags: Dict[str, Any]) -> List[Dict[str, Any]]:
        evidence: List[Dict[str, Any]] = []
        sources = research.get("sources") or research.get("evidence") or []
        for source in sources:
            if not isinstance(source, dict):
                continue
            item = {
                "source": source.get("source_file") or source.get("section") or "source",
                "snippet": source.get("snippet") or source.get("section") or "No snippet available.",
                "chunk_id": source.get("chunk_id"),
            }
            evidence.append(item)
        for flag in (red_flags.get("flags") or []):
            if isinstance(flag, dict):
                snippet = flag.get("description") or flag.get("title") or "No description provided."
                evidence_item = {
                    "source": flag.get("category") or "red_flag",
                    "snippet": snippet,
                    "chunk_id": None,
                }
                evidence_value = flag.get("evidence")
                if evidence_value is not None:
                    if isinstance(evidence_value, str):
                        if evidence_value.strip() != snippet.strip():
                            evidence_item["evidence"] = evidence_value
                    else:
                        evidence_item["evidence"] = evidence_value
                evidence.append(evidence_item)
        return evidence

    def generate(
        self,
        analysis: Optional[Dict[str, Any]] = None,
        extraction: Optional[Dict[str, Any]] = None,
        research: Optional[Dict[str, Any]] = None,
        red_flags: Optional[Dict[str, Any]] = None,
        comparison: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if analysis is not None and isinstance(analysis, dict):
            metadata = analysis.get("metadata") or metadata or {}
            extraction = analysis.get("extraction") or extraction or {}
            research = analysis.get("research") or research or {}
            red_flags = analysis.get("red_flags") or red_flags or {}
            comparison = analysis.get("comparison") if "comparison" in analysis else comparison

        metadata = metadata or {}
        extraction = extraction or {}
        research = research or {}
        red_flags = red_flags or {}
        comparison = comparison if comparison is not None else {}

        metadata_dict = self._as_metadata_dict(metadata)
        analysis_id = metadata_dict.get("analysis_id")
        document_id = metadata_dict.get("document_id")
        company_name = metadata_dict.get("company_name") or extraction.get("company_name") or "Unknown Company"
        report_year = metadata_dict.get("report_year")
        try:
            if report_year is not None and str(report_year).strip() not in {"", "None"}:
                report_year = int(report_year)
        except (TypeError, ValueError):
            report_year = metadata.get("report_year") if isinstance(metadata, dict) else None

        financial_metrics = self._metric_records_from_extraction(extraction, metadata_dict)
        extraction_snapshot = {
            "company_name": company_name,
            "report_year": report_year,
            "source": extraction.get("source") if isinstance(extraction, dict) else None,
            "chunk_id": extraction.get("chunk_id") if isinstance(extraction, dict) else metadata_dict.get("chunk_id"),
            "revenue": None,
            "operating_income": None,
            "net_income": None,
            "total_assets": None,
            "total_liabilities": None,
            "cash_flow": None,
        }
        for metric in financial_metrics:
            key = metric["metric"].lower().replace(" ", "_")
            value = metric.get("value")
            if isinstance(value, dict):
                value = value.get("display_value") if value.get("display_value") is not None else value.get("value")
            extraction_snapshot[key] = value

        comparison_payload = self._comparison_payload(comparison)
        risk_assessment = self._risk_assessment(red_flags)
        research_findings = self._research_findings(research)
        evidence = self._evidence(research, red_flags)
        recommendations = self._recommendations(red_flags)
        research_evidence = research.get("evidence") if isinstance(research, dict) else []
        if not research_evidence and isinstance(research, dict):
            research_evidence = research.get("sources") or []

        if analysis_id and document_id and company_name and report_year is not None:
            report_status = "complete" if financial_metrics or extraction else "partial"
            if not extraction and not comparison and not research and not red_flags:
                report_status = "failed"
        else:
            report_status = "failed"

        if (not research) or (not red_flags) or (not comparison):
            report_status = "partial" if report_status == "complete" else report_status

        if not financial_metrics and not extraction:
            report_status = "partial" if report_status != "failed" else "failed"

        summary_bits = [
            f"{company_name} ({report_year}) financial report summary.",
        ]
        if financial_metrics:
            summary_bits.append(
                "; ".join(
                    f"{item['metric']}={format_financial_value(item, item.get('metric'))}" for item in financial_metrics[:4]
                )
            )
        if research_findings:
            summary_bits.append(f"Research finding: {research_findings[0]['finding']}")
        if risk_assessment.get("flags"):
            summary_bits.append(f"Risk profile: {risk_assessment.get('overall_risk')} with {risk_assessment.get('total_flags')} flagged items.")
        if comparison_payload.get("records"):
            summary_bits.append(f"Comparison: {len(comparison_payload['records'])} comparison records preserved from upstream output.")
        executive_summary = " ".join(summary_bits)

        report = {
            "metadata": {
                "analysis_id": analysis_id,
                "document_id": document_id,
                "company_name": company_name,
                "report_year": report_year,
                "chunk_id": metadata_dict.get("chunk_id"),
            },
            "analysis_id": analysis_id,
            "document_id": document_id,
            "company_name": company_name,
            "report_year": report_year,
            "executive_summary": executive_summary,
            "financial_metrics": financial_metrics,
            "research_findings": research_findings,
            "risk_assessment": risk_assessment,
            "comparison": comparison_payload,
            "evidence": evidence,
            "recommendations": recommendations,
            "report_status": report_status,
            "extraction": extraction_snapshot,
            "research": {
                "answer": research.get("answer") if isinstance(research, dict) else "",
                "sources": research.get("sources") if isinstance(research, dict) else [],
                "evidence": research_evidence,
            },
            "red_flags": risk_assessment,
            "metadata_trace": {
                "analysis_id": analysis_id,
                "document_id": document_id,
                "company_name": company_name,
                "report_year": report_year,
            },
        }

        return report
