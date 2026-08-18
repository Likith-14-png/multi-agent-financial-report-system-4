"""
compare.py - Comparison Agent
Handles cross-company and multi-year benchmarking, structured metadata tracking,
and provides inputs for the Report Agent and Streamlit UI.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


@dataclass
class CompanyFinancialData:
    analysis_id: str
    document_id: str
    company_name: str
    report_year: int
    metrics: Dict[str, float] = field(default_factory=dict)
    chunk_id: Optional[str] = None


class ComparisonAgent:
    STANDARD_METRICS = [
        "Revenue", "Operating Income", "Net Profit", "Assets",
        "Liabilities", "Debt", "EPS", "Profit Margin", "ROE"
    ]

    def load_from_extraction_output(self, extraction_payload: List[Dict[str, Any]]) -> List[CompanyFinancialData]:
        """Parses structured JSON payloads received from Kusuma's Extraction Agent."""
        parsed = []
        for item in extraction_payload:
            comp = CompanyFinancialData(
                analysis_id=item.get("analysis_id", "analysis_default"),
                document_id=item.get("document_id", "doc_default"),
                company_name=item.get("company_name", "Unknown"),
                report_year=int(item.get("report_year", 2024)),
                metrics=item.get("metrics", {}),
                chunk_id=item.get("chunk_id", None)
            )
            parsed.append(comp)
        return parsed

    def compare_companies(self, companies_data: List[CompanyFinancialData]) -> Dict[str, Any]:
        """Compares multiple companies/years across financial metrics."""
        if not companies_data:
            return {"error": "No company data provided."}

        records = []
        for comp in companies_data:
            row = {
                "company_name": comp.company_name,
                "report_year": comp.report_year,
                "analysis_id": comp.analysis_id,
                "document_id": comp.document_id,
            }
            row.update(comp.metrics)
            records.append(row)

        df = pd.DataFrame(records)
        summary_insights = []

        if "Net Profit" in df.columns and len(df) >= 2:
            top_profit = df.loc[df["Net Profit"].idxmax()]
            summary_insights.append(f"{top_profit['company_name']} led in Net Profit with {top_profit['Net Profit']:,}.")

        if "ROE" in df.columns and len(df) >= 2:
            top_roe = df.loc[df["ROE"].idxmax()]
            summary_insights.append(f"{top_roe['company_name']} achieved the highest ROE at {top_roe['ROE']}%.")

        return {
            "analysis_id": companies_data[0].analysis_id if companies_data else None,
            "companies_compared": [c.company_name for c in companies_data],
            "years_compared": list(set(c.report_year for c in companies_data)),
            "comparison_table": df.to_dict(orient="records"),
            "summary_insights": summary_insights,
            "metadata_audit": [
                {"company_name": c.company_name, "document_id": c.document_id, "chunk_id": c.chunk_id}
                for c in companies_data
            ]
        }

# --- Legacy Compatibility Function for Local CSV Testing ---
def load_company(file_path: str) -> pd.DataFrame:
    return pd.read_csv(file_path)

def compare_companies_csv(file1: str, file2: str) -> pd.DataFrame:
    comp1 = load_company(file1)
    comp2 = load_company(file2)
    return pd.merge(comp1, comp2, on="Metric", suffixes=("_Company1", "_Company2"))