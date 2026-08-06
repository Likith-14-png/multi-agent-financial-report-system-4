"""
report_service.py

Coordinates the Report Agent workflow.
"""

from models import ReportData
from pdf_builder import PDFBuilder


class ReportService:
    """
    High-level service responsible for generating
    the complete financial research report.
    """

    def __init__(self):
        self.builder = PDFBuilder()

    def generate(self, report: ReportData, output_file: str):
        """
        Generate the analyst-style PDF report.

        Parameters
        ----------
        report : ReportData
            Structured data received from all agents.

        output_file : str
            Output PDF path.
        """

        self.builder.build(report, output_file)

        return output_file