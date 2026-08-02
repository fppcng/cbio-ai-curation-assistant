"""Extract publication metadata for curation reports."""

from __future__ import annotations

import logging

from cbio_curation_assistant.llm import LLMConfig
from cbio_curation_assistant.publications import (
    PublicationMetadata,
    extract_pdf_metadata_with_llm,
    extract_xml_metadata_with_llm,
)
from cbio_curation_assistant.workflows.curation_report.models import (
    LlmMetadataExtraction,
    PaperSource,
)


logger = logging.getLogger(__name__)


def extract_metadata(
    paper_source: PaperSource,
    llm_config: LLMConfig | None,
    warnings: list[str],
) -> PublicationMetadata:
    paper_path = paper_source.path.expanduser().resolve()
    if not paper_path.is_file():
        source_name = paper_source.kind.upper()
        raise FileNotFoundError(f"Paper {source_name} not found: {paper_path}")
    if paper_source.kind == "pdf":
        return extract_pdf_metadata_with_llm(
            paper_path,
            llm_config,
            warnings,
            logger=logger,
        )
    extracted = extract_xml_metadata_with_llm(
        paper_path,
        llm_config,
        warnings,
        logger=logger,
        missing_text_warning=(
            "Could not extract text from the XML. Using structured XML metadata only."
        ),
        missing_llm_warning=(
            "No Hermes LLM configuration is available. "
            "Using structured XML metadata only."
        ),
        completion_failure_warning=(
            "XML metadata completion returned unexpected format. "
            "Continuing with structured XML metadata only."
        ),
    )
    return PublicationMetadata.from_mapping(extracted)


def build_llm_details(llm_config: LLMConfig | None) -> LlmMetadataExtraction:
    return LlmMetadataExtraction(
        enabled=llm_config is not None,
        provider=llm_config.provider if llm_config else None,
        model=llm_config.model if llm_config else None,
        api_mode=llm_config.api_mode if llm_config else None,
        base_url=llm_config.base_url if llm_config else None,
    )


__all__ = ["build_llm_details", "extract_metadata"]
