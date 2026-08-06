"""
tables.py

Creates professional ReportLab tables for the
Multi-Agent Financial Research System.
"""

from reportlab.platypus import Table

from styles import ReportStyles
from models import ReportData


class ReportTables:
    """
    Builds all tables used in the report.
    """

    def __init__(self):
        self.styles = ReportStyles()

    def financial_metrics_table(self, report: ReportData):

        e = report.extraction

        data = [
            ["Financial Metric", "Value"],
            ["Revenue", e.revenue if e.revenue is not None else "N/A"],
            ["Net Profit", e.net_profit if e.net_profit is not None else "N/A"],
            ["EPS", e.eps if e.eps is not None else "N/A"],
            ["Operating Margin", e.operating_margin if e.operating_margin is not None else "N/A"],
            ["Gross Margin", e.gross_margin if e.gross_margin is not None else "N/A"],
            ["EBITDA", e.ebitda if e.ebitda is not None else "N/A"],
            ["Assets", e.assets if e.assets is not None else "N/A"],
            ["Liabilities", e.liabilities if e.liabilities is not None else "N/A"],
            ["Cash Flow", e.cash_flow if e.cash_flow is not None else "N/A"],
        ]

        table = Table(data, colWidths=[220, 220])
        table.setStyle(self.styles.table_style())

        return table

    def financial_ratio_table(self, report: ReportData):

        data = [["Ratio", "Value"]]

        ratios = report.extraction.financial_ratios

        if not ratios:
            data.append(["No Ratio Available", "N/A"])
        else:
            for key, value in ratios.items():
                data.append([key, value])

        table = Table(data, colWidths=[220, 220])
        table.setStyle(self.styles.table_style())

        return table

    def risk_table(self, report: ReportData):

        data = [["Category", "Severity", "Description"]]

        if not report.red_flags.risks:
            data.append(
                [
                    "General",
                    "Low",
                    "No major financial risks detected."
                ]
            )

        else:

            for risk in report.red_flags.risks:

                data.append(
                    [
                        risk.category,
                        risk.severity,
                        risk.description,
                    ]
                )

        table = Table(
            data,
            colWidths=[120, 80, 240]
        )

        table.setStyle(self.styles.table_style())

        return table

    def comparison_table(self, report: ReportData):

        data = [
            [
                "Company",
                "Revenue",
                "Net Profit",
                "Operating Margin",
                "Debt",
                "Cash Flow",
            ]
        ]

        if not report.comparison.companies:

            data.append(
                [
                    "No Comparison Data",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                ]
            )

        else:

            for company in report.comparison.companies:

                data.append(
                    [
                        company.company_name,
                        company.revenue,
                        company.net_profit,
                        company.operating_margin,
                        company.debt,
                        company.cash_flow,
                    ]
                )

        table = Table(data)

        table.setStyle(self.styles.table_style())

        return table

    def research_table(self, report: ReportData):

        data = [
            [
                "Question",
                "Answer",
                "Source",
            ]
        ]

        if not report.research:

            data.append(
                [
                    "No Research",
                    "-",
                    "-",
                ]
            )

        else:

            for item in report.research:

                data.append(
                    [
                        item.question,
                        item.answer,
                        item.source,
                    ]
                )

        table = Table(
            data,
            colWidths=[180, 220, 120]
        )

        table.setStyle(self.styles.table_style())

        return table