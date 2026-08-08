"""Backward-compatible import path for the production document agent."""

from document_agent import DocumentAgent, DocumentAgentConfig, IngestionResult, discover_supported_files

__all__ = ["DocumentAgent", "DocumentAgentConfig", "IngestionResult", "discover_supported_files"]