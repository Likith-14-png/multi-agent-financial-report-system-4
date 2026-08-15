"""
utils.py - Comparison evaluation helpers
"""

def better_company(metric_name: str, val1: float, val2: float, comp1_name: str = "Company 1", comp2_name: str = "Company 2") -> str:
    """Evaluates which company performed better given the metric type."""
    # For Debt and Liabilities, lower values are generally healthier
    lower_is_better = ["Debt", "Liabilities", "Total Liabilities", "Operating Expenses"]

    if metric_name in lower_is_better:
        if val1 < val2:
            return f"{comp1_name} (Lower/Healthier)"
        elif val2 < val1:
            return f"{comp2_name} (Lower/Healthier)"
        return "Equal"
    else:
        if val1 > val2:
            return comp1_name
        elif val2 > val1:
            return comp2_name
        return "Equal"