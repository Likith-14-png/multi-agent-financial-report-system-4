"""
main.py

Entry point for the Multi-Agent Financial Research System
Report Agent.
"""

from models import (
    ReportData,
    ExtractionData,
    RedFlagData,
    RiskItem,
    ComparisonData,
    CompanyComparison,
    ResearchItem,
)

from report_service import ReportService
from utils import output_pdf_path


def create_sample_report() -> ReportData:

    extraction = ExtractionData(
        company_name="Tesla Inc.",
        industry="Automotive & Clean Energy",
        business_model="Electric Vehicles, Energy Storage and Software",
        market_position="Global EV Market Leader",

        revenue=96.0,
        net_profit=15.0,
        eps=4.25,
        operating_margin=11.0,
        gross_margin=19.0,
        ebitda=18.0,
        assets=106.0,
        liabilities=43.0,
        cash_flow=13.0,

        financial_ratios={
            "ROE": 24.0,
            "ROA": 12.0,
            "Current Ratio": 1.60,
            "Debt-to-Equity": 0.42,
            "Profit Margin": 15.0,
        },
    )

    red_flags = RedFlagData(
        risks=[
            RiskItem(
                category="Debt",
                description="Debt increased compared with previous year.",
                severity="Medium",
            ),
            RiskItem(
                category="Liquidity",
                description="Liquidity position should be monitored.",
                severity="Low",
            ),
            RiskItem(
                category="Margins",
                description="Operating margin declined slightly.",
                severity="Medium",
            ),
        ]
    )

    comparison = ComparisonData(
        companies=[
            CompanyComparison(
                company_name="Tesla",
                revenue=96.0,
                net_profit=15.0,
                operating_margin=11.0,
                debt=43.0,
                cash_flow=13.0,
                ratios={
                    "ROE": 24,
                    "ROA": 12,
                },
            ),
            CompanyComparison(
                company_name="BYD",
                revenue=85.0,
                net_profit=12.5,
                operating_margin=10.2,
                debt=47.0,
                cash_flow=10.5,
                ratios={
                    "ROE": 20,
                    "ROA": 10,
                },
            ),
        ]
    )

    research = [
        ResearchItem(
            question="Is Tesla financially stable?",
            answer="Tesla demonstrates strong profitability and cash generation.",
            evidence="Revenue and operating cash flow remained strong during the reporting period.",
            source="Annual Report Page 42",
        ),
        ResearchItem(
            question="What are the major financial risks?",
            answer="Margin pressure and increasing competition remain the primary risks.",
            evidence="Operating margin declined compared with the previous financial year.",
            source="Risk Factors Page 58",
        ),
    ]

    return ReportData(
        extraction=extraction,
        red_flags=red_flags,
        comparison=comparison,
        research=research,
    )


def main():

    report = create_sample_report()

    service = ReportService()

    output = output_pdf_path()

    service.generate(report, output)

    print("=" * 60)
    print("Financial Research Report Generated Successfully")
    print(f"Output PDF: {output}")
    print("=" * 60)


if __name__ == "__main__":
    main()