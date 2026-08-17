#!/usr/bin/env python3
"""Inspect ABB document structure for section headings."""

from pathlib import Path
import sys
import re

sys.path.insert(0, str(Path(__file__).resolve().parent))
from document_agent import DocumentAgent

pdf = Path(__file__).resolve().parent / "demo_data" / "ABB Group Mock Financial Report 2025 - Google Docs.pdf"
agent = DocumentAgent()
text, pages = agent.extract_text(pdf)

print("=== DOCUMENT START (first 1500 chars) ===")
print(text[:1500])
print("\n=== PAGES AND STRUCTURE ===")

for i, page in enumerate(pages[:5]):
    print(f"\n--- Page {page['page_number']} (first 400 chars) ---")
    print(page["text"][:400])
    print(f"Content length: {page['content_length']}")

# Check what section headings exist
print("\n=== POTENTIAL SECTION HEADINGS ===")
for page in pages[:10]:
    lines = [line.strip() for line in page["text"].splitlines() if line.strip()]
    for line in lines[:5]:
        # Look for lines that might be headings
        if 5 <= len(line.split()) <= 12 and not line.endswith(('.', '!', '?')):
            if re.search(r'[A-Z][a-z]', line):
                print(f"  {line}")
