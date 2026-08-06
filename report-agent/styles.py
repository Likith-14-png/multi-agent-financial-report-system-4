"""
styles.py

Professional ReportLab styles for the
Multi-Agent Financial Research System.
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet


class ReportStyles:
    """
    Centralised styles used throughout the report.
    """

    def __init__(self):

        base = getSampleStyleSheet()

        self.title = ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=30,
            textColor=colors.HexColor("#0B3C5D"),
            spaceAfter=25,
        )

        self.subtitle = ParagraphStyle(
            "Subtitle",
            parent=base["Heading2"],
            alignment=TA_CENTER,
            fontName="Helvetica",
            fontSize=14,
            leading=18,
            textColor=colors.grey,
            spaceAfter=20,
        )

        self.heading1 = ParagraphStyle(
            "Heading1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0B3C5D"),
            spaceBefore=16,
            spaceAfter=10,
        )

        self.heading2 = ParagraphStyle(
            "Heading2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            textColor=colors.HexColor("#1D4E89"),
            spaceBefore=12,
            spaceAfter=8,
        )

        self.body = ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            alignment=TA_LEFT,
            fontName="Helvetica",
            fontSize=11,
            leading=18,
            spaceAfter=8,
        )

        self.small = ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.grey,
        )

    @staticmethod
    def table_style():
        """
        Returns a reusable table style.
        """

        from reportlab.platypus import TableStyle

        return TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B3C5D")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),

            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),

            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),

            ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),

            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),

            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),

            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])