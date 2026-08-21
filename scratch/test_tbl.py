import sys, re
sys.path.insert(0, ".")
from research_agent import parse_numeric_value

doc = """Revenue & Segment Analysis (In millions)

Total Software: $29,962 million
2024: $27,085 million

Total Consulting: $21,055 million
2024: $20,692 million

Total Infrastructure: $15,718 million
2024: $14,020 million

Management Discussion and Analysis — Segment Growth Performance

Software revenue grew 10.6% year-over-year driven by Hybrid Cloud and Red Hat expansion. Consulting revenue increased 1.8% reflecting steady business transformation demand. Infrastructure revenue expanded 12.1% reflecting strong mainframe adoption and hybrid infrastructure growth."""

lines = [line.strip() for line in doc.splitlines() if line.strip()]
row_patterns = []

# Step 1: Pipe-separated
for line in lines:
    m_pipe = re.match(r"^([^:\d\|]+?)\s*:\s*(?:202\d|201\d)?\s*[:\s]*\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)?\s*\|\s*(?:202\d|201\d)?\s*[:\s]*\$?\s*([\d,]+(?:\.\d+)?)", line, re.I)
    if m_pipe:
        label = m_pipe.group(1).strip()
        v1 = parse_numeric_value(m_pipe.group(2))
        v2 = parse_numeric_value(m_pipe.group(3))
        if v1 is not None and v2 is not None and len(label) >= 2:
            row_patterns.append((label, [v1, v2]))

# Step 2: Single-line multi-numeric table rows (e.g. "Total Software $29,962 $27,085")
if not row_patterns:
    for line in lines:
        if len(line) > 100:
            continue
        m_num = re.findall(r"(?:\$?\s*\(?[\d,]+(?:\.\d+)?\)?\s*%?|\(?[\d,]+(?:\.\d+)?\s*(?:million|billion)\)?)", line)
        m_num_clean = [n for n in m_num if n.strip("$ ,%") not in ["2023", "2024", "2025", "2026", "2022", "2021"]]
        if len(m_num_clean) >= 2:
            label = re.sub(r"(?:\$?\s*\(?[\d,]+(?:\.\d+)?\)?\s*%?|\(?[\d,]+(?:\.\d+)?\s*(?:million|billion)\)?).*", "", line).strip()
            label = re.sub(r"[:\-\|]+$", "", label).strip()
            is_inv = (
                len(label) > 40 or
                any(v in label.lower() for v in ["grew", "increased", "declined", "expanded", "decreased", "reflecting", "driven", "primarily", "attribut", "due to", "because", "benefit", "represent"]) or
                label.lower().startswith(("table", "item", "page", "note", "consisting", "consolidated", "statement", "total debt", "short-term", "long-term", "free cash", "diluted", "net cash"))
            )
            if not is_inv and label:
                parsed_vals = []
                for raw_val in m_num_clean:
                    v = parse_numeric_value(raw_val)
                    if v is not None:
                        parsed_vals.append(v)
                if len(parsed_vals) >= 2:
                    row_patterns.append((label, parsed_vals[:2]))

# Step 3: Multiline vertical table structures
if not row_patterns:
    i = 0
    while i < len(lines):
        line = lines[i]
        m_with_val = re.match(r"^(?:Total\s+)?([A-Za-z0-9\s&/\-]+?)\s*[:\-]\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(?:million|billion)?$", line, re.I)
        m_label_only = re.match(r"^(?:Total\s+)?([A-Za-z0-9\s&/\-]+?)\s*[:\-]?$", line, re.I)

        cand_label = None
        vals = []

        if m_with_val:
            cand_label = m_with_val.group(1).strip()
            val1 = parse_numeric_value(m_with_val.group(2))
            if val1 is not None:
                vals.append(val1)
        elif m_label_only:
            cand_label = m_label_only.group(1).strip()

        if cand_label:
            j = i + 1
            while j < min(len(lines), i + 4) and len(vals) < 2:
                next_line = lines[j]
                num_matches = re.findall(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)", next_line)
                for nm in num_matches:
                    if nm and nm not in ["2023", "2024", "2025", "2026", "2022", "2021"]:
                        v = parse_numeric_value(nm)
                        if v is not None and v > 0:
                            vals.append(v)
                            if len(vals) == 2:
                                break
                j += 1

            cand_low = cand_label.lower()
            is_invalid_label = (
                cand_low.startswith(("table", "item", "page", "note", "consisting", "consolidated", "statement", "total debt", "short-term", "long-term", "free cash", "diluted", "net cash")) or
                any(v in cand_low for v in ["grew", "increased", "declined", "expanded", "decreased", "reflecting", "driven", "primarily", "attribut", "due to", "because", "benefit", "represent"]) or
                "cash flows" in cand_low or
                "highlights" in cand_low or
                "summary" in cand_low or
                "balance sheet" in cand_low or
                "assets" in cand_low or
                "liabilities" in cand_low or
                "equity" in cand_low
            )
            if len(vals) >= 2 and not is_invalid_label:
                if len(cand_label) > 2 and not any(r[0].lower() == cand_label.lower() for r in row_patterns):
                    row_patterns.append((cand_label, vals[:2]))
                    i = j - 1
        i += 1

print("Final row_patterns:", row_patterns)
