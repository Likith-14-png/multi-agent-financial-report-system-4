import pandas as pd

def load_company(file):
    return pd.read_csv(file)

def compare_companies(file1, file2):
    company1 = load_company(file1)
    company2 = load_company(file2)

    comparison = pd.merge(
        company1,
        company2,
        on="Metric",
        suffixes=("_Company1", "_Company2")
    )

    return comparison