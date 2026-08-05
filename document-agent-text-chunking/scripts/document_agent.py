#!/usr/bin/env python3
"""Generic, evidence-based ingestion engine for PDF and TXT financial documents."""

from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from shared_chroma_path import resolve_chroma_db_path

try:
    import PyPDF2
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError as exc:
    PyPDF2 = None  # type: ignore[assignment]
    chromadb = None  # type: ignore[assignment]
    embedding_functions = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

logger = logging.getLogger("DocumentAgent")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

SUPPORTED_EXTENSIONS = {".pdf", ".txt"}


@dataclass
class DocumentAgentConfig:
    db_path: str = "./chroma_db"
    collection_name: str = "financial_research_v1"
    embedding_model_name: str = "all-MiniLM-L6-v2"
    chunk_size: int = 450
    chunk_overlap: int = 100
    batch_size: int = 100
    overwrite: bool = False
    max_workers: int = 4
    enable_document_versioning: bool = False
    history_log_path: Optional[str] = None
    ocr_callback: Optional[Callable[[Path], Tuple[str, List[Dict[str, Any]]]]] = None


@dataclass
class IngestionResult:
    status: str
    document: str
    analysis_id: str
    chunks: int
    time_seconds: float
    collection: str
    duplicates_skipped: bool
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = dict(self.__dict__)
        result["time_seconds"] = round(self.time_seconds, 2)
        return result


def discover_supported_files(directory_path: str | Path) -> List[Path]:
    path = Path(directory_path)
    if path.is_file():
        return [path] if path.suffix.lower() in SUPPORTED_EXTENSIONS else []
    if not path.is_dir():
        return []
    return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)


