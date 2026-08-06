"""
formatter.py

Generates professional report text for the Report Agent.
"""

from datetime import datetime
from models import ReportData


class ReportFormatter:
    """
    Creates formatted narrative sections for the financial report.
    """

    @staticmethod
    def current_date() -> str:
        return datetime.now().strftime("%d %B %Y")

    @staticmethod
    def executive_summary(report: ReportData) -> str:
        company = report.extraction.company_name

        revenue = report.extraction.revenue
        profit = report.extraction.net_profit
        operating_margin = report.extraction.operating_margin

        summary = (
            f"{company} has been analysed using the Multi-Agent Financial "
            f"Research System. The report combines financial extraction, "
            f"risk detection, company comparison, and research findings "
            f"to provide an overall assessment of the organisation."
        )

        if revenue is not None:
            summary += (
                f"\n\nThe company reported revenue of {revenue:,}, "
                f"indicating the scale of its operations."
            )

        if profit is not None:
            summary += (
                f" Net profit of {profit:,} reflects "
                f"overall profitability."
            )

        if operating_margin is not None:
            summary += (
                f" Operating margin of {operating_margin}% "
                f"provides insight into operational efficiency."
            )

        summary += (
            "\n\nOverall, the financial information suggests that "
            "further evaluation of profitability, liquidity, "
            "financial risks and competitive positioning is "
            "required before drawing investment conclusions."
        )

        return summary

    @staticmethod
    def company_overview(report: ReportData) -> str:
        extraction = report.extraction

        industry = extraction.industry or "Information not available"
        business = extraction.business_model or "Information not available"
        position = extraction.market_position or "Information not available"

        return (
            f"Company Name: {extraction.company_name}\n\n"
            f"Industry: {industry}\n\n"
            f"Business Model:\n{business}\n\n"
            f"Market Position:\n{position}"
        )

    @staticmethod
    def key_takeaways(report: ReportData):
        points = []

        if report.extraction.revenue is not None:
            points.append("Revenue information successfully extracted.")

        if report.extraction.net_profit is not None:
            points.append("Profitability metrics are available.")

        if report.red_flags.risks:
            points.append(
                f"{len(report.red_flags.risks)} financial risks detected."
            )
        else:
            points.append("No significant financial risks detected.")

        if report.comparison.companies:
            points.append("Company comparison completed.")

        if report.research:
            points.append("Research findings include cited evidence.")

        while len(points) < 10:
            points.append("Additional financial analysis recommended.")

        return points[:10]