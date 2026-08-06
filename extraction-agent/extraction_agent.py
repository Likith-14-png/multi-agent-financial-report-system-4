# Demo Extraction Agent
# Reads financial metrics from sample_report.txt
import re
import json

# Read the report
with open("sample_report.txt", "r", encoding="utf-8") as file:
    report = file.read()

# Function to extract values
def extract(pattern):
    match = re.search(pattern, report)
    return match.group(1).strip() if match else "Not Found"

# Extract financial metrics
data = {
    "Company": extract(r"Company:\s*(.*)"),
    "Revenue": extract(r"Revenue:\s*(.*)"),
    "Net Income": extract(r"Net Income:\s*(.*)"),
    "Total Assets": extract(r"Total Assets:\s*(.*)"),
    "Total Liabilities": extract(r"Total Liabilities:\s*(.*)"),
    "Cash Flow": extract(r"Cash Flow from Operations:\s*(.*)"),
    "EPS": extract(r"Earnings Per Share \(EPS\):\s*(.*)")
}

# Display extracted data
print("\n===== Extracted Financial Metrics =====\n")

for key, value in data.items():
    print(f"{key}: {value}")

# Save as JSON
with open("output.json", "w", encoding="utf-8") as json_file:
    json.dump(data, json_file, indent=4)

print("\n✅ Data saved to output.json")