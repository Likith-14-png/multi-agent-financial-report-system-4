from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from compare import ComparisonResult


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
    def _metric_records_from_extraction(extraction: Dict[str, Any], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        metric_names = [
            ("Revenue", "revenue"),
            ("Operating Income", "operating_income"),
            ("Net Income", "net_income"),
            ("Total Assets", "total_assets"),
            ("Total Liabilities", "total_liabilities"),
            ("Cash Flow", "cash_flow"),
            ("EPS", "eps"),
        ]

        records: List[Dict[str, Any]] = []
        metrics = extraction.get("metrics") if isinstance(extraction, dict) and isinstance(extraction.get("metrics"), list) else []
        if metrics:
            for metric in metrics:
                if not isinstance(metric, dict):
                    continue
                name = metric.get("metric") or metric.get("name")
                if not name:
                    continue
                records.append({
                    "metric": name,
                    "value": metric.get("value") or metric.get("amount") or metric.get("current_value"),
                    "unit": metric.get("unit") or "unitless",
                    "year": metric.get("year") or metric.get("report_year") or metadata.get("report_year"),
                    "source": metric.get("source") or extraction.get("source"),
                    "chunk_id": metric.get("chunk_id") or extraction.get("chunk_id") or metadata.get("chunk_id"),
                    "source_chunks": metric.get("source_chunks") or ([extraction.get("chunk_id")] if extraction.get("chunk_id") else []),
                })
            return records

        for metric_label, key_name in metric_names:
            value = extraction.get(key_name)
            if value is None and metric_label.lower().replace(" ", "_") in extraction:
                value = extraction.get(metric_label.lower().replace(" ", "_"))
            if value is None:
                continue
            records.append({
                "metric": metric_label,
                "value": value,
                "unit": ReportAgent._extract_unit_from_value(value),
                "year": extraction.get("report_year") or metadata.get("report_year"),
                "source": extraction.get("source"),
                "chunk_id": extraction.get("chunk_id") or metadata.get("chunk_id"),
                "source_chunks": [extraction.get("chunk_id")] if extraction.get("chunk_id") else [],
            })
        return records

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
                "source_chunks": source_chunks,
            })
        return findings or [{"finding": "No research findings provided.", "evidence": "No evidence available.", "source_chunks": []}]

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
            recommendation = item.get("recommendation") or item.get("title") or item.get("description")
            if recommendation:
                recommendations.append(str(recommendation))
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
            extraction_snapshot[key] = metric["value"]

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
                    f"{item['metric']}={item.get('value')}" for item in financial_metrics[:4]
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

        if not recommendations and risk_assessment.get("flags"):
            report["recommendations"] = [
                str(flag.get("recommendation") or flag.get("title") or flag.get("description") or "Review the risk item with source evidence.")
                for flag in risk_assessment.get("flags", [])
                if isinstance(flag, dict)
            ]

        return report
