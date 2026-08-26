"""
analysis.py

Generates analytical commentary for the financial report.
"""

from models import ReportData
from formatter import format_financial_value


class FinancialAnalysis:
    """
    Generates analyst-style financial interpretations.
    """

    @staticmethod
    def performance_analysis(report: ReportData) -> list[str]:
        e = report.extraction
        analysis = []

        for metric in getattr(e, "metrics", []) or []:
            if isinstance(metric, dict) and metric.get("value") is not None:
                analysis.append(f"{metric.get('metric', 'Metric')}: Reported value is {format_financial_value(metric, metric.get('metric'))}.")

        return analysis

    @staticmethod
    def ratio_analysis(report: ReportData) -> list[str]:
        ratios = report.extraction.financial_ratios

        explanations = {
            "ROE": "Return on Equity measures how efficiently shareholder capital is used.",
            "ROA": "Return on Assets measures how efficiently assets generate profit.",
            "Current Ratio": "Measures the company's ability to meet short-term obligations.",
            "Debt-to-Equity": "Indicates the level of financial leverage.",
            "Profit Margin": "Shows how much profit is earned from each unit of revenue.",
            "Operating Margin": "Measures operating efficiency before interest and taxes.",
        }

        output = []

        for ratio, meaning in explanations.items():
            value = ratios.get(ratio)

            if value is None:
                output.append(f"{ratio}: Information not available.")
            else:
                output.append(
                    f"{ratio}: {format_financial_value(value, ratio)}\n"
                    f"Interpretation: {meaning}"
                )

        return output

    @staticmethod
    def risk_assessment(report: ReportData) -> list[dict]:
        risks = []

        for item in report.red_flags.risks:
            risks.append({
                "Category": item.category,
                "Severity": item.severity,
                "Description": item.description,
            })

        return risks

    @staticmethod
    def swot_analysis(report: ReportData) -> dict:
        strengths = []
        weaknesses = []
        opportunities = []
        threats = []

        if report.extraction.net_profit is not None:
            strengths.append("Company is generating profits.")

        if report.extraction.cash_flow is not None:
            strengths.append("Positive cash flow supports operations.")

        if report.red_flags.risks:
            weaknesses.append("Financial risks have been identified.")

        if report.comparison.companies:
            opportunities.append(
                "Benchmarking against peers may identify growth opportunities."
            )

        return {
            "Strengths": strengths,
            "Weaknesses": weaknesses,
            "Opportunities": opportunities,
            "Threats": threats,
        }

    @staticmethod
    def investment_outlook(report: ReportData) -> str:
        return (
            "This report provides an objective assessment of the company's "
            "financial position based on the available financial documents. "
            "The findings should be considered alongside broader market, "
            "industry, and economic factors. This report does not constitute "
            "investment advice."
        )