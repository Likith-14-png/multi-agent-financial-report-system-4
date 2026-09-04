from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / 'extraction-agent'))

from extraction_agent import (
    extract_report_metrics,
    extract_table_header_units,
    validate_financial_accounting_invariants,
    _classify_metric_candidate,
    parse_financial_number,
)


def test_task1_ind_as_statutory_table_header_units():
    header1 = '(All amounts in Indian Rupees million except share data)'
    curr1, unit1 = extract_table_header_units(header1)
    assert curr1 == 'INR'
    assert unit1 == 'million'

    header2 = '(Amounts in Indian Rupees in millions)'
    curr2, unit2 = extract_table_header_units(header2)
    assert curr2 == 'INR'
    assert unit2 == 'million'

    header3 = '(All amounts are in Indian Rupee crores)'
    curr3, unit3 = extract_table_header_units(header3)
    assert curr3 == 'INR'
    assert unit3 == 'crore'


def test_task1_table_unit_strictly_overrides_narrative_crore():
    text = (
        'Highlights\n'
        'The company crossed ₹100 crore in milestone ARR during the fiscal year.\n\n'
        'Consolidated Statement of Profit and Loss\n'
        '(All amounts in Indian Rupees million)\n'
        'Revenue from operations\n'
        '15,056.06\n'
        '12,000.00\n'
        '10,000.00\n'
    )
    result = extract_report_metrics(
        text,
        metadata={'company_name': 'Amagi Media', 'report_year': '2026'},
        enable_llm=False,
    )
    assert result['financial_values']['revenue']['currency'] == 'INR'
    assert result['financial_values']['revenue']['unit_scale'] == 'million'
    assert result['revenue'] == '₹15,056.06 million'


def test_task2_dynamic_column_year_alignment_and_no_inversion():
    text = (
        'Statement of Profit and Loss\n'
        '(All amounts in Indian Rupees million)\n'
        '2026\n2025\n2024\n'
        'Revenue from operations\n'
        '1,506\n'
        '1,163\n'
        '879\n'
        'Gross profit\n'
        '800\n'
        '600\n'
        '450\n'
        'Net income\n'
        '716\n'
        '500\n'
        '350\n'
        'R&D expenditure\n'
        '150\n'
        '120\n'
        '100\n'
    )
    result = extract_report_metrics(
        text,
        metadata={'company_name': 'Amagi Media', 'report_year': '2026'},
        enable_llm=False,
    )

    # 1. Chronological time series order in yearly_metrics: FY24=879, FY25=1163, FY26=1506
    rev_series = result['yearly_metrics']['Revenue']
    years = [item['year'] for item in rev_series]
    values = [item['numeric_value'] for item in rev_series]
    assert years == [2024, 2025, 2026]
    assert values == [879.0, 1163.0, 1506.0]

    # 2. No False Negatives for FY26: Gross Profit, Net Income, R&D are found and populated!
    assert result['revenue'] == '₹1,506 million'
    assert result['gross_profit'] == '₹800 million'
    assert result['net_income'] == '₹716 million'
    assert result['rd_expense'] == '₹150 million'


def test_task3_compound_header_is_not_equity_or_liabilities():
    parsed = parse_financial_number('23,532.55')
    sentence = 'TOTAL EQUITY AND LIABILITIES: 23,532.55'

    eq_class = _classify_metric_candidate('total_equity', sentence, 'equity', parsed)
    assert eq_class is None, 'Compound header must not be classified as total_equity'

    liab_class = _classify_metric_candidate('total_liabilities', sentence, 'liabilities', parsed)
    assert liab_class is None, 'Compound header must not be classified as total_liabilities'


def test_task3_working_capital_is_not_operating_cash_flow():
    parsed = parse_financial_number('-108')
    sentence = 'Working capital adjustments in operating cash flows: -₹108 crore'

    ocf_class = _classify_metric_candidate('operating_cash_flow', sentence, 'operating cash flow', parsed)
    assert ocf_class is None, 'Working capital adjustment must not be classified as operating_cash_flow'


def test_task3_pat_is_not_misclassified_as_revenue():
    parsed_pat = parse_financial_number('₹716.73 million')
    sentence = 'Profit after tax (PAT) was ₹716.73 million achieved on total revenue of ₹15,056.06 million'

    rev_class = _classify_metric_candidate('revenue', sentence, 'revenue', parsed_pat)
    assert rev_class is None, 'PAT amount must not be classified as revenue'


def test_task4_accounting_invariants_middleware_detects_compound_collision():
    corrupted_metrics = {
        'revenue': '₹15,056.06 million',
        'total_assets': '₹23,532.55 crore',
        'total_liabilities': '₹23,532.55 crore',
        'total_equity': '₹23,532.55 crore',
    }
    validated = validate_financial_accounting_invariants(corrupted_metrics)
    assert validated['total_assets'] == '₹23,532.55 crore'
    assert validated['total_liabilities'] is None
    assert validated['total_equity'] is None


def test_task4_accounting_invariants_middleware_preserves_valid_balance_sheet():
    valid_metrics = {
        'revenue': ' million',
        'total_assets': ' million',
        'total_liabilities': ' million',
        'total_equity': ' million',
    }
    validated = validate_financial_accounting_invariants(valid_metrics)
    assert validated['total_assets'] == ' million'
    assert validated['total_liabilities'] == ' million'
    assert validated['total_equity'] == ' million'