class DocumentAgent:
    """Ingest reports with page-aware chunks and evidence-only metadata."""

    def __init__(self, config: Optional[DocumentAgentConfig] = None) -> None:
        if chromadb is None or embedding_functions is None:
            raise ImportError("Missing dependency: install PyPDF2 chromadb sentence-transformers") from _IMPORT_ERROR
        self.config = config or DocumentAgentConfig()
        db_path = Path(self.config.db_path)
        if not db_path.is_absolute():
            db_path = (Path(__file__).resolve().parent.parent / db_path).resolve()
        self.client = chromadb.PersistentClient(path=str(db_path))
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=self.config.embedding_model_name)
        self.collection = self.client.get_or_create_collection(
            name=self.config.collection_name,
            embedding_function=self.embedding_fn,
            metadata={"description": "Generic financial research document chunks"},
        )

    def generate_embedding(self, text: str) -> List[float]:
        return list(self.embedding_fn([text])[0])

    def generate_document_hash(self, file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def create_analysis(self) -> str:
        return str(uuid.uuid4())

    def document_exists(self, doc_hash: str, analysis_id: Optional[str] = None) -> bool:
        try:
            found = self.collection.get(where={"doc_hash": doc_hash}, limit=1, include=["metadatas"])
            return bool(found.get("ids"))
        except Exception:
            found = self.collection.get(include=["metadatas"])
            return any(m.get("doc_hash") == doc_hash for m in found.get("metadatas", []) or [] if isinstance(m, dict))

    def _source_chunk_ids(self, source: str) -> List[str]:
        """Return stored IDs for one source so overwrite can replace that version."""
        try:
            found = self.collection.get(where={"source": source}, include=["metadatas"])
            return list(found.get("ids", []) or [])
        except Exception:
            return []

    @staticmethod
    def clean_text(text: str) -> str:
        text = "".join(c for c in text if c.isprintable() or c in "\n\t")
        text = re.sub(r"[ \t]+", " ", text)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    def _resolve_file_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute() or path.exists():
            return path
        base = Path(__file__).resolve().parent
        for candidate in (base / path, base / "demo_data" / path.name, base.parent / path, base.parent / "demo_data" / path.name):
            if candidate.exists():
                return candidate
        return path

    def _remove_repeated_margins(self, pages: List[str]) -> List[str]:
        if len(pages) < 3:
            return pages
        lines = [page.splitlines() for page in pages]
        counts: Dict[str, int] = {}
        for page in lines:
            for line in {item.strip() for item in page[:3] + page[-3:] if item.strip()}:
                counts[line] = counts.get(line, 0) + 1
        repeated = {line for line, count in counts.items() if count >= max(3, len(pages) // 2)}
        return ["\n".join(line for line in page if line.strip() not in repeated) for page in lines]

    @staticmethod
    def _token_count(text: str) -> int:
        return len(text.split())

    def _page_has_searchable_text(self, page: Any) -> bool:
        page_text = page.extract_text() or ""
        return bool(page_text.strip()) and len(page_text.split()) >= 5

    def _extract_page_text(self, page: Any) -> str:
        return self.clean_text(page.extract_text() or "")

    def _split_large_narrative_block(self, block: str) -> List[str]:
        if self._token_count(block) <= self.config.chunk_size:
            return [block]
        sentences = re.split(r"(?<=[.!?])\s+", block)
        chunks: List[str] = []
        current: List[str] = []
        word_count = 0
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            sentence_words = sentence.split()
            if current and word_count + len(sentence_words) > self.config.chunk_size:
                chunks.append(" ".join(current).strip())
                current = []
                word_count = 0
            current.append(sentence)
            word_count += len(sentence_words)
        if current:
            chunks.append(" ".join(current).strip())
        return [chunk for chunk in chunks if chunk]

    def _split_table_row(self, line: str) -> List[str]:
        if "|" in line:
            return [cell.strip() for cell in re.split(r"\s*\|\s*", line)]
        if "\t" in line:
            return [cell.strip() for cell in line.split("\t")]
        return [cell.strip() for cell in re.split(r"\s{2,}", line) if cell.strip()]

    def _split_table_block(self, block: str) -> List[str]:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or self._token_count(block) <= self.config.chunk_size:
            return [block]
        header_rows = [lines[0]]
        chunks: List[str] = []
        current_rows = header_rows.copy()
        current_tokens = sum(self._token_count(row) for row in current_rows)
        for line in lines[1:]:
            line_tokens = self._token_count(line)
            if current_rows and current_tokens + line_tokens > self.config.chunk_size and len(current_rows) > len(header_rows):
                chunks.append("\n".join(current_rows))
                current_rows = header_rows.copy()
                current_tokens = sum(self._token_count(row) for row in current_rows)
            current_rows.append(line)
            current_tokens += line_tokens
        if current_rows:
            chunks.append("\n".join(current_rows))
        return chunks

    def _is_searchable_pdf(self, reader: Any, sample_pages: int = 5) -> bool:
        pages = list(reader.pages)[: min(sample_pages, len(reader.pages))] if getattr(reader, "pages", None) else []
        if not pages:
            return False
        searchable_pages = sum(1 for page in pages if self._page_has_searchable_text(page))
        return searchable_pages >= max(1, len(pages) // 2)

    def _extract_with_ocr(self, path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        if not self.config.ocr_callback:
            raise ValueError("OCR required but no OCR callback is configured")
        logger.info("OCR required for %s", path.name)
        text, pages = self.config.ocr_callback(path)
        if not text:
            raise ValueError("OCR returned no text")
        records: List[Dict[str, Any]] = []
        for index, page in enumerate(pages, 1):
            page_text = self.clean_text(page["text"] if isinstance(page, dict) else str(page))
            if page_text:
                records.append({"page_number": page.get("page_number", index) if isinstance(page, dict) else index, "text": page_text, "content_length": len(page_text)})
        if not records:
            raise ValueError("OCR produced no readable pages")
        return "\n\n".join(record["text"] for record in records), records

    def _extract_pdf_text(self, path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        if PyPDF2 is None:
            raise ImportError("PyPDF2 is required for PDF ingestion") from _IMPORT_ERROR
        logger.info("Extracting text from PDF %s", path.name)
        try:
            with path.open("rb") as handle:
                reader = PyPDF2.PdfReader(handle)
                if getattr(reader, "is_encrypted", False):
                    try:
                        if not reader.decrypt(""):
                            raise ValueError("encrypted PDF requires a password")
                    except Exception as exc:
                        raise ValueError("encrypted PDF cannot be read") from exc

                searchable = self._is_searchable_pdf(reader)
                if searchable:
                    logger.info("Detecting PDF type for %s: searchable text", path.name)
                    raw_pages = [self._extract_page_text(page) for page in reader.pages]
                    if not any(page.strip() for page in raw_pages) and self.config.ocr_callback:
                        logger.info("Searchable PDF yielded no text, falling back to OCR for %s", path.name)
                        return self._extract_with_ocr(path)
                else:
                    logger.info("Detecting PDF type for %s: scanned document", path.name)
                    return self._extract_with_ocr(path)
        except Exception as exc:
            raise ValueError(f"Unable to open or read PDF: {exc}") from exc

        pages = self._remove_repeated_margins(raw_pages)
        records = []
        for number, page in enumerate(pages, 1):
            cleaned = self.clean_text(page)
            if cleaned:
                records.append({"page_number": number, "text": cleaned, "content_length": len(cleaned)})
        if not records and self.config.ocr_callback:
            logger.info("PDF text extraction produced no readable pages, falling back to OCR for %s", path.name)
            return self._extract_with_ocr(path)
        return "\n\n".join(record["text"] for record in records), records

    def _extract_pdf_metadata(self, path: Path) -> Dict[str, str]:
        metadata: Dict[str, str] = {}
        if PyPDF2 is None:
            return metadata
        with path.open("rb") as handle:
            reader = PyPDF2.PdfReader(handle)
            raw = reader.metadata or {}
        for raw_key, clean_key in (("/Title", "title"), ("/Author", "author"), ("/Subject", "subject"), ("/Creator", "creator"), ("/Producer", "producer")):
            value = raw.get(raw_key) or raw.get(clean_key)
            if value:
                metadata[clean_key] = self.clean_text(str(value))
        return metadata

    def _top_text_evidence(self, text: str, pages: List[Dict[str, Any]]) -> str:
        if not pages:
            return text[:16000]
        # use only the first 1-3 pages as the primary evidence window for
        # document-level metadata extraction (company, title, dates)
        first_pages = "\n\n".join(page["text"] for page in pages[:min(3, len(pages))])
        return (first_pages + "\n\n" + text)[:16000]

    def _extract_text_file(self, path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        text = self.clean_text(path.read_text(encoding="utf-8", errors="ignore"))
        return text, ([{"page_number": 1, "text": text, "content_length": len(text)}] if text else [])

    def extract_text(self, file_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        extension = file_path.suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension: {extension}")
        return self._extract_pdf_text(file_path) if extension == ".pdf" else self._extract_text_file(file_path)

    def chunk_text(self, text: str) -> List[str]:
        """Prefer paragraph and sentence boundaries, retaining word overlap."""
        if not text:
            return []
        blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
        chunks: List[str] = []
        current: List[str] = []
        word_count = 0
        for block in blocks:
            sentences = [block] if len(block.split()) <= self.config.chunk_size else re.split(r"(?<=[.!?])\s+", block)
            for sentence in sentences:
                sentence_words = sentence.split()
                if current and word_count + len(sentence_words) > self.config.chunk_size:
                    previous = "\n\n".join(current)
                    chunks.append(previous)
                    overlap = " ".join(previous.split()[-self.config.chunk_overlap:])
                    current, word_count = ([overlap] if overlap else []), len(overlap.split())
                current.append(sentence)
                word_count += len(sentence_words)
        if current:
            chunks.append("\n\n".join(current))
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    def _normalize_table_block(self, block: str) -> str:
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        if not lines:
            return block
        normalized_rows: List[str] = []
        for line in lines:
            cells = self._split_table_row(line)
            if len(cells) > 1:
                normalized_rows.append(" | ".join(cells))
            else:
                normalized_rows.append(line)
        return "\n".join(normalized_rows)

    def _chunk_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Chunk logical blocks while preserving tables and section boundaries."""
        blocks: List[Tuple[str, int, str, str, str]] = []
        current_section_title = ""
        current_section_type = "other"

        for page in pages:
            page_number = page["page_number"]
            raw_blocks = [block.strip() for block in re.split(r"\n\s*\n", page["text"]) if block.strip()]
            index = 0
            while index < len(raw_blocks):
                block = raw_blocks[index]
                kind = self._logical_block_type(block)
                if kind == "heading":
                    heading_title, heading_type = self._extract_section_heading_and_type(block)
                    if heading_title:
                        current_section_title = heading_title
                        current_section_type = heading_type
                    elif len(block.split()) <= 10:
                        current_section_title = self._normalize_heading(block)
                        current_section_type = "other"
                    if index + 1 < len(raw_blocks):
                        block = f"{block}\n\n{raw_blocks[index + 1]}"
                        index += 1
                        kind = "narrative"
                if kind == "table":
                    normalized = self._normalize_table_block(block)
                    for table_block in self._split_table_block(normalized):
                        blocks.append((table_block, page_number, "table", current_section_title, current_section_type))
                else:
                    blocks.append((block, page_number, kind, current_section_title, current_section_type))
                index += 1

        chunks: List[Dict[str, Any]] = []
        current: List[str] = []
        current_pages: List[int] = []
        current_types: List[str] = []
        current_section_title = ""
        current_section_type = "other"
        word_count = 0

        for block, page_number, block_type, block_section_title, block_section_type in blocks:
            if block_type == "table":
                if current:
                    chunks.append({
                        "text": "\n\n".join(current).strip(),
                        "page_numbers": sorted(set(current_pages)),
                        "block_types": sorted(set(current_types)),
                        "section_title": current_section_title,
                        "section_type": current_section_type,
                    })
                    current = []
                    current_pages = []
                    current_types = []
                    word_count = 0
                chunks.append({
                    "text": block.strip(),
                    "page_numbers": [page_number],
                    "block_types": ["table"],
                    "section_title": block_section_title,
                    "section_type": block_section_type,
                })
                continue

            sentences = [block]
            if block_type == "narrative" and self._token_count(block) > self.config.chunk_size:
                sentences = self._split_large_narrative_block(block)
            for sentence in sentences:
                sentence_words = sentence.split()
                atomic = block_type in {"list", "heading", "note"}
                if current and (word_count + len(sentence_words) > self.config.chunk_size or atomic):
                    chunks.append({
                        "text": "\n\n".join(current).strip(),
                        "page_numbers": sorted(set(current_pages)),
                        "block_types": sorted(set(current_types)),
                        "section_title": current_section_title,
                        "section_type": current_section_type,
                    })
                    overlap = " ".join("\n\n".join(current).split()[-self.config.chunk_overlap:])
                    current = [overlap] if overlap and not atomic else []
                    current_pages = [current_pages[-1]] if overlap and not atomic else []
                    current_types = ["narrative"] if overlap and not atomic else []
                    word_count = len(overlap.split())
                if block_section_title:
                    current_section_title = block_section_title
                    current_section_type = block_section_type
                current.append(sentence)
                current_pages.append(page_number)
                current_types.append(block_type)
                word_count += len(sentence_words)
        if current:
            chunks.append({
                "text": "\n\n".join(current).strip(),
                "page_numbers": sorted(set(current_pages)),
                "block_types": sorted(set(current_types)),
                "section_title": current_section_title,
                "section_type": current_section_type,
            })
        logger.info("Created %d chunks from %d pages", len(chunks), len(pages))
        return chunks

    @staticmethod
    def _logical_block_type(block: str) -> str:
        """Classify layout-preserving blocks without interpreting their values."""
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            return "narrative"
        if re.match(r"^(?:[-*•▪◦]|\(?\d{1,3}[.)])\s+", lines[0]):
            return "list"
        table_line = any("|" in line or "\t" in line or len(re.split(r"\s{2,}", line)) >= 3 for line in lines)
        numeric_rows = sum(bool(re.search(r"(?:\(?[$€£₹]?\d[\d,]*(?:\.\d+)?%?\)?|\b\d{4}\b)", line)) for line in lines)
        if len(lines) >= 2 and table_line and numeric_rows >= 2:
            return "table"
        if len(lines) >= 2 and numeric_rows >= 3 and table_line:
            return "table"
        if re.match(r"^(?:note|notes|footnote|source)\s*\d*\s*[:.-]", lines[0], re.I):
            return "note"
        if len(lines) == 1 and len(lines[0].split()) <= 14 and not re.search(r"[.!?]$", lines[0]):
            return "heading"
        return "narrative"

    @staticmethod
    def _csv(values: Iterable[str]) -> str:
        return ",".join(sorted({value.strip() for value in values if value.strip()}, key=str.casefold))

    @staticmethod
    def _matches(text: str, terms: Sequence[str]) -> str:
        return DocumentAgent._csv(term for term in terms if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.I))

    def _document_metadata(self, path: Path, text: str, pages: List[Dict[str, Any]]) -> Dict[str, str]:
        pdf_metadata: Dict[str, str] = {}
        if path.suffix.lower() == ".pdf":
            try:
                pdf_metadata = self._extract_pdf_metadata(path)
            except Exception as exc:
                logger.warning("Unable to read PDF metadata for %s: %s", path.name, exc)
                pdf_metadata = {}
        cover = self._top_text_evidence(text, pages)
        document_evidence = f"{cover}\n{path.stem.replace('_', ' ')}"
        title = pdf_metadata.get("title", "")
        if not title:
            title_match = re.search(r"(?im)^\s*(.{2,120}(?:annual|integrated|sustainability|esg|proxy|quarterly|earnings|10-k|10-q) (?:report|statement|filing).{0,80})\s*$", document_evidence)
            title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else ""
        if title and len(title) > 200:
            title = title[:200].strip()
        company = self._extract_company_name(cover, pdf_metadata=pdf_metadata, pages=pages)
        financial_year = self._extract_financial_year(document_evidence)
        report_type = self._infer_report_type(document_evidence)
        period_match = re.search(r"\b((?:Q[1-4])\s*(?:FY)?\s*(?:19|20)?\d{2})\b|\b(?:year ended|fiscal year ended)\s+([A-Za-z]+\s+\d{1,2},?\s+(?:19|20)\d{2})", document_evidence, re.I)
        filing_match = re.search(r"\b(?:filed|filing date|report date|dated)\s*[:\-]?\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{4}[-/]\d{2}[-/]\d{2})", cover, re.I)
        boundary = re.findall(r"\b(?:beginning|starting|ended|ending)\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{4}[-/]\d{2}[-/]\d{2})", cover, re.I)
        currency = re.search(r"\b(USD|INR|EUR|GBP|JPY|CAD|AUD)\b|([$€£₹])", cover, re.I)
        language = "English" if len(re.findall(r"\b(?:the|and|of|for|financial|report|corporate|company)\b", cover, re.I)) >= 5 else ""
        industry_match = re.search(r"\b(?:industry|sector)\s*[:\-]\s*([^\n,;]{2,80})", cover, re.I)
        return {
            "document_title": title,
            "report_title": title,
            "company_name": company,
            "financial_year": financial_year,
            "report_type": report_type,
            "report_period": (period_match.group(1).upper().replace("FY", "FY") if period_match and period_match.group(1) else (period_match.group(2).strip() if period_match and period_match.group(2) else "")),
            "filing_date": filing_match.group(1) if filing_match else "",
            "document_language": language,
            "fiscal_year_start": boundary[0] if boundary else "",
            "fiscal_year_end": boundary[-1] if len(boundary) > 1 else (boundary[0] if boundary else ""),
            "currency": (currency.group(1) or {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}.get(currency.group(2), "")) if currency else "",
            "industry": industry_match.group(1).strip() if industry_match else "",
        }

    @staticmethod
    def _named_values(text: str, labels: Sequence[str]) -> str:
        """Extract names or labels only when introduced by explicit document language."""
        matches = []
        label_pattern = "|".join(re.escape(label) for label in labels)
        for match in re.finditer(rf"(?:{label_pattern})\s*(?:include|are|:)?\s*([^.;\n]+)", text, re.I):
            matches.extend(re.findall(r"\b[A-Z][A-Za-z0-9&.-]{1,30}(?:\s+[A-Z][A-Za-z0-9&.-]{1,30}){0,3}\b", match.group(1)))
        return DocumentAgent._csv(matches)

    @staticmethod
    def _normalize_heading(text: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"\s*[:\-–—]\s*$", "", text.strip())).strip()

    def _extract_company_name(self, text: str, pdf_metadata: Optional[Dict[str, str]] = None, pages: Optional[List[Dict[str, Any]]] = None) -> str:
        if not text and not pdf_metadata:
            return ""

        def _clean_line(value: str) -> str:
            value = re.sub(r"\s+", " ", value).strip()
            value = re.sub(r"^\s*(?:page\s*)?\d{1,4}\s+", "", value, flags=re.I)
            value = re.sub(r"^[,;:\- ]+|[,;:\- ]+$", "", value)
            return value.strip()

        def _normalize_candidate(value: str) -> str:
            candidate = re.sub(r"\s+", " ", value).strip()
            candidate = re.sub(r"^\s*(?:page\s*)?\d{1,4}\s+", "", candidate, flags=re.I)
            candidate = re.sub(r"^(?:the\s+)?(?:company|issuer|registrant|issuer name|registrant name|company name)\s*[:\-]\s*", "", candidate, flags=re.I)
            candidate = re.sub(r"\s+(?:annual|quarterly|sustainability|esg|proxy|integrated|report|statement|letter|results|update|presentation|shareholder|notice|form)(?:\s+(?:report|statement|letter|results|update|presentation|shareholder|notice|form))*\s*(?:\b(?:19|20)\d{2}\b)?$", "", candidate, re.I)
            candidate = re.sub(r"\s+\b(?:19|20)\d{2}\b$", "", candidate, re.I)
            candidate = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9.]+$", "", candidate)
            return candidate.strip()

        def _is_company_candidate(value: str, source: str = "", line: str = "", occurrences: int = 1) -> bool:
            if not value or len(value) < 3:
                return False
            normalized = value.strip()
            if not re.search(r"[A-Za-z]", normalized):
                return False
            words = normalized.split()
            haystack = f"{normalized} {line}".lower()
            if normalized.lower().startswith(("for ", "to ")):
                return False
            if len(words) > 8:
                return False
            punctuation_probe = re.sub(r"\b(?:inc|ltd|corp|co)\.", "", normalized, flags=re.I)
            if re.search(r"[.!?]", punctuation_probe):
                return False
            if re.search(r"\b(?:dear|shareholders?|colleagues|customers?|partners?|letter from|message from)\b", haystack, re.I):
                return False
            if re.search(r"\b(?:annual|quarterly|sustainability|esg|proxy|integrated|report|statement|presentation|letter|notice|form|financial|management|risk|auditor|page|section|table|figure|note|notes|about|business overview|security overview|cybersecurity|income statement|balance sheets?|cash flows?|governance|liquidity|dividends?|initiative|program|project|campaign)\b", normalized, re.I):
                return False
            if re.search(r"\b(?:github copilot|copilot|azure|windows|office|word|microsoft 365|artificial intelligence|generative ai|\bai\b)\b", normalized, re.I):
                return False
            if re.search(r"\b(?:continue|continues|drive|drives|delivered|generated|using|provides|platform|service|product|solution|technology)\b", haystack, re.I):
                return False
            legal_suffix = re.search(r"\b(?:inc\.?|incorporated|limited|ltd\.?|llc|corp\.?|plc|co\.?|company|group|holdings|corporation|bancorp|technologies|systems|motors)(?=$|\W)", normalized, re.I)
            strong_source = source in {"document_metadata", "title", "issuer", "frequency"}
            if len(words) == 1 and not (legal_suffix or (strong_source and occurrences >= 2) or source == "title"):
                return False
            return True

        def _extract_candidates(text_block: str, source: str, max_lines: int = 40) -> list[dict[str, object]]:
            candidates = []
            lines = [_clean_line(line) for line in text_block.splitlines() if _clean_line(line)]
            for index, line in enumerate(lines[:max_lines]):
                if not line or len(line.split()) > 20:
                    continue
                normalized = _normalize_candidate(line)
                if _is_company_candidate(normalized, source, line):
                    candidates.append({"value": normalized, "source": source, "line": line, "index": index})
            return candidates

        def _repeated_headers(pages_list: Optional[list[dict[str, object]]]) -> list[str]:
            if not pages_list:
                return []
            header_counts: dict[str, int] = {}
            for page in pages_list:
                lines = [_clean_line(line) for line in page.get("text", "").splitlines() if _clean_line(line)]
                for line in lines[:2] + lines[-2:]:
                    if line and len(line.split()) <= 10:
                        header_counts[line] = header_counts.get(line, 0) + 1
            return [line for line, count in header_counts.items() if count >= 2]

        def _issuer_candidates(text_block: str) -> list[dict[str, object]]:
            candidates = []
            lines = [_clean_line(line) for line in text_block.splitlines() if _clean_line(line)]
            for index, line in enumerate(lines[:40]):
                if re.search(r"\b(?:issuer|registrant|issuer name|registrant name|company name|issued by|registered office|registered name)\b", line, re.I):
                    next_line = lines[index + 1] if index + 1 < len(lines) else ""
                    for value in (line, next_line):
                        normalized = _normalize_candidate(value)
                        if _is_company_candidate(normalized, "issuer", value):
                            candidates.append({"value": normalized, "source": "issuer", "line": value, "index": index})
            return candidates

        def _title_candidates(text_block: str) -> list[dict[str, object]]:
            candidates = []
            lines = [_clean_line(line) for line in text_block.splitlines() if _clean_line(line)]
            report_words = r"(?:annual|quarterly|integrated|sustainability|esg|proxy|10-k|10-q)"
            for index, line in enumerate(lines[:30]):
                if not re.search(rf"\b{report_words}\b", line, re.I):
                    continue
                before = re.split(rf"\b{report_words}\b", line, maxsplit=1, flags=re.I)[0].strip(" -:|")
                after = re.sub(rf".*?\b{report_words}\b\s*(?:report|statement|filing)?\s*(?:for\s+)?", "", line, flags=re.I).strip(" -:|")
                for value in (before, after):
                    normalized = _normalize_candidate(value)
                    if _is_company_candidate(normalized, "title", line):
                        candidates.append({"value": normalized, "source": "title", "line": line, "index": index})
            return candidates

        def _frequency_candidates(text_block: str) -> list[dict[str, object]]:
            counts: Dict[str, int] = {}
            for match in re.finditer(r"\b[A-Z][A-Za-z&.-]{2,}(?:\s+[A-Z][A-Za-z&.-]{2,}){0,2}\b", text_block):
                value = _normalize_candidate(match.group(0))
                if _is_company_candidate(value, "frequency", match.group(0), occurrences=2):
                    counts[value] = counts.get(value, 0) + 1
            candidates = []
            for value, count in counts.items():
                if count >= 3:
                    candidates.append({"value": value, "source": "frequency", "line": value, "index": 20, "count": count})
            return candidates

        def _score_candidate(record: dict[str, object]) -> float:
            score = 0.0
            weights = {
                "document_metadata": 0.40,
                "title": 0.42,
                "cover": 0.20,
                "first_page": 0.18,
                "issuer": 0.35,
                "repeated_headers": 0.30,
                "frequency": 0.36,
            }
            for source, count in record["sources"].items():
                score += weights.get(source, 0.0) * min(count, 2)
            if record["occurrences"] >= 2:
                score += 0.10
            if record["first_index"] == 0:
                score += 0.05
            if record["first_index"] == 1:
                score += 0.03
            return score

        candidates: dict[str, dict[str, object]] = {}

        def add_candidate(value: str, source: str, line: str, index: int) -> None:
            normalized = _normalize_candidate(value)
            if not _is_company_candidate(normalized, source, line):
                return
            key = normalized.lower()
            record = candidates.setdefault(
                key,
                {"value": normalized, "sources": {}, "occurrences": 0, "first_index": index, "lines": []},
            )
            record["sources"][source] = record["sources"].get(source, 0) + 1
            record["occurrences"] += 1
            record["lines"].append(line)
            if index < record["first_index"]:
                record["first_index"] = index

        if pdf_metadata:
            for field in ("title", "author", "subject"):
                value = pdf_metadata.get(field)
                if value:
                    add_candidate(value, "document_metadata", value, -1)

        cover = self._top_text_evidence(text, pages or [])
        for candidate in _title_candidates(cover):
            add_candidate(candidate["value"], candidate["source"], candidate["line"], candidate["index"])

        first_page_text = pages[0]["text"] if pages else text
        for candidate in _extract_candidates(first_page_text, "first_page", max_lines=40):
            add_candidate(candidate["value"], candidate["source"], candidate["line"], candidate["index"])

        for candidate in _extract_candidates(cover, "cover", max_lines=40):
            add_candidate(candidate["value"], candidate["source"], candidate["line"], candidate["index"])

        for header in _repeated_headers(pages):
            add_candidate(header, "repeated_headers", header, 0)

        for candidate in _issuer_candidates(cover):
            add_candidate(candidate["value"], candidate["source"], candidate["line"], candidate["index"])

        for candidate in _frequency_candidates(cover):
            add_candidate(candidate["value"], candidate["source"], candidate["line"], candidate["index"])
            key = str(candidate["value"]).lower()
            if key in candidates:
                candidates[key]["occurrences"] = max(int(candidates[key]["occurrences"]), int(candidate.get("count", 1)))

        if not candidates:
            return ""

        scored = [
            {**record, "score": _score_candidate(record)}
            for record in candidates.values()
        ]
        scored.sort(key=lambda item: item["score"], reverse=True)
        best = scored[0]
        return best["value"] if best["score"] >= 0.45 else ""

    @staticmethod
    def _extract_financial_year(text: str) -> str:
        patterns = [
            r"\b(?:fiscal|financial)\s+year\s+(?:ended|ending)?\s*(?:\w+\s+\d{1,2},?\s+)?((?:19|20)\d{2})\b",
            r"\byear\s+ended\s+(?:\w+\s+\d{1,2},?\s+)?((?:19|20)\d{2})\b",
            r"\b(?:annual|integrated|sustainability|proxy|quarterly)\s+report\s+((?:19|20)\d{2})\b",
            r"\b(?:FY|Q[1-4]\s*FY?)\s*((?:19|20)?\d{2})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                year = match.group(1)
                return f"20{year}" if len(year) == 2 else year
        years = [int(year) for year in re.findall(r"\b((?:19|20)\d{2})\b", text)]
        plausible = [year for year in years if 1990 <= year <= datetime.now().year + 1]
        return str(max(plausible)) if plausible else ""

    def _infer_report_type(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        lowered = cleaned.lower()
        if re.search(r"\b10-k\b", lowered):
            return "10-K"
        if re.search(r"\b10-q\b", lowered):
            return "10-Q"
        if re.search(r"\bproxy\b|definitive proxy statement|annual meeting of shareholders", lowered):
            return "Proxy Statement"
        if re.search(r"\bintegrated report\b|\bintegrated annual report\b", lowered):
            return "Integrated Report"
        if re.search(r"\bsustainability report\b|\besg report\b|\benvironmental,? social,? and governance report\b", lowered):
            return "Sustainability Report"
        if re.search(r"\bquarterly report\b|\bquarter ended\b|\bq[1-4]\b", lowered):
            return "Quarterly Report"
        if re.search(r"\bannual report\b|\bform 10-k\b", lowered):
            return "Annual Report"
        return "Other"

    def _extract_section_heading_and_type(self, text: str) -> Tuple[str, str]:
        if not text:
            return "", "other"
        cleaned = re.sub(r"\s+", " ", text).strip()
        lower = cleaned.lower()
        section_patterns = [
            (r"management discussion and analysis|md&a", "Management Discussion and Analysis", "management_discussion"),
            (r"business overview|our business|business\s*$|operations overview|company overview", "Business Overview", "business"),
            (r"risk factors?|market risk|legal proceedings|cybersecurity risk", "Risk Factors", "risk"),
            (r"consolidated balance sheets?|balance sheets?", "Balance Sheets", "financial_statement"),
            (r"consolidated statements? of (?:income|operations)|income statements?|statements? of earnings", "Income Statement", "financial_statement"),
            (r"statements? of cash flows?|cash flow statements?", "Cash Flow Statement", "financial_statement"),
            (r"statements? of shareholders'? equity|stockholders'? equity", "Shareholders' Equity", "financial_statement"),
            (r"financial statements?", "Financial Statements", "financial_statement"),
            (r"notes to the financial statements?|footnotes?", "Notes to Financial Statements", "notes"),
            (r"dividends?", "Dividends", "financial_statement"),
            (r"share repurchases?|stock repurchases?", "Share Repurchases", "financial_statement"),
            (r"liquidity|capital resources", "Liquidity and Capital Resources", "management_discussion"),
            (r"letter to shareholders?|shareholders' letter", "Letter to Shareholders", "cover"),
            (r"corporate governance", "Corporate Governance", "governance"),
            (r"environmental,? social,? and governance|esg|sustainability", "Sustainability", "sustainability"),
            (r"auditor(?:'s)? report|independent auditor", "Auditor's Report", "financial_statement"),
            (r"appendix|appendices", "Appendix", "appendix"),
        ]
        for pattern, title, kind in section_patterns:
            if re.search(pattern, lower, re.I):
                return self._normalize_heading(title), kind
        heading_candidates = [line.strip() for line in text.splitlines() if line.strip()]
        for line in heading_candidates[:8]:
            if len(line.split()) <= 12 and not re.search(r"[.!?]$", line):
                heading = self._normalize_heading(line)
                if len(heading.split()) >= 2 and re.search(r"[A-Za-z]", heading):
                    return heading, "other"
        return "", "other"

    def _window_chunk_text(self, index: int, chunks: List[Dict[str, Any]]) -> str:
        window_texts: List[str] = []
        for offset in (-1, 0, 1):
            pos = index + offset
            if 0 <= pos < len(chunks):
                window_texts.append(chunks[pos]["text"])
        return "\n\n".join(window_texts).strip()

    @staticmethod
    def _financial_metric_mapping() -> dict[str, str]:
        return {
            r"\brevenue\b": "Revenue",
            r"\boperating income\b": "Operating Income",
            r"\bgross profit\b": "Gross Profit",
            r"\bgross margin\b": "Gross Margin",
            r"\b(?:ebitda|e\.b\.i\.t\.d\.a\.)\b": "EBITDA",
            r"\b(?:ebit|e\.b\.i\.t\.)\b": "EBIT",
            r"\bcash flow\b": "Cash Flow",
            r"\boperating cash flow\b": "Operating Cash Flow",
            r"\bfree cash flow\b": "Free Cash Flow",
            r"\beps\b": "EPS",
            r"\bdiluted eps\b": "Diluted EPS",
            r"\bcapex\b": "CapEx",
            r"\bcapital expenditure\b": "CapEx",
            r"\b(?:r\s*&\s*d|research and development)\b": "R&D",
            r"\bshare repurchases?\b": "Share Repurchases",
            r"\bbuyback\b": "Share Repurchases",
            r"\bdividend\b": "Dividend",
            r"\btax expense\b": "Tax Expense",
            r"\bnet income\b": "Net Income",
            r"\bworking capital\b": "Working Capital",
            r"\bdebt\b": "Debt",
            r"\bequity\b": "Equity",
            r"\binventory\b": "Inventory",
            r"\baccounts receivable\b": "Accounts Receivable",
            r"\baccounts payable\b": "Accounts Payable",
            r"\bgoodwill\b": "Goodwill",
            r"\bintangible assets\b": "Intangible Assets",
            r"\bsegment revenue\b": "Segment Revenue",
            r"\boperating margin\b": "Operating Margin",
            r"\breturn on equity\b": "Return on Equity",
            r"\breturn on assets\b": "Return on Assets",
            r"\bliquidity\b": "Liquidity",
            r"\bleverage\b": "Leverage",
            r"\bgrowth rate\b": "Growth Rate",
            r"\bgrowth\b": "Growth Rate",
            r"\bassets\b": "Assets",
            r"\bliabilities\b": "Liabilities",
        }

    def _extract_financial_metrics(self, text: str) -> str:
        metrics: List[str] = []
        mapping = self._financial_metric_mapping()
        normalized = text.lower()
        for pattern, name in mapping.items():
            if re.search(pattern, normalized, re.I) and name not in metrics:
                metrics.append(name)
        return self._csv(metrics)

    @staticmethod
    def _semantic_tag_mapping() -> dict[str, Tuple[str, ...]]:
        return {
            "Cloud": (r"\bcloud\b", r"\bazure\b", r"\binfrastructure\b", r"\bdata center\b", r"\bdata centre\b"),
            "Artificial Intelligence": (r"\bartificial intelligence\b", r"\bmachine learning\b", r"\bai\b", r"\bdeep learning\b"),
            "Cybersecurity": (r"\bcybersecurity\b", r"\bsecurity\b", r"\bcyber risk\b"),
            "Gaming": (r"\bgaming\b", r"\bgame\b", r"\bconsole\b"),
            "Advertising": (r"\badvertis(?:ing|ement)\b", r"\bads\b"),
            "Azure": (r"\bazure\b",),
            "Microsoft 365": (r"\bmicrosoft 365\b", r"\boffice 365\b"),
            "Office": (r"\boffice\b",),
            "Developer Tools": (r"\bdeveloper tools\b", r"\bdeveloper platform\b", r"\bdev tools\b"),
            "GitHub": (r"\bgithub\b",),
            "Enterprise": (r"\benterprise\b", r"\benterprise software\b"),
            "Productivity": (r"\bproductivity\b",),
            "Infrastructure": (r"\binfrastructure\b", r"\bplatform\b", r"\bservices?\b"),
            "Investment": (r"\binvestment\b", r"\bcapital markets\b", r"\bcapital expenditure\b", r"\bcapex\b"),
            "Risk": (r"\brisk\b", r"\brisk factors\b"),
            "Compliance": (r"\bcompliance\b", r"\bregulator|regulatory\b"),
            "Sustainability": (r"\bsustainability\b", r"\besg\b", r"\benvironmental\b", r"\bsocial\b"),
            "Supply Chain": (r"\bsupply chain\b", r"\blogistics\b"),
            "Manufacturing": (r"\bmanufactur(?:ing|er)\b",),
            "Consumer": (r"\bconsumer\b", r"\bretail\b"),
            "Automotive": (r"\bautomotive\b", r"\bvehicle\b", r"\bauto\b"),
            "Energy": (r"\benergy\b", r"\bpower\b", r"\brenewable\b"),
            "Healthcare": (r"\bhealthcare\b", r"\bmedical\b", r"\bpharma\b"),
        }

    def _extract_semantic_tags(self, text: str) -> str:
        tags: List[str] = []
        normalized = text.lower()
        for label, patterns in self._semantic_tag_mapping().items():
            for pattern in patterns:
                if re.search(pattern, normalized, re.I):
                    tags.append(label)
                    break
        return self._csv(tags)

    @staticmethod
    def _table_profile(text: str) -> Tuple[bool, bool, str, int, int]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return False, False, "", 0, 0
        number_pattern = r"(?:\(?[-$€£₹]?\d[\d,]*(?:\.\d+)?%?\)?|\b(?:19|20)\d{2}\b)"
        numeric_lines = [line for line in lines if re.search(number_pattern, line)]
        year_lines = [line for line in lines if len(re.findall(r"\b(?:19|20)\d{2}\b", line)) >= 2]
        separated_lines = [line for line in lines if "\t" in line or "|" in line or len(re.split(r"\s{2,}", line)) >= 3]
        dense_numeric_lines = [line for line in lines if len(re.findall(number_pattern, line)) >= 2]
        metric_re = r"\b(?:revenue|sales|income|earnings|assets|liabilities|equity|cash flow|cash and cash equivalents|debt|dividend|repurchase|shares|expense|gross margin|operating margin|net income|operating income|cost of revenue|accounts receivable|inventory)\b"
        financial_lines = [line for line in lines if re.search(metric_re, line, re.I)]
        table = (
            len(separated_lines) >= 2
            or len(dense_numeric_lines) >= 3
            or (len(numeric_lines) >= 4 and bool(year_lines))
            or (len(financial_lines) >= 2 and len(numeric_lines) >= 3)
        )
        financial_table = table and (len(financial_lines) >= 1 or bool(year_lines and dense_numeric_lines))
        columns = max((len(re.split(r"\s{2,}|\|", line)) for line in lines), default=0)
        if table and columns <= 1 and len(lines) >= 4:
            columns = max(columns, min(3, max(len(line.split()) for line in lines) // 2))
        lowered = text.lower()
        if re.search(r"balance sheets?|assets|liabilities", lowered):
            table_type = "Balance Sheet"
        elif re.search(r"cash flows?|operating activities|financing activities|investing activities", lowered):
            table_type = "Cash Flow"
        elif re.search(r"income|operations|earnings|revenue|sales", lowered):
            table_type = "Income Statement"
        elif re.search(r"dividend", lowered):
            table_type = "Dividend Table"
        elif re.search(r"repurchase", lowered):
            table_type = "Share Repurchases"
        elif re.search(r"segment", lowered):
            table_type = "Segment Revenue"
        elif re.search(r"geographic|country|region", lowered):
            table_type = "Geographic Revenue"
        else:
            table_type = "Financial Table" if financial_table else ("Table" if table else "")
        return table, financial_table, table_type, len(lines) if table else 0, columns if table else 0

    @staticmethod
    def _contains_chart(text: str) -> bool:
        return bool(re.search(r"\b(?:figure|chart|graph|plot|diagram|bar chart|pie chart|trend|performance graph|indexed comparison|visualization)\b", text, re.I))

    def _people(self, text: str) -> str:
        names = re.findall(r"\b(?:CEO|CFO|Chief Executive Officer|Chief Financial Officer|Chair(?:man|person)?|Director)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})", text)
        names += re.findall(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\s+(?:is|was|serves as)\s+(?:the\s+)?(?:CEO|CFO|Chair|Director)", text, re.I)
        return self._csv(names)

    def _build_chunk_metadata(self, path: Path, doc_hash: str, chunks: List[Dict[str, Any]], analysis_id: str, pages: List[Dict[str, Any]], ids: List[str], full_text: str) -> List[Dict[str, Any]]:
        doc = self._document_metadata(path, full_text, pages)
        result = []
        timestamp = datetime.now(timezone.utc).isoformat()
        for index, chunk_record in enumerate(chunks):
            chunk = chunk_record["text"]
            section_title = chunk_record.get("section_title", "") or ""
            section_type = chunk_record.get("section_type", "other") or "other"
            table, financial_table, table_type, table_rows, table_columns = self._table_profile(chunk)
            if not table:
                table = "table" in chunk_record.get("block_types", [])
            window_text = self._window_chunk_text(index, chunks)
            if table:
                surrounding_text = f"{chunk}\n\n{window_text}" if window_text else chunk
            else:
                surrounding_text = window_text or chunk
            values = re.findall(
                r"\b(?:revenue|operating income|gross profit|gross margin|ebitda|ebit|cash flow|free cash flow|eps|diluted eps|capex|r&d|research and development|share repurchases?|dividend|tax expense|net income|working capital|debt|equity|inventory|accounts receivable|accounts payable|goodwill|intangible assets|segment revenue|operating margin|return on equity|return on assets|liquidity|leverage|growth rate|growth|assets|liabilities)\b[^\n]{0,45}?(?:[-−(]?[$€£₹]?[\d,.]+(?:\s*(?:million|billion|bn|m|b))?%?[)]?)",
                surrounding_text,
                re.I,
            )
            page_numbers = chunk_record["page_numbers"]
            organizations = self._named_values(surrounding_text, ("companies", "organizations", "partners", "customer", "customers"))
            products = self._named_values(surrounding_text, ("products", "services", "platforms", "offerings"))
            business_segments = self._named_values(surrounding_text, ("segments", "business segments", "operating segments"))
            confidence = round(sum(bool(value) for value in (doc["company_name"], doc["financial_year"], section_title, values)) / 4, 2)
            sentences = [sentence for sentence in re.split(r"(?<=[.!?])\s+", chunk) if sentence.strip()]
            paragraphs = [paragraph for paragraph in re.split(r"\n\s*\n", chunk) if paragraph.strip()]
            chunk_type = "financial_table" if financial_table else ("risk" if section_type == "risk" else ("md&a" if section_type == "management_discussion" else section_type if section_type in {"notes", "governance", "sustainability", "appendix", "chart", "business", "cover", "financial_statement"} else "narrative"))
            semantic_tags = self._extract_semantic_tags(surrounding_text)
            financial_metrics = self._extract_financial_metrics(surrounding_text)
            chunk_summary = f"Discusses {financial_metrics.lower()}." if financial_metrics else (f"Discusses {section_title.lower()}." if section_title else "Contains report information.")
            chunk_summary = " ".join(chunk_summary.split()[:25])
            metadata: Dict[str, Any] = {
                "analysis_id": analysis_id,
                "source": path.name,
                "doc_hash": doc_hash,
                "chunk_id": ids[index],
                "chunk_index": index,
                "total_chunks": len(chunks),
                "previous_chunk_id": ids[index - 1] if index else "",
                "next_chunk_id": ids[index + 1] if index + 1 < len(chunks) else "",
                "page_start": min(page_numbers) if page_numbers else 0,
                "page_end": max(page_numbers) if page_numbers else 0,
                "page_numbers": self._csv(map(str, page_numbers)),
                "content_length": len(chunk),
                "word_count": len(chunk.split()),
                "sentence_count": len(sentences),
                "paragraph_count": len(paragraphs),
                "reading_time": round(len(chunk.split()) / 3.33, 1),
                "reading_time_seconds": round(len(chunk.split()) / 3.33, 1),
                "document_title": doc["document_title"],
                "report_title": doc["report_title"],
                "document_language": doc["document_language"],
                "report_type": doc["report_type"],
                "financial_year": doc["financial_year"],
                "report_period": doc["report_period"],
                "filing_date": doc["filing_date"],
                "fiscal_year_start": doc["fiscal_year_start"],
                "fiscal_year_end": doc["fiscal_year_end"],
                "currency": doc["currency"],
                "document_version": "1",
                "section_title": section_title,
                "section_type": section_type,
                "chunk_type": chunk_type,
                "chunk_summary": chunk_summary[:240],
                "industry": doc["industry"],
                "company_name": doc["company_name"],
                "company_ticker": (re.search(r"\b(?:ticker|symbol)\s*[:\-]\s*([A-Z]{1,5})\b", chunk) or ["", ""])[1],
                "confidence_score": confidence,
                "semantic_tags": semantic_tags,
                "organizations": organizations,
                "people": self._people(surrounding_text),
                "products": products,
                "countries": self._csv(re.findall(r"\b(?:United States|United Kingdom|Canada|India|Germany|France|Japan|China|Australia|Singapore)\b", surrounding_text)),
                "financial_metrics": financial_metrics,
                "financial_entities": financial_metrics,
                "financial_values": self._csv(values),
                "business_segments": business_segments,
                "investment_keywords": self._matches(surrounding_text, ("investment", "capital expenditure", "share buyback", "share repurchase", "dividend", "guidance")),
                "risks": self._matches(surrounding_text, ("cybersecurity", "competition", "regulation", "inflation", "interest rates", "supply chain", "litigation")),
                "contains_table": str(table).lower(),
                "table_type": table_type,
                "contains_financial_table": str(financial_table).lower(),
                "table_rows": table_rows,
                "table_columns": table_columns,
                "contains_chart": str(self._contains_chart(surrounding_text)).lower(),
                "contains_footnotes": str(bool(re.search(r"\bfootnotes?\b|notes to", surrounding_text, re.I))).lower(),
                "is_audited": self._matches(surrounding_text, ("audited", "unaudited")),
                "ingestion_timestamp": timestamp,
            }
            result.append(metadata)
        return result

    def _store_chunks(self, chunks: List[str], metadatas: List[Dict[str, Any]], ids: List[str]) -> None:
        for start in range(0, len(chunks), self.config.batch_size):
            end = start + self.config.batch_size
            logger.info("Embedding generation and insertion: chunks %s-%s", start + 1, min(end, len(chunks)))
            self.collection.add(documents=chunks[start:end], metadatas=metadatas[start:end], ids=ids[start:end])

    def ingest_document(self, file_path_str: str, overwrite: Optional[bool] = None, analysis_id: Optional[str] = None, force_reingest: bool = False) -> Dict[str, Any]:
        started = time.time()
        path = self._resolve_file_path(file_path_str)
        current_analysis = analysis_id or self.create_analysis()
        if not path.exists():
            return IngestionResult("error", path.name, current_analysis, 0, 0, self.config.collection_name, False, "File not found").to_dict()
        try:
            doc_hash = self.generate_document_hash(path)
            allow_replace = force_reingest
            if not allow_replace and self.document_exists(doc_hash):
                logger.info("Skipped duplicate: %s", path.name)
                return IngestionResult("success", path.name, current_analysis, 0, time.time() - started, self.config.collection_name, True).to_dict()
            if (self.config.overwrite or overwrite) and self._source_chunk_ids(path.name):
                old_ids = self._source_chunk_ids(path.name)
                self.collection.delete(ids=old_ids)
                logger.info("Replaced existing source source=%s chunks=%s", path.name, len(old_ids))
            text, pages = self.extract_text(path)
            if not text:
                return IngestionResult("error", path.name, current_analysis, 0, time.time() - started, self.config.collection_name, False, "Document is empty or unreadable").to_dict()
            chunk_records = self._chunk_pages(pages)
            chunks = [record["text"] for record in chunk_records]
            ids = [str(uuid.uuid4()) for _ in chunk_records]
            self._store_chunks(chunks, self._build_chunk_metadata(path, doc_hash, chunk_records, current_analysis, pages, ids, text), ids)
            logger.info("Loaded document=%s pages=%s chunks=%s time=%.2fs", path.name, len(pages), len(chunks), time.time() - started)
            return IngestionResult("success", path.name, current_analysis, len(chunks), time.time() - started, self.config.collection_name, False).to_dict()
        except Exception as exc:
            logger.exception("Error ingesting %s", path)
            return IngestionResult("error", path.name, current_analysis, 0, time.time() - started, self.config.collection_name, False, str(exc)).to_dict()

    def ingest_directory(self, directory_path: str) -> List[Dict[str, Any]]:
        files = discover_supported_files(directory_path)
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            return [future.result() for future in [executor.submit(self.ingest_document, str(path)) for path in files]]

    def get_collection_stats(self) -> Dict[str, Any]:
        return {"collection_name": self.config.collection_name, "total_chunks": self.collection.count(), "database_path": self.config.db_path, "embedding_model": self.config.embedding_model_name}


if __name__ == "__main__":
    scripts_dir = Path(__file__).resolve().parent
    root = scripts_dir.parent
    db = resolve_chroma_db_path(__file__, root.parent)
    print(DocumentAgent(DocumentAgentConfig(db_path=str(db))).ingest_directory(str(scripts_dir / "demo_data")))
