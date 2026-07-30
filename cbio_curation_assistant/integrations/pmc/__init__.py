"""Public API for PubMed Central identifiers, transport, and discovery."""

from cbio_curation_assistant.integrations.pmc.archives import (
    extract_supported_files,
    is_archive,
    is_supported_file,
)
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
from cbio_curation_assistant.integrations.pmc.downloads import (
    PMC_DOWNLOAD_RETRY_ATTEMPTS,
    PMC_DOWNLOAD_RETRY_BASE_DELAY_SECONDS,
    download_file,
    download_oa_package_files,
    download_pmc_supplements,
    validate_downloaded_content,
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
    DownloadedSupplement,
    PMCErrorClassification,
    PMCRequestError,
    ResolvedStudyIdentifier,
    format_pmc_error,
)

__all__ = [
    "HTTP_HEADERS",
    "NCBI_CONTACT_EMAIL",
    "NCBI_TIMEOUT_SECONDS",
    "NCBI_TOOL_NAME",
    "DownloadedSupplement",
    "PMCErrorClassification",
    "PMCRequestError",
    "PMC_DOWNLOAD_RETRY_ATTEMPTS",
    "PMC_DOWNLOAD_RETRY_BASE_DELAY_SECONDS",
    "PMC_REQUEST_RETRY_ATTEMPTS",
    "PMC_REQUEST_RETRY_BASE_DELAY_SECONDS",
    "ResolvedStudyIdentifier",
    "classify_pmc_error",
    "detect_pubmed_identifier_type",
    "download_file",
    "download_oa_package_files",
    "download_pmc_supplements",
    "discover_article_pdf_url",
    "discover_supplement_urls",
    "discover_supplement_urls_from_html",
    "discover_supplement_urls_from_xml",
    "fetch_pmc_article_html",
    "fetch_pmc_xml",
    "format_pmc_error",
    "extract_supported_files",
    "is_archive",
    "is_supported_file",
    "lookup_oa_package_url",
    "normalize_pmcid",
    "pmid_to_pmcid",
    "resolve_study_identifier_to_pmcid",
    "run_with_pmc_retry",
    "validate_downloaded_content",
]
