"""HTTP transport, retry policy, and remote PMC lookups."""

from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import requests

from cbio_curation_assistant.integrations.pmc.identifiers import (
    normalize_pmcid,
    pmcid_numeric,
)
from cbio_curation_assistant.integrations.pmc.models import (
    PMCErrorClassification,
    PMCRequestError,
)


NCBI_TIMEOUT_SECONDS = 30
NCBI_TOOL_NAME = "cBioAbstractor"
NCBI_CONTACT_EMAIL = os.getenv("NCBI_EMAIL", "cBioAbstractor@example.com")
HTTP_HEADERS = {
    "User-Agent": "cBioAbstractor/1.0 (supplementary-file-curation)",
    "Accept": "*/*",
}
PMC_REQUEST_RETRY_ATTEMPTS = 3
PMC_REQUEST_RETRY_BASE_DELAY_SECONDS = 1.0

_T = TypeVar("_T")


def http_status_code_from_error(exc: Exception) -> int | None:
    if isinstance(exc, PMCRequestError):
        return exc.status_code
    if isinstance(exc, requests.HTTPError):
        response = exc.response
        return response.status_code if response is not None else None
    if isinstance(exc, HTTPError):
        return exc.code
    return None


def classify_pmc_error(exc: Exception) -> PMCErrorClassification:
    if isinstance(exc, PMCRequestError):
        return PMCErrorClassification(
            category=exc.category,
            retryable=exc.retryable,
            status_code=exc.status_code,
        )

    status_code = http_status_code_from_error(exc)
    if status_code == 429:
        return PMCErrorClassification(
            category="rate_limited",
            retryable=True,
            status_code=status_code,
        )
    if status_code in {403, 500, 502, 503, 504}:
        return PMCErrorClassification(
            category="transient_remote_error",
            retryable=True,
            status_code=status_code,
        )
    if status_code == 404:
        return PMCErrorClassification(
            category="remote_not_found",
            retryable=False,
            status_code=status_code,
        )
    if status_code is not None:
        return PMCErrorClassification(
            category="remote_http_error",
            retryable=False,
            status_code=status_code,
        )

    if isinstance(
        exc,
        (requests.Timeout, requests.ConnectionError, TimeoutError, URLError),
    ):
        return PMCErrorClassification(
            category="transient_network_error",
            retryable=True,
        )
    if isinstance(exc, ET.ParseError):
        return PMCErrorClassification(
            category="response_parse_error",
            retryable=False,
        )
    if isinstance(exc, ValueError):
        message = str(exc)
        if "No PMCID found for PMID" in message:
            return PMCErrorClassification(
                category="unresolved_identifier",
                retryable=False,
            )
        if (
            "proof-of-work challenge" in message
            or "Preparing to download" in message
            or "PMC returned an HTML" in message
        ):
            return PMCErrorClassification(
                category="pmc_challenge",
                retryable=True,
            )
        if "PMC XML was not returned" in message:
            return PMCErrorClassification(
                category="unexpected_response",
                retryable=True,
            )
        if (
            "PMID must contain digits." in message
            or "PMCID is empty." in message
            or "Could not parse PMCID" in message
            or "Identifier must be a numeric PMID" in message
        ):
            return PMCErrorClassification(
                category="invalid_identifier",
                retryable=False,
            )
        return PMCErrorClassification(
            category="invalid_response",
            retryable=False,
        )
    if isinstance(exc, requests.RequestException):
        return PMCErrorClassification(
            category="remote_request_error",
            retryable=False,
        )
    return PMCErrorClassification(
        category="unexpected_error",
        retryable=False,
    )


def wrap_pmc_error(operation: str, exc: Exception) -> PMCRequestError:
    if isinstance(exc, PMCRequestError):
        return exc
    return PMCRequestError(
        operation=operation,
        classification=classify_pmc_error(exc),
        detail=str(exc),
    )


def run_with_pmc_retry(
    *,
    operation: str,
    request_fn: Callable[[], _T],
    attempts: int = PMC_REQUEST_RETRY_ATTEMPTS,
    base_delay_seconds: float = PMC_REQUEST_RETRY_BASE_DELAY_SECONDS,
) -> _T:
    last_error: PMCRequestError | None = None
    for attempt in range(1, attempts + 1):
        try:
            return request_fn()
        except Exception as exc:
            last_error = wrap_pmc_error(operation, exc)
            if attempt >= attempts or not last_error.retryable:
                raise last_error from exc
            time.sleep(base_delay_seconds * attempt)

    assert last_error is not None
    raise last_error


