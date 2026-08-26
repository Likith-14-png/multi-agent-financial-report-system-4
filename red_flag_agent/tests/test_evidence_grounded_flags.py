import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RED_FLAG_PATH = ROOT / "red_flag_agent"
if str(RED_FLAG_PATH) not in sys.path:
    sys.path.insert(0, str(RED_FLAG_PATH))

from app.services.offline_analyzer import OfflineAnalyzer


def test_detects_evidence_based_debt_and_margin_flags():
    chunks = [{
        "document": (
            "Total debt increased to $42 billion in 2025. "
            "Operating margin fell to 13.2% from 18.4% during the year."
        ),
        "metadata": {
            "company_name": "Acme Corp",
            "page_number": 12,
            "chunk_id": "chunk-12",
        },
    }]

    result = OfflineAnalyzer().analyze("What are the main financial risks?", chunks)

    assert result["total_flags"] >= 2
    titles = {flag["title"].lower() for flag in result["flags"]}
    assert any("debt" in title or "leverage" in title for title in titles)
    assert any("margin" in title or "profitability" in title for title in titles)
    assert all(flag.get("page") == 12 for flag in result["flags"])
    assert all(flag.get("evidence") for flag in result["flags"])


def test_rejects_negative_evidence_and_missing_values():
    chunks = [{
        "document": (
            "No material liquidity risk was identified. Cash flow remained positive and the company "
            "reported no debt increase during the year. Management disclosed no litigation or accounting issues."
        ),
        "metadata": {
            "company_name": "Acme Corp",
            "page_number": 8,
            "chunk_id": "chunk-8",
        },
    }]

    result = OfflineAnalyzer().analyze("What are the risks?", chunks)

    assert result["total_flags"] == 0
    assert result["flags"] == []
    assert result["overall_risk"] == "Low"


def test_preserves_currency_and_units_in_evidence_snippets():
    chunks = [{
        "document": "Operating cash flow declined to $1.1 billion from $1.8 billion; working capital remained under pressure.",
        "metadata": {
            "company_name": "Acme Corp",
            "page_number": 17,
            "chunk_id": "chunk-17",
        },
    }]

    result = OfflineAnalyzer().analyze("What are the cash flow risks?", chunks)

    assert result["total_flags"] >= 1
    assert any("$1.1 billion" in flag["evidence"] for flag in result["flags"]) or any("$1.8 billion" in flag["evidence"] for flag in result["flags"])
    assert all("$" in flag["evidence"] or "billion" in flag["evidence"].lower() for flag in result["flags"])
