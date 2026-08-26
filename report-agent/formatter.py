"""
formatter.py

Generates professional report text for the Report Agent.
"""

from datetime import datetime
from models import ReportData

_CURRENCY_SYMBOLS = {
    "INR": "₹",
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
}


def format_financial_value(value, metric=None) -> str:
    """Format structured or legacy financial values for report display."""
    if value is None:
        return ""
    metadata = value if isinstance(value, dict) else {}
    nested_value = metadata.get("value") if isinstance(metadata.get("value"), dict) else None
    if nested_value:
        metadata = {**metadata, **nested_value}
    metric_text = str(metric or metadata.get("metric") or "").casefold()
    numeric = metadata.get("numeric_value", metadata.get("value"))
    currency = str(metadata.get("currency") or "").upper()
    unit = str(metadata.get("unit") or metadata.get("unit_scale") or "").casefold().replace(" ", "_")
    if numeric is None and not metadata:
        return str(value).strip()
    if numeric is None:
        return str(metadata.get("display_value") or "Not reported")
    try:
        number = float(numeric)
    except (TypeError, ValueError):
        if isinstance(numeric, (dict, list, tuple, set)):
            return str(metadata.get("display_value") or "Not reported")
        return str(metadata.get("display_value") or numeric)
    if unit in {"percent", "%"} or "margin" in metric_text or "growth" in metric_text:
        return f"{number:g}%"
    if unit in {"x", "ratio", "multiple"} or "ratio" in metric_text or "debt/equity" in metric_text:
        return f"{number:g}x"
    if unit == "per_share" or metric_text in {"eps", "basic eps", "diluted eps", "trend eps"}:
        return f"{_CURRENCY_SYMBOLS.get(currency, '')}{number:.2f} per share"
    if unit == "days":
        return f"{number:g} days"
    sign = "-" if number < 0 else ""
    formatted = f"{abs(number):,.2f}".rstrip("0").rstrip(".")
    symbol = _CURRENCY_SYMBOLS.get(currency, "")
    suffix = f" {unit}" if unit and unit not in {"units", "unitless"} else (" units" if unit in {"units", "unitless"} else "")
    return f"{sign}{symbol}{formatted}{suffix}"


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

        summary = (
            f"{company} has been analysed using the Multi-Agent Financial "
            f"Research System. The report combines financial extraction, "
            f"risk detection, company comparison, and research findings "
            f"to provide an overall assessment of the organisation."
        )

        metrics = getattr(report.extraction, "metrics", []) or []
        if metrics:
            summary += "\n\n" + "; ".join(
                f"{metric.get('metric', 'Metric')}: {format_financial_value(metric, metric.get('metric'))}"
                for metric in metrics if isinstance(metric, dict) and metric.get("value") is not None
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

        return list(dict.fromkeys(points))