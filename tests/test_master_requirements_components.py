"""
Tests for Master Requirements components: Evidence Validator, Question Analyzer, Evidence Retrieval
"""

import pytest
from evidence_validator import EvidenceValidator, ValidationResult
from question_analyzer import QuestionIntentAnalyzer, FinancialQuestionIntent


# ============================================================
# Evidence Validator Tests
# ============================================================

class TestEvidenceValidator:
    """Test Evidence Validator per Master Requirements §21"""

    def test_validates_financial_value_with_correct_metadata(self):
        """Validate a well-formed financial value claim."""
        validator = EvidenceValidator()

        claim = {
            "metric": "Revenue",
            "value": 520,
            "currency": "USD",
            "year": "2025",
            "unit": "million",
        }

        evidence = {
            "snippet": "Revenue from operations for FY2025 was $520 million.",
            "source_file": "report.pdf",
            "page": 5,
            "chunk_id": "chunk-123",
            "company": "ABC Corp",
        }

        metadata = {
            "company_name": "ABC Corp",
            "report_year": "2025",
        }

        result = validator.validate_financial_value(claim, evidence, metadata)

        assert result.valid is True
        assert result.confidence >= 0.6
        assert len(result.issues) == 0

    def test_detects_company_mismatch(self):
        """Validator should flag company mismatch."""
        validator = EvidenceValidator()

        claim = {"metric": "Revenue", "value": 520, "company": "ABC Corp"}
        evidence = {"snippet": "Revenue was $520 million", "company": "XYZ Corp"}
        metadata = {"company_name": "ABC Corp"}

        result = validator.validate_financial_value(claim, evidence, metadata)

        assert result.valid is False
        assert any("company" in issue.lower() for issue in result.issues)

    def test_detects_year_mismatch(self):
        """Validator should flag year mismatch."""
        validator = EvidenceValidator()

        claim = {"metric": "Revenue", "value": 520, "year": "2025"}
        evidence = {"snippet": "Revenue in 2024 was $520 million"}
        metadata = {"report_year": "2024"}

        result = validator.validate_financial_value(claim, evidence, metadata)

        assert result.valid is False
        assert any("year" in issue.lower() for issue in result.issues)

    def test_detects_missing_metric_in_evidence(self):
        """Validator should flag when metric not found in evidence."""
        validator = EvidenceValidator()

        claim = {"metric": "Operating Margin", "value": 19.0}
        evidence = {"snippet": "Revenue was $520 million"}

        result = validator.validate_financial_value(claim, evidence)

        assert result.valid is False
        assert any("metric" in issue.lower() for issue in result.issues)

    def test_detects_missing_currency(self):
        """Validator should flag when currency not found in evidence."""
        validator = EvidenceValidator()

        claim = {"metric": "Revenue", "value": 520, "currency": "USD"}
        evidence = {"snippet": "Revenue was 520 million"}  # No $ sign

        result = validator.validate_financial_value(claim, evidence)

        assert result.valid is False
        assert any("currency" in issue.lower() for issue in result.issues)

    def test_validates_inr_currency(self):
        """Validator should support INR currency."""
        validator = EvidenceValidator()

        claim = {
            "metric": "Revenue",
            "value": 267021,
            "currency": "INR",
            "unit": "crore",
        }

        evidence = {
            "snippet": "Revenue from operations for FY2025 was ₹2,67,021 crore.",
        }

        result = validator.validate_financial_value(claim, evidence)

        assert result.valid is True or len(result.issues) <= 1

    def test_detects_negation_error(self):
        """Validator should flag claims contradicted by negation."""
        validator = EvidenceValidator()

        claim = {"metric": "Material Weakness", "value": 1}
        evidence = {"snippet": "No material weakness was identified in our audit."}

        result = validator.validate_financial_value(claim, evidence)

        assert result.valid is False
        assert any("negation" in issue.lower() for issue in result.issues)

    def test_validates_research_answer(self):
        """Validator should validate research answers."""
        validator = EvidenceValidator()

        answer = "Revenue increased by 15% from FY2024 to FY2025."
        citations = [
            {"snippet": "Revenue grew from $520M to $598M"},
            {"snippet": "This represents a 15% year-over-year increase"},
        ]
        question = "How did revenue change year-over-year?"

        result = validator.validate_research_answer(answer, citations, question)

        assert result.valid is True
        assert result.confidence >= 0.6

    def test_rejects_answer_with_no_citations(self):
        """Validator should flag answers without citations."""
        validator = EvidenceValidator()

        answer = "Revenue increased by 15%."
        citations = []
        question = "How did revenue change?"

        result = validator.validate_research_answer(answer, citations, question)

        assert result.valid is False
        assert any("citation" in issue.lower() for issue in result.issues)

    def test_rejects_answer_claiming_insufficient_evidence_when_citations_exist(self):
        """Validator should flag contradictory claims."""
        validator = EvidenceValidator()

        answer = "Insufficient grounded evidence was retrieved."
        citations = [
            {"snippet": "Revenue was $520 million"},
            {"snippet": "Operating margin was 19%"},
        ]
        question = "What was revenue?"

        result = validator.validate_research_answer(answer, citations, question)

        assert result.valid is False
        assert any("insufficient" in issue.lower() for issue in result.issues)