def pmid_to_pmcid(pmid: str) -> str:
    """Convert PMID to PMCID using the PMC ID Converter API."""
    clean_pmid = re.sub(r"\D", "", pmid or "")
    if not clean_pmid:
        raise ValueError("PMID must contain digits.")

    def _request_id_converter() -> str:
        params = urlencode(
            {
                "ids": clean_pmid,
                "idtype": "pmid",
                "format": "json",
                "tool": NCBI_TOOL_NAME,
                "email": NCBI_CONTACT_EMAIL,
            }
        )
        request = Request(
            "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
            f"?{params}",
            headers=HTTP_HEADERS,
        )
        with urlopen(request, timeout=NCBI_TIMEOUT_SECONDS) as response:
            payload = response.read().decode("utf-8")

        response_payload = json.loads(payload)
        records = response_payload.get("records") or []
        if not records or not records[0].get("pmcid"):
            raise ValueError(f"No PMCID found for PMID {clean_pmid}.")

        return normalize_pmcid(records[0]["pmcid"])

    return run_with_pmc_retry(
        operation=f"PMID to PMCID resolution for PMID {clean_pmid}",
        request_fn=_request_id_converter,
    )


def fetch_pmc_xml(pmcid: str) -> str:
    normalized_pmcid = normalize_pmcid(pmcid)

    def _request_xml() -> str:
        response = requests.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={
                "db": "pmc",
                "id": pmcid_numeric(normalized_pmcid),
                "retmode": "xml",
            },
            headers=HTTP_HEADERS,
            timeout=NCBI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        if (
            "<article" not in response.text
            and "<pmc-articleset" not in response.text
        ):
            raise ValueError(
                f"PMC XML was not returned for {normalized_pmcid}."
            )
        return response.text

    return run_with_pmc_retry(
        operation=f"PMC XML fetch for {normalized_pmcid}",
        request_fn=_request_xml,
    )


def fetch_pmc_article_html(pmcid: str) -> str:
    normalized_pmcid = normalize_pmcid(pmcid)

    def _request_article_html() -> str:
        response = requests.get(
            f"https://pmc.ncbi.nlm.nih.gov/articles/{normalized_pmcid}/",
            headers=HTTP_HEADERS,
            timeout=NCBI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        if "<html" not in response.text.lower():
            raise ValueError(
                f"PMC article HTML was not returned for {normalized_pmcid}."
            )
        return response.text

    return run_with_pmc_retry(
        operation=f"PMC article HTML fetch for {normalized_pmcid}",
        request_fn=_request_article_html,
    )


def lookup_oa_package_url(pmcid: str) -> str | None:
    normalized_pmcid = normalize_pmcid(pmcid)

    def _request_oa_package_url() -> str | None:
        response = requests.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi",
            params={"id": normalized_pmcid},
            headers=HTTP_HEADERS,
            timeout=NCBI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
        for link in root.iter("link"):
            if (
                link.attrib.get("format") == "tgz"
                and link.attrib.get("href")
            ):
                href = link.attrib["href"]
                return href.replace(
                    "ftp://ftp.ncbi.nlm.nih.gov",
                    "https://ftp.ncbi.nlm.nih.gov",
                )
        return None

    return run_with_pmc_retry(
        operation=f"PMC OA package lookup for {normalized_pmcid}",
        request_fn=_request_oa_package_url,
    )


__all__ = [
    "HTTP_HEADERS",
    "NCBI_CONTACT_EMAIL",
    "NCBI_TIMEOUT_SECONDS",
    "NCBI_TOOL_NAME",
    "PMC_REQUEST_RETRY_ATTEMPTS",
    "PMC_REQUEST_RETRY_BASE_DELAY_SECONDS",
    "classify_pmc_error",
    "fetch_pmc_article_html",
    "fetch_pmc_xml",
    "http_status_code_from_error",
    "lookup_oa_package_url",
    "pmid_to_pmcid",
    "run_with_pmc_retry",
    "wrap_pmc_error",
]
