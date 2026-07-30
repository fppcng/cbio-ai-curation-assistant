"""Public API for PubMed Central identifiers, transport, and discovery."""

from cbio_curation_assistant.integrations.pmc.client import (
    HTTP_HEADERS,
    NCBI_CONTACT_EMAIL,
    NCBI_TIMEOUT_SECONDS,
    NCBI_TOOL_NAME,
    PMC_REQUEST_RETRY_ATTEMPTS,
    PMC_REQUEST_RETRY_BASE_DELAY_SECONDS,
    classify_pmc_error,
    fetch_pmc_article_html,
    fetch_pmc_xml,
    lookup_oa_package_url,
    pmid_to_pmcid,
    run_with_pmc_retry,
)
from cbio_curation_assistant.integrations.pmc.discovery import (
    discover_article_pdf_url,
    discover_supplement_urls,
    discover_supplement_urls_from_html,
    discover_supplement_urls_from_xml,
)
from cbio_curation_assistant.integrations.pmc.identifiers import (
    detect_pubmed_identifier_type,
    normalize_pmcid,
    resolve_study_identifier_to_pmcid,
)
from cbio_curation_assistant.integrations.pmc.models import (
    PMCErrorClassification,
    PMCRequestError,
    ResolvedStudyIdentifier,
)

__all__ = [
    "HTTP_HEADERS",
    "NCBI_CONTACT_EMAIL",
    "NCBI_TIMEOUT_SECONDS",
    "NCBI_TOOL_NAME",
    "PMCErrorClassification",
    "PMCRequestError",
    "PMC_REQUEST_RETRY_ATTEMPTS",
    "PMC_REQUEST_RETRY_BASE_DELAY_SECONDS",
    "ResolvedStudyIdentifier",
    "classify_pmc_error",
    "detect_pubmed_identifier_type",
    "discover_article_pdf_url",
    "discover_supplement_urls",
    "discover_supplement_urls_from_html",
    "discover_supplement_urls_from_xml",
    "fetch_pmc_article_html",
    "fetch_pmc_xml",
    "lookup_oa_package_url",
    "normalize_pmcid",
    "pmid_to_pmcid",
    "resolve_study_identifier_to_pmcid",
    "run_with_pmc_retry",
]