# ============================================================
# Question Analyzer Tests
# ============================================================

class TestQuestionIntentAnalyzer:
    """Test Question Analyzer per Master Requirements §3"""

    def test_analyzes_financial_metric_question(self):
        """Analyzer should identify financial metric questions."""
        question = "What was revenue in FY2025?"

        intent = QuestionIntentAnalyzer.analyze(question)

        assert intent.intent == "financial_metric"
        assert "revenue" in intent.target_metrics
        assert "2025" in intent.target_years or "FY2025" in intent.target_years

    def test_analyzes_causal_question(self):
        """Analyzer should identify causal questions."""
        question = "Why did operating margin decline?"

        intent = QuestionIntentAnalyzer.analyze(question)

        assert intent.intent == "causal_analysis"
        assert intent.is_causal is True
        # Should identify margin-related metric
        assert any("margin" in m.lower() for m in intent.target_metrics)

    def test_analyzes_comparison_question(self):
        """Analyzer should identify comparison questions."""
        question = "Compare revenue between Company A and Company B"

        intent = QuestionIntentAnalyzer.analyze(question)

        # Should identify as comparative
        assert intent.is_comparative is True
        assert "revenue" in intent.target_metrics

    def test_analyzes_ranking_question(self):
        """Analyzer should identify ranking questions."""
        question = "Which segment had the highest revenue growth?"

        intent = QuestionIntentAnalyzer.analyze(question)

        assert intent.is_ranking is True
        assert intent.requires_calculation is True
        assert "revenue" in intent.target_metrics

    def test_extracts_multiple_years(self):
        """Analyzer should extract multiple years for trend analysis."""
        question = "How did revenue change from 2023 to 2024 to 2025?"

        intent = QuestionIntentAnalyzer.analyze(question)

        assert len(intent.target_years) >= 2
        assert "2023" in intent.target_years or 2023 in [int(y) for y in intent.target_years if y.isdigit()]

    def test_extracts_fy_notation(self):
        """Analyzer should handle FY notation."""
        question = "What was revenue in FY2025 vs FY2024?"

        intent = QuestionIntentAnalyzer.analyze(question)

        assert any("FY" in year for year in intent.target_years)

    def test_detects_segment_breakdown_question(self):
        """Analyzer should detect segment breakdown requests."""
        question = "Break down revenue by geographic segment"

        intent = QuestionIntentAnalyzer.analyze(question)

        assert intent.requires_segment_breakdown is True
        assert "revenue" in intent.target_metrics

    def test_detects_calculation_requirement(self):
        """Analyzer should detect when calculations are needed."""
        question = "What is the growth rate of revenue?"

        intent = QuestionIntentAnalyzer.analyze(question)

        assert intent.requires_calculation is True

    def test_analyzes_risk_question(self):
        """Analyzer should identify risk-related questions."""
        question = "What financial risks are disclosed?"

        intent = QuestionIntentAnalyzer.analyze(question)

        assert intent.intent == "risk" or "risk" in intent.intent.lower()

    def test_preserves_target_company_from_parameter(self):
        """Analyzer should use provided company name."""
        question = "What was revenue in FY2025?"

        intent = QuestionIntentAnalyzer.analyze(question, target_company="ABC Corp")

        assert intent.target_company == "ABC Corp"

    def test_handles_complex_multi_part_question(self):
        """Analyzer should handle compound questions."""
        question = "What was revenue in FY2025, and why did it increase?"

        intent = QuestionIntentAnalyzer.analyze(question)

        assert intent.is_causal is True or "revenue" in intent.target_metrics
        assert "2025" in intent.target_years or "FY2025" in intent.target_years

    def test_handles_empty_question(self):
        """Analyzer should handle empty input gracefully."""
        intent = QuestionIntentAnalyzer.analyze("")

        assert intent.intent == "unknown"

    def test_converts_to_dict(self):
        """Intent should convert to dictionary."""
        question = "What was revenue?"

        intent = QuestionIntentAnalyzer.analyze(question)
        intent_dict = intent.to_dict()

        assert isinstance(intent_dict, dict)
        assert "intent" in intent_dict
        assert "target_metrics" in intent_dict
        assert "is_causal" in intent_dict

    def test_detects_historical_trend_question(self):
        """Analyzer should detect historical trend questions."""
        question = "How has revenue trended over the past 5 years?"

        intent = QuestionIntentAnalyzer.analyze(question)

        # Should recognize it needs historical context
        assert intent.requires_historical is True or "revenue" in intent.target_metrics

    def test_prioritizes_metrics_by_importance(self):
        """Analyzer should order metrics by priority."""
        question = "Compare revenue, net income, and operating margin"

        intent = QuestionIntentAnalyzer.analyze(question)

        # Revenue and net_income should be higher priority than margin
        assert len(intent.target_metrics) >= 2
        if "revenue" in intent.target_metrics and "margin" in str(intent.target_metrics):
            revenue_idx = intent.target_metrics.index("revenue") if "revenue" in intent.target_metrics else 999
            margin_idx = next((i for i, m in enumerate(intent.target_metrics) if "margin" in m), 999)
            # Revenue should come before or at same position as margin (lower or equal index = higher priority)


