from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from document_agent import DocumentAgent


def make_agent():
    return object.__new__(DocumentAgent)


def test_extract_company_name_from_generic_report_text():
    agent = make_agent()
    text = """
    Annual Report
    Example Manufacturing Holdings Ltd.
    For the year ended December 31, 2024
    """

    assert agent._extract_company_name(text) == "Example Manufacturing Holdings Ltd."


def test_infer_report_type_from_document_text():
    agent = make_agent()
    text = "Proxy Statement for the Annual Meeting of Shareholders"

    assert agent._infer_report_type(text) == "Proxy Statement"


def test_extract_company_name_ignores_long_descriptive_sentence():
    agent = make_agent()
    text = "Fiscal year 2024 was a pivotal year for Microsoft. We entered our 50th year with strong momentum."

    assert agent._extract_company_name(text) == ""


def test_extract_company_name_prefers_document_owner_over_product_mentions():
    agent = make_agent()
    text = "Microsoft Annual Report 2024\nGitHub Copilot and Microsoft 365 continue to drive growth."

    assert agent._extract_company_name(text) == "Microsoft"


def test_extract_section_heading_and_type_from_heading_line():
    agent = make_agent()
    chunk = "Management Discussion and Analysis\nRevenue grew meaningfully during the period."

    section_title, section_type = agent._extract_section_heading_and_type(chunk)

    assert section_title == "Management Discussion and Analysis"
    assert section_type == "management_discussion"
