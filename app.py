import streamlit as st
import plotly.express as px
from compare import compare_companies

st.set_page_config(page_title="Comparison Agent", layout="wide")

st.title("📊 Financial Comparison Agent")

comparison = compare_companies(
    "data/apple.csv",
    "data/microsoft.csv"
)

st.subheader("Comparison Table")
st.dataframe(comparison)

fig = px.bar(
    comparison,
    x="Metric",
    y=["Value_Company1", "Value_Company2"],
    barmode="group",
    title="Company Comparison"
)

st.plotly_chart(fig)

st.subheader("Summary")

for _, row in comparison.iterrows():
    if row["Value_Company1"] > row["Value_Company2"]:
        st.write(f"✅ Apple performs better in **{row['Metric']}**")
    elif row["Value_Company2"] > row["Value_Company1"]:
        st.write(f"✅ Microsoft performs better in **{row['Metric']}**")
    else:
        st.write(f"➖ Both companies are equal in **{row['Metric']}**")