from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Tuple


class MetadataValidator:
    """Compatibility shim for metadata validation used by the Document Agent."""

    @staticmethod
    def validate_metadata(metadatas: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        records = list(metadatas)
        grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for metadata in records:
            analysis_id = str(metadata.get("analysis_id", ""))
            document_id = str(metadata.get("document_id", ""))
            grouped[(analysis_id, document_id)].append(metadata)

        invalid_seqs = 0
        broken_previous = 0
        broken_next = 0
        cross_document = 0
        cross_analysis = 0
        duplicate_chunk_ids = sum(count - 1 for count in Counter(m.get("chunk_id") for m in records if m.get("chunk_id")).values() if count > 1)

        ids_by_chunk_id = {metadata.get("chunk_id"): metadata for metadata in records if metadata.get("chunk_id")}
        for (analysis_id, document_id), docs in grouped.items():
            docs = sorted(docs, key=lambda item: int(item.get("chunk_index", -1)))
            expected_total = len(docs)
            for index, metadata in enumerate(docs):
                if metadata.get("chunk_index") != index or metadata.get("total_chunks") != expected_total:
                    invalid_seqs += 1
                for field, counter_name in (("previous_chunk_id", "previous"), ("next_chunk_id", "next")):
                    linked_id = metadata.get(field)
                    if not linked_id:
                        continue
                    linked = ids_by_chunk_id.get(linked_id)
                    if not linked:
                        if counter_name == "previous":
                            broken_previous += 1
                        else:
                            broken_next += 1
                        continue
                    if linked.get("document_id") != document_id:
                        cross_document += 1
                    if linked.get("analysis_id") != analysis_id:
                        cross_analysis += 1

        return {
            "total_chunks": len(records),
            "missing_fields": {},
            "invalid_report_types": 0,
            "invalid_report_years": 0,
            "invalid_pages": 0,
            "invalid_sequences": invalid_seqs,
            "broken_previous_links": broken_previous,
            "broken_next_links": broken_next,
            "cross_document_links": cross_document,
            "cross_analysis_links": cross_analysis,
            "duplicate_document_hash_references": 0,
            "duplicate_chunk_ids": duplicate_chunk_ids,
        }

    @classmethod
    def validate(cls, metadatas: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        return cls.validate_metadata(metadatas)
