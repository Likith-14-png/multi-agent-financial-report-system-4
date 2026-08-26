from extraction_agent import (
    _find_observation_conflicts,
    _provenance_score,
    extract_report_metrics,
    select_canonical_observation,
)


def _observation(value, year=2026, context="income_statement_audited", section="Income Statement", page=1, metric="revenue"):
    return {
        "metric_name": metric,
        "raw_value": f"₹{value} million",
        "numeric_value": value,
        "currency": "INR",
        "unit": "million",
        "report_year": year,
        "statement_context": context,
        "source_section": section,
        "source_page": page,
        "source_chunk_id": f"chunk-{page}",
        "canonical_label": "Revenue",
    }


def test_primary_statement_beats_accounting_notes_and_keeps_supporting_observation():
    statement = _observation(187472, section="Consolidated Income Statement", page=1)
    notes = _observation(187472, context="disclosure", section="Accounting Notes", page=9)
    selected = select_canonical_observation([notes, statement], "revenue", target_year=2026)

    assert selected["source_page"] == 1
    assert selected["numeric_value"] == 187472
    assert len([notes, statement]) == 2
    assert _provenance_score(statement, 2026) > _provenance_score(notes, 2026)


def test_exact_requested_year_beats_better_source_from_another_year():
    old_statement = _observation(176320, year=2025, page=1)
    target_notes = _observation(187472, year=2026, context="disclosure", section="Accounting Notes", page=9)

    selected = select_canonical_observation([old_statement, target_notes], "revenue", target_year=2026)

    assert selected["report_year"] == 2026
    assert selected["numeric_value"] == 187472


def test_different_years_do_not_create_a_conflict():
    observations = [_observation(176320, year=2025), _observation(187472, year=2026)]

    assert _find_observation_conflicts(observations) == {}


def test_genuine_same_year_value_conflict_remains_visible():
    observations = [_observation(187472), _observation(190000, context="disclosure", section="Accounting Notes", page=9)]

    conflicts = _find_observation_conflicts(observations)

    assert len(conflicts["revenue"]) == 2
    assert {item["numeric_value"] for item in conflicts["revenue"]} == {187472, 190000}


def test_segment_observation_remains_separate_from_consolidated_revenue():
    consolidated = _observation(187472, section="Consolidated Income Statement")
    segment = _observation(45000, context="segment_metrics", section="Digital Services", metric="software_revenue")

    assert select_canonical_observation([consolidated], "revenue", target_year=2026) is consolidated
    assert select_canonical_observation([segment], "software_revenue", target_year=2026) is segment
    assert _find_observation_conflicts([consolidated, segment]) == {}


def test_reference_values_are_ignored_by_extraction():
    text = """
    Expected Cross-Document Checks:
    Revenue: ₹999,999 million

    Income Statement:
    Revenue: ₹187,472 million
    """
    result = extract_report_metrics(text, metadata={"company_name": "Test Co", "report_year": 2026})

    assert result["revenue"] == "₹187,472 million"
    assert result["traceability"]["revenue"]["value"] == "₹187,472 million"


def test_balance_sheet_statement_beats_notes():
    statement = _observation(185000, section="Balance Sheet", page=2, metric="total_assets")
    notes = _observation(185000, context="disclosure", section="Accounting Notes", page=10, metric="total_assets")

    assert select_canonical_observation([notes, statement], "total_assets", target_year=2026)["source_page"] == 2


def test_cash_flow_statement_beats_notes():
    statement = _observation(14200, section="Cash Flow Statement", page=3, metric="operating_cash_flow")
    notes = _observation(14200, context="disclosure", section="Notes", page=11, metric="operating_cash_flow")

    assert select_canonical_observation([notes, statement], "operating_cash_flow", target_year=2026)["source_page"] == 3