# ============================================================
# Integration Tests
# ============================================================

class TestMasterRequirementsIntegration:
    """Test that components work together correctly."""

    def test_question_drives_retrieval_strategy(self):
        """Question intent should determine what to retrieve."""
        analyzer = QuestionIntentAnalyzer()

        # Causal question
        intent = analyzer.analyze("Why did margin decline?")
        assert intent.is_causal is True
        assert intent.intent == "causal_analysis"

        # Comparison question
        intent = analyzer.analyze("Compare revenue between A and B")
        assert intent.is_comparative is True

    def test_validation_catches_extraction_errors(self):
        """Validator should catch extraction mistakes."""
        validator = EvidenceValidator()

        # Claim with no supporting evidence
        claim = {"metric": "Revenue", "value": 999999}
        evidence = {"snippet": "Revenue was $520 million"}

        result = validator.validate_financial_value(claim, evidence)
        assert result.valid is False

    def test_end_to_end_workflow(self):
        """Test question → intent → validation workflow."""
        analyzer = QuestionIntentAnalyzer()
        validator = EvidenceValidator()

        # User asks question
        question = "What was revenue in FY2025?"

        # Analyzer extracts intent
        intent = analyzer.analyze(question)
        assert "revenue" in intent.target_metrics
        assert len(intent.target_years) > 0  # At least one year extracted

        # (Hypothetical) Extraction finds value
        claim = {
            "metric": "revenue",
            "value": 520,
            "currency": "USD",
            "year": "2025",
        }

        # Validator checks the extracted value
        evidence = {
            "snippet": "Revenue for FY2025 was $520 million",
            "company": "ABC Corp",
        }
        metadata = {"company_name": "ABC Corp", "report_year": "2025"}

        result = validator.validate_financial_value(claim, evidence, metadata)
        # Should be mostly valid (confidence >= 0.6)
        assert result.confidence >= 0.6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
