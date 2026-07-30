"""Compatibility facade for the public :mod:`integrations.pmc` API."""

# ruff: noqa: F401

from __future__ import annotations

import time  # noqa: F401 - legacy module attribute
from pathlib import Path

import requests  # noqa: F401 - legacy module attribute

from cbio_curation_assistant.integrations.pmc import (
    HTTP_HEADERS,
    NCBI_CONTACT_EMAIL,
    NCBI_TIMEOUT_SECONDS,
    NCBI_TOOL_NAME,
    DownloadedSupplement,
    PMCErrorClassification,
    PMCRequestError,
    PMC_DOWNLOAD_RETRY_ATTEMPTS,
    PMC_DOWNLOAD_RETRY_BASE_DELAY_SECONDS,
    PMC_REQUEST_RETRY_ATTEMPTS,
    PMC_REQUEST_RETRY_BASE_DELAY_SECONDS,
    ResolvedStudyIdentifier,
    detect_pubmed_identifier_type,
    download_pmc_supplements,
    normalize_pmcid,
    pmid_to_pmcid,
)
from cbio_curation_assistant.integrations.pmc.archives import (
    extract_supported_files as _extract_supported_files,
    is_archive as _is_archive,
    is_supported_file as _is_supported_file,
    safe_extract_path as _safe_extract_path,
)
from cbio_curation_assistant.integrations.pmc.client import (
    classify_pmc_error as _classify_pmc_error,
    fetch_pmc_article_html as _fetch_pmc_article_html,
    fetch_pmc_xml as _fetch_pmc_xml,
    http_status_code_from_error as _http_status_code_from_error,
    lookup_oa_package_url as _oa_package_url,
    run_with_pmc_retry as _run_with_pmc_retry,
    wrap_pmc_error as _wrap_pmc_error,
)
from cbio_curation_assistant.integrations.pmc.discovery import (
    discover_article_pdf_url as _article_pdf_url_from_article_html,
    discover_supplement_urls as _discover_supplement_urls,
    discover_supplement_urls_from_html as _supplement_urls_from_article_html,
    discover_supplement_urls_from_xml as _supplement_urls,
)
from cbio_curation_assistant.integrations.pmc.downloads import (
    download_file as _download_url,
    download_file_once as _download_url_once,
    download_oa_package_files as _download_oa_package,
    download_with_proof_of_work as _download_url_with_urllib_pow,
    filename_extension as _filename_extension,
    filename_from_headers as _filename_from_headers,
    filename_from_response as _filename_from_response,
    is_pmc_download_host as _is_pmc_download_host,
    is_retryable_pmc_download_error as _is_retryable_pmc_download_error,
    looks_like_html_payload as _looks_like_html_payload,
    safe_filename as _safe_filename,
    validate_downloaded_content as _validate_downloaded_content,
)
from cbio_curation_assistant.integrations.pmc.identifiers import (
    pmcid_numeric as _pmcid_numeric,
    resolve_study_identifier_to_pmcid as _resolve_identifier_to_pmcid,
)
from cbio_curation_assistant.integrations.pmc.proof_of_work import (
    POW_MAX_ITERATIONS,
    parse_proof_of_work_challenge as _parse_pow_challenge,
    set_proof_of_work_cookie as _set_cookie,
    solve_proof_of_work_nonce as _solve_pow_nonce,
)
from cbio_curation_assistant.supplements.formats import (
    ARCHIVE_EXTENSIONS,
    SUPPORTED_SUPPLEMENT_EXTENSIONS,
)


def resolve_study_identifier_to_pmcid(
    identifier: str,
) -> ResolvedStudyIdentifier:
    """Preserve the legacy converter patch seam while delegating resolution."""
    return _resolve_identifier_to_pmcid(
        identifier,
        pmid_resolver=pmid_to_pmcid,
    )


def _extension(path: Path) -> str:
    if path.name.lower().endswith(".tar.gz"):
        return ".tar.gz"
    return path.suffix.lower()
