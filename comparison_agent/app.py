import streamlit as st
import pandas as pd
import plotly.express as px
from compare import ComparisonAgent, compare_companies_csv
from utils import better_company

st.set_page_config(page_title="Financial Comparison Agent", layout="wide")
st.title("📊 Financial Comparison Agent")

tab1, tab2 = st.tabs(["📁 Local CSV Comparison", "🤖 Multi-Agent Pipeline Mode"])

with tab1:
    st.subheader("Side-by-Side File Comparison")
    col1, col2 = st.columns(2)
    with col1:
        file1 = st.text_input("Company 1 CSV Path", "data/apple.csv")
    with col2:
        file2 = st.text_input("Company 2 CSV Path", "data/microsoft.csv")

    if st.button("Run CSV Benchmark"):
        try:
            df = compare_companies_csv(file1, file2)
            st.subheader("Comparison Table")
            st.dataframe(df, use_container_width=True)

            # Bar chart
            fig = px.bar(
                df,
                x="Metric",
                y=["Value_Company1", "Value_Company2"],
                barmode="group",
                title="Metrics Comparison"
            )
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Performance Summary")
            for _, row in df.iterrows():
                winner = better_company(row["Metric"], row["Value_Company1"], row["Value_Company2"], "Apple", "Microsoft")
                st.write(f"• **{row['Metric']}**: {winner}")
        except Exception as e:
            st.error(f"Error loading files: {e}")

with tab2:
    st.subheader("Simulated Extraction Agent Input")
    sample_payload = [
        {
            "analysis_id": "sess_001",
            "document_id": "doc_apple",
            "company_name": "Apple",
            "report_year": 2023,
            "chunk_id": "chunk_01",
            "metrics": {"Revenue": 383285, "Net Profit": 99803, "EPS": 6.13, "ROE": 160.0, "Debt": 111088}
        },
        {
            "analysis_id": "sess_001",
            "document_id": "doc_msft",
            "company_name": "Microsoft",
            "report_year": 2023,
            "chunk_id": "chunk_02",
            "metrics": {"Revenue": 211915, "Net Profit": 88136, "EPS": 11.8, "ROE": 38.5, "Debt": 59578}
        }
    ]
    st.json(sample_payload)

    if st.button("Process Extraction Payload"):
        agent = ComparisonAgent()
        parsed = agent.load_from_extraction_output(sample_payload)
        result = agent.compare_companies(parsed)
        st.success("Comparison Generated for Report Agent!")
        st.json(result)
        # Comparison Agent module