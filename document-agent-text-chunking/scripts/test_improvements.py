#!/usr/bin/env python3
"""Test the improved Document Agent on the ABB report to validate the targeted improvements."""

from pathlib import Path
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from document_agent import DocumentAgent, DocumentAgentConfig

def test_improved_sections_and_metrics():
    """Test that section headings and financial metrics are improved."""
    
    # Create a temporary database for this test
    tmp = Path(tempfile.mkdtemp(prefix='improved_agent_test_'))
    pdf = Path(__file__).resolve().parent / "demo_data" / "ABB Group Mock Financial Report 2025 - Google Docs.pdf"
    
    cfg = DocumentAgentConfig(
        db_path=str(tmp / 'chroma_db'),
        collection_name='improved_test_collection',
        chunk_size=800,
        chunk_overlap=150,
        overwrite=True
    )
    agent = DocumentAgent(cfg)
    
    # Ingest the ABB report
    result = agent.ingest_document(str(pdf), analysis_id='improved-test-session')
    
    print("\n" + "="*80)
    print("IMPROVED DOCUMENT AGENT TEST RESULTS")
    print("="*80)
    print(f"\nIngestion Status: {result['status']}")
    print(f"Chunks Created: {result['chunks']}")
    print(f"Analysis ID: {result['analysis_id']}")
    
    if result['status'] != 'success':
        print(f"Error: {result.get('error')}")
        return False
    
    # Retrieve the chunks and metadata
    all_data = agent.collection.get(
        where={"analysis_id": "improved-test-session"},
        include=["metadatas", "documents"]
    )
    
    metadatas = all_data.get("metadatas", [])
    documents = all_data.get("documents", [])
    
    print(f"\nTotal Chunks Retrieved: {len(metadatas)}")
    
    # Analyze section metadata
    print("\n" + "-"*80)
    print("SECTION METADATA ANALYSIS")
    print("-"*80)
    
    section_titles = {}
    subsection_titles = {}
    for i, meta in enumerate(metadatas):
        section = meta.get("section_title", "Unknown")
        subsection = meta.get("subsection_title", "")
        
        if section not in section_titles:
            section_titles[section] = 0
        section_titles[section] += 1
        
        if subsection:
            if subsection not in subsection_titles:
                subsection_titles[subsection] = 0
            subsection_titles[subsection] += 1
    
    print(f"\nUnique Section Titles: {len(section_titles)}")
    for title, count in sorted(section_titles.items()):
        if title == "Unknown":
            print(f"  {title}: {count} chunks (should be reduced)")
        else:
            print(f"  {title}: {count} chunks")
    
    print(f"\nUnique Subsection Titles: {len(subsection_titles)}")
    for title, count in sorted(subsection_titles.items()):
        print(f"  {title}: {count} chunks")
    
    # Analyze financial metrics
    print("\n" + "-"*80)
    print("FINANCIAL METRICS ANALYSIS")
    print("-"*80)
    
    metrics_per_chunk = []
    sample_metrics = []
    
    for i, meta in enumerate(metadatas[:5]):  # Show first 5 chunks
        metrics_str = meta.get("financial_metrics", "")
        if metrics_str:
            metrics_list = [m.strip() for m in metrics_str.split(",")]
            metrics_per_chunk.append(len(metrics_list))
            sample_metrics.append({
                "chunk": i+1,
                "metrics": metrics_list,
                "section": meta.get("section_title", "Unknown")[:50]
            })
    
    print(f"\nChunks with Financial Metrics: {sum(1 for m in metadatas if m.get('financial_metrics', ''))}/{len(metadatas)}")
    print(f"\nFirst 5 Chunks Sample:")
    for sample in sample_metrics:
        print(f"\n  Chunk {sample['chunk']} (Section: {sample['section']}):")
        for metric in sample['metrics']:
            print(f"    - {metric}")
    
    # Analyze countries extraction
    print("\n" + "-"*80)
    print("COUNTRIES EXTRACTION ANALYSIS")
    print("-"*80)
    
    countries_list = []
    for meta in metadatas:
        countries = meta.get("countries", "")
        if countries:
            countries_list.append(countries)
    
    print(f"\nChunks with Countries: {len(countries_list)}/{len(metadatas)}")
    print(f"Unique Country Values:")
    unique_countries = set(countries_list)
    for country in sorted(unique_countries):
        print(f"  - {country}")
    
    if not unique_countries:
        print("  (No countries found - expected if document doesn't explicitly list them)")
    
    # Quality report
    print("\n" + "-"*80)
    print("QUALITY REPORT")
    print("-"*80)
    
    quality_report = result.get('quality_report', {})
    if quality_report:
        print(f"\nMetadata Completeness:")
        completeness = quality_report.get('metadata_completeness', {})
        for key, value in completeness.items():
            print(f"  {key}: {value}%")
    
    # Validate no regressions
    print("\n" + "-"*80)
    print("REGRESSION CHECK")
    print("-"*80)
    
    validation = quality_report.get('validation', {})
    checks = [
        ('broken_previous_links', 0, 'Previous chunk links broken'),
        ('broken_next_links', 0, 'Next chunk links broken'),
        ('duplicate_chunk_ids', 0, 'Duplicate chunk IDs'),
        ('invalid_sequences', 0, 'Invalid chunk sequences'),
    ]
    
    all_pass = True
    for key, expected, description in checks:
        actual = validation.get(key, -1)
        status = "✓ PASS" if actual == expected else "✗ FAIL"
        print(f"  {status}: {description} (expected {expected}, got {actual})")
        if actual != expected:
            all_pass = False
    
    print("\n" + "="*80)
    if all_pass:
        print("✓ ALL VALIDATION CHECKS PASSED")
    else:
        print("✗ SOME VALIDATION CHECKS FAILED")
    print("="*80)
    
    return all_pass

if __name__ == "__main__":
    success = test_improved_sections_and_metrics()
    sys.exit(0 if success else 1)
