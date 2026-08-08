"""
charts.py

Generates professional financial charts for the Report Agent.

All charts are saved as PNG images and later embedded into the PDF.
"""

from pathlib import Path
import matplotlib.pyplot as plt

from models import ReportData


class ChartGenerator:
    """
    Creates charts for the financial report.
    """

    def __init__(self, output_dir: str = "output/charts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _save_chart(self, filename: str):
        filepath = self.output_dir / filename
        plt.tight_layout()
        plt.savefig(filepath, dpi=300)
        plt.close()
        return filepath

    def revenue_profit_chart(self, report: ReportData):

        revenue = report.extraction.revenue or 0
        profit = report.extraction.net_profit or 0

        plt.figure(figsize=(6, 4))

        plt.bar(
            ["Revenue", "Net Profit"],
            [revenue, profit]
        )

        plt.title("Revenue vs Net Profit")
        plt.ylabel("Value")

        return self._save_chart("revenue_profit.png")

    def assets_liabilities_chart(self, report: ReportData):

        assets = report.extraction.assets or 0
        liabilities = report.extraction.liabilities or 0

        plt.figure(figsize=(6, 4))

        plt.bar(
            ["Assets", "Liabilities"],
            [assets, liabilities]
        )

        plt.title("Assets vs Liabilities")
        plt.ylabel("Value")

        return self._save_chart("assets_liabilities.png")

    def cash_flow_chart(self, report: ReportData):

        cash = report.extraction.cash_flow or 0

        plt.figure(figsize=(6, 4))

        plt.bar(
            ["Cash Flow"],
            [cash]
        )

        plt.title("Cash Flow")

        return self._save_chart("cash_flow.png")

    def ratio_chart(self, report: ReportData):

        ratios = report.extraction.financial_ratios

        if not ratios:
            return None

        plt.figure(figsize=(8, 4))

        plt.bar(
            list(ratios.keys()),
            list(ratios.values())
        )

        plt.xticks(rotation=30)

        plt.title("Financial Ratios")

        return self._save_chart("ratios.png")

    def risk_distribution_chart(self, report: ReportData):

        severity = {
            "Low": 0,
            "Medium": 0,
            "High": 0,
        }

        for risk in report.red_flags.risks:
            level = risk.severity.title()

            if level in severity:
                severity[level] += 1

        plt.figure(figsize=(5, 5))

        plt.pie(
            severity.values(),
            labels=severity.keys(),
            autopct="%1.0f%%"
        )

        plt.title("Risk Distribution")

        return self._save_chart("risk_distribution.png")

    def company_comparison_chart(self, report: ReportData):

        if not report.comparison.companies:
            return None

        companies = []
        revenues = []

        for company in report.comparison.companies:
            companies.append(company.company_name)
            revenues.append(company.revenue or 0)

        plt.figure(figsize=(8, 4))

        plt.bar(companies, revenues)

        plt.xticks(rotation=20)

        plt.title("Company Revenue Comparison")

        return self._save_chart("company_comparison.png")

    def generate_all(self, report: ReportData):

        charts = []

        charts.append(self.revenue_profit_chart(report))
        charts.append(self.assets_liabilities_chart(report))
        charts.append(self.cash_flow_chart(report))

        ratio = self.ratio_chart(report)
        if ratio:
            charts.append(ratio)

        risk = self.risk_distribution_chart(report)
        if risk:
            charts.append(risk)

        comparison = self.company_comparison_chart(report)
        if comparison:
            charts.append(comparison)

        return charts