"""Human-readable quality report for an ingested Chroma collection."""

from collections import Counter
from pathlib import Path

import chromadb

from shared_chroma_path import resolve_chroma_db_path


REQUIRED = ("analysis_id", "document_id", "source", "doc_hash", "doc_type", "chunk_index", "total_chunks", "page_number", "page_start", "page_end", "page_numbers", "company_name", "report_type", "report_year", "report_period", "section_title", "subsection_title", "semantic_tags", "financial_metrics", "is_table", "is_financial_table", "is_chart", "previous_chunk_id", "next_chunk_id")


def summarize(collection) -> None:
    data = collection.get(include=["documents", "metadatas", "embeddings"])

    def _as_list(value):
        if value is None:
            return []
        if hasattr(value, "tolist"):
            return value.tolist()
        return list(value)

    ids = _as_list(data.get("ids", []))
    documents = _as_list(data.get("documents", []))
    metadatas = _as_list(data.get("metadatas", []))
    embeddings = _as_list(data.get("embeddings", []))

    records = [{"id": chunk_id, "document": documents[index] if index < len(documents) else "", "metadata": metadatas[index] if index < len(metadatas) else {}, "embedding": embeddings[index] if index < len(embeddings) else None} for index, chunk_id in enumerate(ids)]
    
    # Group records by analysis_id
    analyses = {}
    for record in records:
        analysis_id = record["metadata"].get("analysis_id", "unknown")
        if analysis_id not in analyses:
            analyses[analysis_id] = []
        analyses[analysis_id].append(record)
    
    metadata_count = sum(sum(field in record["metadata"] and record["metadata"][field] not in ("", None) for field in REQUIRED) for record in records)
    possible = len(records) * len(REQUIRED)
    missing = Counter(field for record in records for field in REQUIRED if field not in record["metadata"] or record["metadata"][field] in ("", None))
    document_hashes = Counter((record["metadata"].get("analysis_id", ""), record["metadata"].get("document_id", ""), record["metadata"].get("doc_hash", "")) for record in records)
    duplicate_chunk_ids = [value for value, count in Counter(record["id"] for record in records).items() if value and count > 1]
    ids_set = set(ids)
    broken_links = sum(1 for record in records for field in ("previous_chunk_id", "next_chunk_id") if record["metadata"].get(field) and record["metadata"][field] not in ids_set)
    tags = Counter(tag for record in records for tag in str(record["metadata"].get("semantic_tags", "")).split(",") if tag)
    metrics = Counter(metric for record in records for metric in str(record["metadata"].get("financial_metrics", "")).split(",") if metric)
    sizes = [len(record["document"].split()) for record in records]
    dimensions = sorted({len(record["embedding"]) for record in records if record["embedding"] is not None})
    
    print(f"\n{'='*80}")
    print(f"Collection: {collection.name}")
    print(f"{'='*80}")
    print(f"Total Chunks: {len(records)}")
    print(f"Total Documents: {len({r['metadata'].get('doc_hash') for r in records if r['metadata'].get('doc_hash')})}")
    print(f"Total Analysis Sessions: {len(analyses)}")
    print(f"Companies: {', '.join(sorted({r['metadata'].get('company_name') for r in records if r['metadata'].get('company_name')})) or '<unknown>'}")
    print(f"Reports: {', '.join(sorted({r['metadata'].get('report_type') for r in records if r['metadata'].get('report_type')})) or '<unknown>'}")
    print(f"Years: {', '.join(sorted({str(r['metadata'].get('report_year') or r['metadata'].get('financial_year')) for r in records if r['metadata'].get('report_year') or r['metadata'].get('financial_year')})) or '<unknown>'}")
    print(f"Metadata completeness: {metadata_count / possible:.1%}" if possible else "Metadata completeness: 0.0%")
    print(f"Missing metadata: {dict(missing)}")
    print(f"Duplicate chunk IDs: {duplicate_chunk_ids or 'none'}")
    print(f"Document hash references: {sum(document_hashes.values())}")
    print(f"Broken previous/next links: {broken_links}")
    print(f"Top semantic tags: {tags.most_common(10)}")
    print(f"Top financial metrics: {metrics.most_common(10)}")
    print(f"Tables: {sum(r['metadata'].get('is_table') is True or r['metadata'].get('contains_table') == 'true' for r in records)}")
    print(f"Financial tables: {sum(r['metadata'].get('is_financial_table') is True or r['metadata'].get('contains_financial_table') == 'true' for r in records)}")
    print(f"Charts: {sum(r['metadata'].get('is_chart') is True or r['metadata'].get('contains_chart') == 'true' for r in records)}")
    print(f"Average chunk size: {sum(sizes) / len(sizes):.1f} words" if sizes else "Average chunk size: 0 words")
    print(f"Embedding dimensions: {dimensions or 'N/A'}")
    
    # Analysis-level breakdown
    print(f"\n{'='*80}")
    print(f"BREAKDOWN BY ANALYSIS SESSION")
    print(f"{'='*80}")
    for idx, (analysis_id, analysis_records) in enumerate(sorted(analyses.items()), 1):
        analysis_chunks = len(analysis_records)
        analysis_docs = len({r['metadata'].get('doc_hash') for r in analysis_records if r['metadata'].get('doc_hash')})
        analysis_sources = sorted({r['metadata'].get('source') for r in analysis_records if r['metadata'].get('source')})
        analysis_companies = sorted({r['metadata'].get('company_name') for r in analysis_records if r['metadata'].get('company_name')})
        
        print(f"\n[Analysis {idx}] UUID: {analysis_id}")
        print(f"  Chunks: {analysis_chunks}")
        print(f"  Documents: {analysis_docs}")
        print(f"  Sources: {', '.join(analysis_sources) or '<unknown>'}")
        print(f"  Companies: {', '.join(analysis_companies) or '<unknown>'}")
        print(f"  Tables: {sum(r['metadata'].get('is_table') is True or r['metadata'].get('contains_table') == 'true' for r in analysis_records)}")
        print(f"  Financial Tables: {sum(r['metadata'].get('is_financial_table') is True or r['metadata'].get('contains_financial_table') == 'true' for r in analysis_records)}")


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    db_path = resolve_chroma_db_path(__file__, project_root.parent).resolve()
    client = chromadb.PersistentClient(path=str(db_path))
    collection_name = "financial_research_v1"
    if collection_name not in [item.name for item in client.list_collections()]:
        print(f"Collection '{collection_name}' was not found.")
        raise SystemExit(1)
    summarize(client.get_collection(collection_name))
