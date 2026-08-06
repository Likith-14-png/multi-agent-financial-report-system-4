"""
utils.py

Utility functions for the Report Agent.
"""

from pathlib import Path
from datetime import datetime


def ensure_directory(path: str) -> Path:
    """
    Create the directory if it doesn't exist.
    """
    directory = Path(path)

    directory.mkdir(parents=True, exist_ok=True)

    return directory


def timestamp() -> str:
    """
    Return the current timestamp.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def output_pdf_path(filename: str = "financial_report.pdf") -> str:
    """
    Return the default output PDF path.
    """
    output_dir = ensure_directory("output")

    return str(output_dir / filename)