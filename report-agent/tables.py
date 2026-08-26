"""
tables.py

Creates professional ReportLab tables for the
Multi-Agent Financial Research System.
"""

from xml.sax.saxutils import escape

from reportlab.platypus import Paragraph, Table

from styles import ReportStyles
from models import ReportData
from formatter import format_financial_value


class ReportTables:
    """
    Builds all tables used in the report.
    """

    def __init__(self):
        self.styles = ReportStyles()

    def _cell(self, value):
        """Wrap cell content so long evidence can flow across pages."""
        if value is None:
            value = ""
        if isinstance(value, dict):
            value = "\n".join(f"{key}: {item}" for key, item in value.items())
        elif isinstance(value, (list, tuple, set)):
            value = "\n".join(str(item) for item in value)
        text = escape(str(value)).replace("\n", "<br/>")
        return Paragraph(text, self.styles.small)

    def _table(self, data, col_widths):
        table = Table(
            data,
            colWidths=col_widths,
            repeatRows=1,
            splitByRow=1,
            splitInRow=1,
        )
        table.setStyle(self.styles.table_style())
        return table

    def financial_metrics_table(self, report: ReportData):
        data = [["Financial Metric", "Value", "Period", "Source"]]
        metrics = getattr(report.extraction, "metrics", []) or []
        for metric in metrics:
            if not isinstance(metric, dict):
                continue
            value = metric.get("value")
            if value is None:
                continue
            provenance = metric.get("source") or ""
            if metric.get("source_page") is not None:
                provenance += f", Page {metric['source_page']}"
            if metric.get("chunk_id"):
                provenance += f", Chunk {metric['chunk_id']}"
            data.append([
                self._cell(metric.get("metric") or "Metric"),
                self._cell(format_financial_value(metric, metric.get("metric"))),
                self._cell(metric.get("year") or "Not reported"),
                self._cell(provenance),
            ])
        if len(data) == 1:
            data.append([self._cell("No financial metrics reported"), self._cell("Not reported"), self._cell(""), self._cell("")])

        return self._table(data, [125, 165, 75, 115])

    def financial_ratio_table(self, report: ReportData):

        data = [["Ratio", "Value"]]

        ratios = report.extraction.financial_ratios

        if not ratios:
            data.append([self._cell("No Ratio Available"), self._cell("N/A")])
        else:
            for key, value in ratios.items():
                data.append([self._cell(key), self._cell(format_financial_value(value, key))])

        return self._table(data, [220, 220])

    def risk_table(self, report: ReportData):

        data = [["Category", "Severity", "Description"]]

        if not report.red_flags.risks:
            data.append(
                [
                    self._cell(""),
                    self._cell(""),
                    self._cell("No source-supported red flags identified.")
                ]
            )

        else:

            for risk in report.red_flags.risks:

                data.append(
                    [
                        self._cell(risk.title or risk.category),
                        self._cell(risk.severity),
                        self._cell(f"{risk.description}"
                        + (f" Evidence: {risk.evidence}" if risk.evidence else "")
                        + (f" Source: {risk.source}" if risk.source else "")),
                    ]
                )

        return self._table(data, [120, 80, 240])

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
                    "No comparable financial metrics available.",
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
                        self._cell(company.company_name),
                        self._cell(format_financial_value(company.revenue, "Revenue")),
                        self._cell(format_financial_value(company.net_profit, "Net Income")),
                        self._cell(format_financial_value(company.operating_margin, "Operating Margin")),
                        self._cell(format_financial_value(company.debt, "Debt")),
                        self._cell(format_financial_value(company.cash_flow, "Cash Flow")),
                    ]
                )

        return self._table(data, [90, 85, 85, 100, 85, 85])

    def research_table(self, report: ReportData):
        if not report.research:
            return [Paragraph("No validated research findings available.", self.styles.body)]

        flowables = []
        for item in report.research:
            flowables.extend([
                Paragraph(f"<b>Question:</b> {item.question}", self.styles.body),
                Paragraph(f"<b>Answer:</b> {item.answer}", self.styles.body),
                Paragraph(f"<b>Evidence:</b> {item.evidence}", self.styles.body),
                Paragraph(
                    "<b>Source:</b> "
                    f"{item.source}"
                    + (f", Page {item.source_page}" if item.source_page is not None else "")
                    + (f", Chunk {item.source_chunk}" if item.source_chunk else "")
                    + (f"<br/><b>Citation:</b> {item.citation}" if item.citation else ""),
                    self.styles.body,
                ),
            ])
        return flowables

    def peer_comparison_table(self, report: ReportData):
        """Render canonical comparison-agent rows, including cross-company records."""
        data = [["Metric", "Company A", "Company B", "Difference", "Assessment"]]
        records = report.comparison.records if hasattr(report.comparison, "records") else []
        for row in records:
            companies = row.get("companies") or [] if isinstance(row, dict) else []
            if companies:
                values = {
                    item.get("company_name"): item.get("display_value") or item.get("value")
                    for item in companies if isinstance(item, dict)
                }
                names = list(values)
                assessment = row.get("interpretation") or row.get("reason") or row.get("comparison_status") or "Not reported"
                data.append([self._cell(row.get("metric", "Metric")), self._cell(values.get(names[0], "Not reported")), self._cell(values.get(names[1], "Not reported") if len(names) > 1 else "Not reported"), self._cell(row.get("absolute_difference", row.get("difference", "Not directly comparable"))), self._cell(assessment)])
            elif isinstance(row, dict):
                company_a = row.get("company_a") or {}
                company_b = row.get("company_b") or {}
                data.append([
                    self._cell(row.get("metric", "Metric")),
                    self._cell(format_financial_value(company_a, row.get("metric"))),
                    self._cell(format_financial_value(company_b, row.get("metric"))),
                    self._cell(row.get("absolute_difference", row.get("difference", "Not directly comparable"))),
                    self._cell(row.get("interpretation") or row.get("reason") or row.get("comparison_status") or "Not reported"),
                ])
        if len(data) == 1:
            data.append([self._cell("No comparable financial metrics available."), self._cell(""), self._cell(""), self._cell(""), self._cell("")])
        return self._table(data, [100, 90, 90, 80, 180])