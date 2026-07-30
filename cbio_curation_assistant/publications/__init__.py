"""Publication metadata extraction, completion, and normalization."""

from cbio_curation_assistant.publications.completion import (
    PUBLICATION_METADATA_PROMPT,
    complete_pdf_metadata,
    extract_pdf_metadata_with_llm,
    extract_xml_metadata_with_llm,
)
from cbio_curation_assistant.publications.metadata import (
    build_study_id,
    is_missing_metadata_value,
    merge_missing_metadata_fields,
)
from cbio_curation_assistant.publications.models import PublicationMetadata
from cbio_curation_assistant.publications.pdf import (
    extract_metadata_regex,
    extract_pdf_text,
)
from cbio_curation_assistant.publications.xml import (
    extract_metadata_from_xml,
    extract_xml_llm_text,
    extract_xml_text,
)

__all__ = [
    "PUBLICATION_METADATA_PROMPT",
    "PublicationMetadata",
    "build_study_id",
    "complete_pdf_metadata",
    "extract_metadata_from_xml",
    "extract_metadata_regex",
    "extract_pdf_metadata_with_llm",
    "extract_pdf_text",
    "extract_xml_llm_text",
    "extract_xml_metadata_with_llm",
    "extract_xml_text",
    "is_missing_metadata_value",
    "merge_missing_metadata_fields",
]
