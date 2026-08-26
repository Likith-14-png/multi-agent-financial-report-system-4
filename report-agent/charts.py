"""
charts.py

Generates professional financial charts for the Report Agent.

All charts are saved as PNG images and later embedded into the PDF.
"""

from pathlib import Path
import matplotlib.pyplot as plt
import re

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

    @staticmethod
    def _numeric(value):
        if isinstance(value, dict):
            if value.get("status") in {"not_found", "unknown", "reported_none"}:
                return None
            value = value.get("value") if value.get("value") is not None else value.get("display_value")
        if isinstance(value, (int, float)):
            return float(value)
        match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", str(value or ""))
        return float(match.group(0).replace(",", "")) if match else None

    def revenue_profit_chart(self, report: ReportData):

        values = [("Revenue", self._numeric(report.extraction.revenue)), ("Net Profit", self._numeric(report.extraction.net_profit))]
        values = [(label, value) for label, value in values if value is not None]
        if not values:
            return None

        plt.figure(figsize=(6, 4))

        plt.bar(
            [label for label, _ in values],
            [value for _, value in values]
        )

        plt.title("Revenue vs Net Profit")
        plt.ylabel("Value")

        return self._save_chart("revenue_profit.png")

    def assets_liabilities_chart(self, report: ReportData):

        values = [("Assets", self._numeric(report.extraction.assets)), ("Liabilities", self._numeric(report.extraction.liabilities))]
        values = [(label, value) for label, value in values if value is not None]
        if not values:
            return None

        plt.figure(figsize=(6, 4))

        plt.bar(
            [label for label, _ in values],
            [value for _, value in values]
        )

        plt.title("Assets vs Liabilities")
        plt.ylabel("Value")

        return self._save_chart("assets_liabilities.png")

    def cash_flow_chart(self, report: ReportData):

        cash = self._numeric(report.extraction.cash_flow)
        if cash is None:
            return None

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

        if not any(severity.values()):
            return None

        plt.figure(figsize=(5, 5))

        plt.pie(
            [value for value in severity.values() if value > 0],
            labels=[key for key, value in severity.items() if value > 0],
            autopct="%1.0f%%"
        )

        plt.title("Risk Distribution")

        return self._save_chart("risk_distribution.png")

    def company_comparison_chart(self, report: ReportData):

        if not report.comparison.companies and not getattr(report.comparison, "records", []):
            return None

        companies = []
        revenues = []
        records = getattr(report.comparison, "records", [])
        revenue_row = next((row for row in records if str(row.get("metric", "")).lower() == "revenue"), None)
        if revenue_row:
            for company in revenue_row.get("companies", []):
                value = self._numeric(company.get("value"))
                if value is not None:
                    revenues.append(value)
                    companies.append(company.get("company_name", "Company"))
        else:
            for company in report.comparison.companies:
                value = self._numeric(company.revenue)
                if value is not None:
                    companies.append(company.company_name)
                    revenues.append(value)

        if len(companies) < 2 or len(revenues) < 2:
            return None

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