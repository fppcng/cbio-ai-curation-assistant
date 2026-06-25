"""
cBioAbstractor — Streamlit Application
Self-contained Streamlit app for cBioPortal curation support.

This cleaned version keeps only:
  1. Curation Report
  2. File Classification

It removes merge-conflict markers, Docker/backend assumptions, and api_config.py usage.
Set provider-specific credentials in your environment or Streamlit secrets.
"""

from __future__ import annotations

import io
import logging
import os
import re
import shutil
import sys
import tempfile
import traceback
import zipfile
from typing import Any

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from config import LLMConfig, PROVIDER_SPECS, get_provider_default_config, get_provider_names
from llm_client import call_llm_with_retry as _call_llm_with_retry
from llm_client import parse_llm_json as _parse_llm_json
from metadata_merge import merge_missing_metadata_fields

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

load_dotenv(os.path.join(_HERE, ".env"), override=False)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="cBioAbstractor",
    page_icon="🧬",
    layout="wide",
)

# ─────────────────────────────────────────────────────────────────────────────
# LLM session config loading
# Resolution order:
#   1. Provider-specific environment variable
#   2. Streamlit secrets
#   3. Per-session sidebar overrides in st.session_state for keys/models only
# ─────────────────────────────────────────────────────────────────────────────
def _load_secret_value(env_name: str) -> str:
    try:
        return st.secrets.get(env_name, "").strip()
    except Exception:
        return ""


def _load_runtime_default(env_name: str, default: str = "") -> str:
    value = os.environ.get(env_name, "").strip()
    if value:
        return value

    return _load_secret_value(env_name) or default


def _provider_state_key(provider: str, field: str) -> str:
    return f"llm_{provider.lower()}_{field}"


def _ensure_provider_state(provider: str) -> None:
    defaults = get_provider_default_config(provider, value_loader=_load_runtime_default)
    state_defaults = {
        "api_key": defaults.api_key,
        "model": defaults.model,
    }
    for field, value in state_defaults.items():
        key = _provider_state_key(provider, field)
        if key not in st.session_state:
            st.session_state[key] = value


def _ensure_llm_state() -> None:
    for provider in get_provider_names():
        _ensure_provider_state(provider)


def _get_provider_config(provider: str) -> LLMConfig:
    _ensure_provider_state(provider)
    defaults = get_provider_default_config(provider, value_loader=_load_runtime_default)
    return LLMConfig(
        provider=provider,
        api_key=st.session_state.get(_provider_state_key(provider, "api_key"), "").strip(),
        model=st.session_state.get(_provider_state_key(provider, "model"), "").strip(),
        base_url=defaults.base_url,
        api_mode=defaults.api_mode,
    )


def _ensure_choice_value(key: str, options: list[str], default: str) -> None:
    if not options:
        st.session_state[key] = default
        return
    if key not in st.session_state or st.session_state[key] not in options:
        st.session_state[key] = default if default in options else options[0]


def _is_provider_configured(config: LLMConfig) -> bool:
    return bool(config.api_key)


def _default_provider_index() -> int:
    providers = list(get_provider_names())
    for preferred in ("OpenAI", "Anthropic", "LiteLLM"):
        if _is_provider_configured(_get_provider_config(preferred)):
            return providers.index(preferred)
    return providers.index("OpenAI")


def _require_llm_config(provider: str) -> bool:
    config = _get_provider_config(provider)
    spec = PROVIDER_SPECS[provider]
    if provider == "LiteLLM":
        if not config.base_url:
            st.error(f"Please set {spec.base_url_env} in .env or the process environment.")
            return False
    if spec.requires_api_key and not config.api_key:
        st.error(f"Please add your {provider} API key in the sidebar or set {spec.api_key_env}.")
        return False
    if not config.model:
        st.error(f"Please choose a model for {provider}.")
        return False
    return True


_ensure_llm_state()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _save_upload_to_tmp(uploaded_file, filename: str | None = None) -> str:
    tmp_dir = tempfile.mkdtemp()
    safe_name = filename or uploaded_file.name
    path = os.path.join(tmp_dir, safe_name)
    with open(path, "wb") as handle:
        handle.write(uploaded_file.getvalue())
    return path


def _safe_cleanup(*paths: str) -> None:
    for path in paths:
        if not path:
            continue
        try:
            shutil.rmtree(os.path.dirname(path), ignore_errors=True)
        except Exception:
            pass


def _clear_pmc_download_state() -> None:
    tmp_dir = st.session_state.get("pmc_download_tmp_dir")
    if tmp_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    for key in [
        "pmc_download_tmp_dir",
        "pmc_download_pmcid",
        "pmc_download_identifier",
        "pmc_download_identifier_type",
        "pmc_downloaded_files",
    ]:
        st.session_state.pop(key, None)


def _build_download_zip(files: list[dict[str, str]]) -> bytes:
    buffer = io.BytesIO()
    used_names: set[str] = set()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for item in files:
            path = item.get("path", "")
            filename = item.get("filename") or os.path.basename(path)
            if not path or not os.path.exists(path):
                continue

            safe_name = os.path.basename(filename)
            if safe_name in used_names:
                stem, ext = os.path.splitext(safe_name)
                suffix = 2
                while f"{stem}_{suffix}{ext}" in used_names:
                    suffix += 1
                safe_name = f"{stem}_{suffix}{ext}"
            used_names.add(safe_name)
            archive.write(path, arcname=safe_name)

    return buffer.getvalue()


def _detect_pubmed_identifier_type(identifier: str) -> str | None:
    value = identifier.strip()
    if re.fullmatch(r"PMC\d+", value, flags=re.IGNORECASE):
        return "PMCID"
    if re.fullmatch(r"\d+", value):
        return "PMID"
    return None


def _looks_tmp(name: str) -> bool:
    return bool(re.match(r"^tmp[a-z0-9_]{4,}", os.path.splitext(name)[0], re.I))


def _colour_curability(value: str) -> str:
    return {
        "Yes": "background-color:#E2EFDA;color:#375623",
        "Partly curatable": "background-color:#FFF2CC;color:#7F6000",
        "Needs manual intervention": "background-color:#FCE4D6;color:#843C0C",
    }.get(value, "")


def _colour_priority(value: str) -> str:
    return {
        "HIGH": "background-color:#FCE4D6;color:#843C0C",
        "MEDIUM": "background-color:#FFF2CC;color:#7F6000",
        "LOW": "background-color:#E2EFDA;color:#375623",
        "N/A": "background-color:#F2F2F2;color:#595959",
    }.get(value, "")


def _colour_confidence(value: str) -> str:
    try:
        numeric = float(str(value).replace("%", ""))
        if numeric >= 70:
            return "background-color:#E2EFDA;color:#375623"
        if numeric >= 40:
            return "background-color:#FFF2CC;color:#7F6000"
        return "background-color:#FCE4D6;color:#843C0C"
    except Exception:
        return ""


def _truncate_for_log(value: str, limit: int = 2000) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [truncated {len(text) - limit} chars]"


def _curability_label(value: str) -> str:
    return {
        "YES": "Yes",
        "PARTIAL": "Partly curatable",
        "NO": "Needs manual intervention",
    }.get(value, value or "—")


def _format_label(value: str) -> str:
    return {
        "NOT_LOADABLE": "Needs manual intervention",
        "Not directly loadable": "Needs manual intervention",
    }.get(value, value or "—")


# ─────────────────────────────────────────────────────────────────────────────
# Report rendering
# ─────────────────────────────────────────────────────────────────────────────
def _render_inline_report(meta: dict[str, Any], summary: dict[str, Any]) -> None:
    st.markdown("## Study Overview")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Study ID", summary.get("study_id") or "—")
    col2.metric("Cancer Type", summary.get("cancer_type") or "—")
    col3.metric("Samples", summary.get("num_samples") or "—")
    col4.metric("Reference Genome", summary.get("reference_genome") or "—")

    fields = [
        ("Title", meta.get("study_title")),
        ("Cancer type full", meta.get("cancer_type_full")),
        ("Primary site", meta.get("primary_site")),
        ("Publication", " ".join(str(x) for x in [meta.get("journal", ""), meta.get("year", "")] if x).strip()),
        ("PMID", meta.get("pmid")),
        ("DOI", meta.get("doi")),
        ("First author", meta.get("first_author_surname")),
        ("Corresponding author(s)", meta.get("corresponding_authors")),
        ("Cohort", meta.get("cohort_description")),
        ("Summary", meta.get("description")),
    ]
    for label, value in fields:
        if value:
            st.markdown(f"**{label}:** {value}")

    sequencing_types = meta.get("sequencing_types")
    if sequencing_types:
        if isinstance(sequencing_types, list):
            sequencing_types = ", ".join(str(x) for x in sequencing_types)
        st.markdown(f"**Sequencing:** {sequencing_types}")

    repositories = meta.get("data_repositories")
    if repositories:
        if isinstance(repositories, list):
            repositories = ", ".join(str(x) for x in repositories)
        st.markdown(f"**Data repositories:** {repositories}")

    key_findings = meta.get("key_findings") or []
    if key_findings:
        st.markdown("**Key findings:**")
        for finding in key_findings:
            st.markdown(f"- {finding}")

    st.divider()
    st.markdown("## Supplementary File Analysis")

    col1, col2, col3 = st.columns(3)
    col1.metric("High Priority", summary.get("high_priority", 0))
    col2.metric("Medium Priority", summary.get("medium_priority", 0))
    col3.metric("Needs Manual Intervention", summary.get("not_loadable", 0))

    breakdown = summary.get("file_breakdown", []) or []
    if not breakdown:
        st.info("No supplementary file breakdown was generated.")
        return

    table = pd.DataFrame([
        {
            "File": row.get("file", "—"),
            "Sheet": row.get("sheet", "—"),
            "cBioPortal Format": _format_label(row.get("cbio_format", "—")),
            "Confidence": f"{float(row.get('confidence', 0)):.0f}%",
            "Loadable": _curability_label(row.get("curability", "—")),
            "Priority": row.get("priority", "—"),
            "Columns Present": ", ".join(row.get("req_present", [])) or "—",
            "Columns Missing": ", ".join(row.get("req_missing", [])) or "None",
        }
        for row in breakdown
    ])

    styled = (
        table.style
        .map(_colour_curability, subset=["Loadable"])
        .map(_colour_priority, subset=["Priority"])
        .map(_colour_confidence, subset=["Confidence"])
    )
    st.dataframe(styled, width="stretch", hide_index=True)

    st.divider()
    st.markdown("## Per-Sheet Classification Detail")
    for row in breakdown:
        label = f"{row.get('file', '—')} — {row.get('sheet', '—')}"
        with st.expander(label, expanded=False):
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Format:** {_format_label(row.get('cbio_format', '—'))}")
            c2.markdown(f"**Confidence:** {float(row.get('confidence', 0)):.0f}%")
            c3.markdown(f"**Priority:** {row.get('priority', '—')}")

            if row.get("verdict"):
                st.markdown(f"**Assessment:** {row['verdict']}")
            if row.get("req_present"):
                st.success("Required columns found: " + ", ".join(row["req_present"]))
            if row.get("req_missing"):
                st.warning("Required columns missing: " + ", ".join(row["req_missing"]))
            if row.get("opt_present"):
                st.info("Optional columns found: " + ", ".join(row["opt_present"]))

    st.divider()
    st.markdown("## Suggested Study Metadata")
    meta_rows = {
        "cancer_study_identifier": summary.get("study_id") or "—",
        "name": meta.get("study_title") or "—",
        "description": meta.get("meta_description") or meta.get("description") or "—",
        "cancer_type": meta.get("cancer_type") or "—",
        "short_name": meta.get("study_id_suggestion") or "—",
        "pmid": meta.get("pmid") or "—",
        "groups": "PUBLIC",
    }
    meta_df = pd.DataFrame([{"Field": key, "Value": value} for key, value in meta_rows.items()])
    st.dataframe(meta_df, width="stretch", hide_index=True)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("cBioAbstractor")
    st.caption("Automated curation support for cancer genomics studies.")
    st.divider()

    provider_options = list(get_provider_names())
    _ensure_choice_value("llm_provider", provider_options, provider_options[_default_provider_index()])
    provider = st.selectbox(
        "AI provider",
        options=provider_options,
        index=provider_options.index(st.session_state["llm_provider"]),
        key="llm_provider",
    )
    provider_config = PROVIDER_SPECS[provider]
    provider_state = _get_provider_config(provider)
    api_key_key = _provider_state_key(provider, "api_key")

    key_help = (
        f"For local use, you can also set {provider_config.api_key_env} "
        "in your shell environment or Streamlit secrets."
    )
    if provider == "LiteLLM":
        key_help = (
            f"Use {provider_config.api_key_env} for LiteLLM Proxy authentication. "
            f"The LiteLLM endpoint is fixed via {provider_config.base_url_env}."
        )

    st.text_input(
        f"{provider} API key",
        type="password",
        placeholder=provider_config.placeholder,
        help=key_help,
        key=api_key_key,
    )

    provider_state = _get_provider_config(provider)
    if provider == "LiteLLM":
        if provider_state.api_key and provider_state.base_url:
            st.success("LiteLLM configured")
        elif not provider_state.base_url:
            st.warning(f"Set {provider_config.base_url_env} in .env or the process environment")
        else:
            st.warning("LiteLLM API key not configured")
    elif provider_state.api_key:
        st.success(f"{provider} connected")
    else:
        st.warning(f"{provider} API key not configured")

    st.divider()
    st.caption("Version 1.2 — Streamlit only")


# ─────────────────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────────────────
st.title("cBioAbstractor")
st.markdown(
    "Upload a published cancer genomics paper and supplementary data files "
    "to generate a structured cBioPortal curation summary."
)


tab_curate, tab_detect = st.tabs(["Curation Report", "File Classification"])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — Curation Report
# ═════════════════════════════════════════════════════════════════════════════
with tab_curate:
    st.subheader("Curation Report Generator")
    st.markdown(
        "Upload a paper PDF with local supplementary files, or enter a PMID/PMCID "
        "to retrieve metadata and supplementary files from PubMed Central."
    )

    try:
        from spec_fetcher import fetch_spec

        spec_info = fetch_spec()
        if spec_info.get("source") == "live":
            st.caption(f"Format specifications loaded from live cBioPortal docs ({len(spec_info.get('specs', []))} formats).")
        else:
            st.caption("Using embedded cBioPortal format specifications.")
    except Exception:
        st.caption("Using embedded cBioPortal format specifications.")

    st.divider()
    supp_source = st.radio(
        "Supplementary source",
        options=["Upload files", "PubMed Central"],
        horizontal=True,
        key="supp_source",
    )

    paper_pdf = None
    supp_files = []
    pmc_identifier = ""
    pmc_identifier_type = None

    if supp_source == "Upload files":
        if st.session_state.get("pmc_downloaded_files"):
            _clear_pmc_download_state()
        col_pdf, col_supp = st.columns(2)
        with col_pdf:
            paper_pdf = st.file_uploader("Main paper PDF", type=["pdf"], key="paper_pdf")
        with col_supp:
            supp_files = st.file_uploader(
                "Supplementary files",
                type=["xlsx", "xls", "csv", "tsv", "txt", "tab", "maf", "doc", "docx", "pdf"],
                accept_multiple_files=True,
                key="supp_files",
            )
    else:
        with st.container():
            pmc_identifier = st.text_input(
                "PMID or PMCID",
                placeholder="34493867 or PMC8432745",
                key="pmc_identifier",
            ).strip()
            pmc_identifier_type = _detect_pubmed_identifier_type(pmc_identifier)
            if pmc_identifier and pmc_identifier_type:
                st.caption(f"Detected {pmc_identifier_type}.")
            elif pmc_identifier:
                st.warning("Enter a numeric PMID or a PMCID such as PMC8432745.")

            current_download_matches = (
                st.session_state.get("pmc_download_identifier") == pmc_identifier
                and st.session_state.get("pmc_download_identifier_type") == pmc_identifier_type
            )
            if pmc_identifier and not current_download_matches:
                _clear_pmc_download_state()

            if st.button(
                "Download supplementary files and study full text",
                disabled=not pmc_identifier_type,
                key="download_pmc_supp_files",
            ):
                from pmc_supplement_fetcher import download_pmc_supplements

                _clear_pmc_download_state()
                pmc_tmp_dir = tempfile.mkdtemp()
                try:
                    with st.spinner("Downloading supplementary files from PubMed Central..."):
                        pmcid, downloaded = download_pmc_supplements(
                            identifier=pmc_identifier,
                            identifier_type=pmc_identifier_type,
                            output_dir=pmc_tmp_dir,
                        )
                    st.session_state["pmc_download_tmp_dir"] = pmc_tmp_dir
                    st.session_state["pmc_download_pmcid"] = pmcid
                    st.session_state["pmc_download_identifier"] = pmc_identifier
                    st.session_state["pmc_download_identifier_type"] = pmc_identifier_type
                    st.session_state["pmc_downloaded_files"] = [
                        {
                            "path": item.path,
                            "filename": item.filename,
                            "source_url": item.source_url,
                        }
                        for item in downloaded
                    ]
                    st.success(f"Downloaded {len(downloaded)} supplementary file(s) from {pmcid}.")
                except Exception as exc:
                    shutil.rmtree(pmc_tmp_dir, ignore_errors=True)
                    print(f"Supplementary download failed: {exc}", file=sys.stderr)
                    traceback.print_exc()
                    st.error(
                        "Impossible to retrieve supplementary files for this identifier. "
                        "Please check that the PMID or PMCID is correct."
                    )

        downloaded_files = st.session_state.get("pmc_downloaded_files") or []
        if downloaded_files:
            st.success(
                f"Ready: {len(downloaded_files)} file(s) from "
                f"{st.session_state.get('pmc_download_pmcid', 'PMC')}."
            )
            for idx, item in enumerate(downloaded_files):
                cols = st.columns([0.08, 0.52, 0.40])
                if cols[0].button("X", key=f"remove_pmc_file_{idx}", help="Remove this file"):
                    try:
                        os.remove(item["path"])
                    except OSError:
                        pass
                    st.session_state["pmc_downloaded_files"] = [
                        row for row_idx, row in enumerate(downloaded_files) if row_idx != idx
                    ]
                    st.rerun()
                cols[1].write(item["filename"])
                cols[2].caption(item["source_url"])

            zip_bytes = _build_download_zip(downloaded_files)
            if zip_bytes:
                st.download_button(
                    "Download selected supplementary files (.zip)",
                    data=zip_bytes,
                    file_name=f"{st.session_state.get('pmc_download_pmcid', 'pmc')}_supplementary_files.zip",
                    mime="application/zip",
                    key="download_pmc_supp_zip",
                )

    if supp_files:
        st.markdown("#### Confirm uploaded filenames")
        st.caption("Edit names here only if Streamlit shows temporary filenames.")
        cols = st.columns(min(len(supp_files), 3))
        for idx, file in enumerate(supp_files):
            ext = os.path.splitext(file.name)[1] or ".xlsx"
            auto_name = f"Supplementary_Data_{idx + 1}{ext}"
            default = auto_name if _looks_tmp(file.name) else file.name
            st.text_input(f"File {idx + 1}", value=default, key=f"fname_{idx}")

    with st.expander("Options"):
        model_key = _provider_state_key(provider, "model")
        if provider_config.supports_custom_model:
            model = st.text_input(
                f"{provider} model",
                help=(
                    "Enter a model string or gateway alias for this provider. "
                    "The override is stored only in the current Streamlit session."
                ),
                key=model_key,
            ).strip()
        else:
            model_options = list(provider_config.model_choices)
            _ensure_choice_value(model_key, model_options, provider_state.model or provider_config.default_model)
            model = st.selectbox(
                f"{provider} model",
                options=model_options,
                index=model_options.index(st.session_state[model_key]),
                key=model_key,
            )

    missing_supp_source = (
        (supp_source == "Upload files" and not supp_files)
        or (supp_source == "PubMed Central" and not st.session_state.get("pmc_downloaded_files"))
    )
    missing_paper_source = supp_source == "Upload files" and paper_pdf is None

    if st.button(
        "Generate Curation Report",
        disabled=missing_paper_source or missing_supp_source,
        type="primary",
    ):
        if not _require_llm_config(provider):
            st.stop()

        active_llm_config = _get_provider_config(provider)

        pdf_tmp: str | None = None
        supp_tmps: list[str] = []

        try:
            with st.spinner("Saving uploaded files..."):
                if supp_source == "Upload files":
                    pdf_tmp = _save_upload_to_tmp(paper_pdf)
                    for idx, uploaded in enumerate(supp_files or []):
                        filename = st.session_state.get(f"fname_{idx}") or uploaded.name
                        supp_tmps.append(_save_upload_to_tmp(uploaded, filename=filename))
                else:
                    downloaded_files = st.session_state.get("pmc_downloaded_files") or []
                    supp_tmps.extend(item["path"] for item in downloaded_files)

            meta: dict[str, Any] = {}
            if supp_source == "PubMed Central":
                with st.spinner("Step 1 of 2 — Extracting study metadata from PMC XML..."):
                    from cbioportal_curator import (
                        SYSTEM_PROMPT_CURATOR,
                        extract_metadata_from_xml,
                        extract_xml_llm_text,
                    )
                    from pmc_supplement_fetcher import _fetch_pmc_xml

                    pmcid = st.session_state.get("pmc_download_pmcid")
                    if not pmcid:
                        raise RuntimeError("Missing PMCID for PMC metadata extraction.")

                    xml_text = _fetch_pmc_xml(pmcid)
                    meta = extract_metadata_from_xml(xml_text)
                    llm_text = extract_xml_llm_text(xml_text)
                    if llm_text.strip():
                        raw_meta = ""
                        try:
                            raw_meta = _call_llm_with_retry(
                                config=active_llm_config,
                                system=SYSTEM_PROMPT_CURATOR,
                                user_content=llm_text[:40000],
                                max_tokens=2000,
                            )
                            meta = merge_missing_metadata_fields(meta, _parse_llm_json(raw_meta))
                        except Exception:
                            logger.exception(
                                "PMC XML metadata completion failed: provider=%s model=%s api_mode=%s base_url=%s pmcid=%s llm_text_len=%s raw_meta=%r",
                                active_llm_config.provider,
                                active_llm_config.model,
                                active_llm_config.api_mode,
                                active_llm_config.base_url,
                                pmcid,
                                len(llm_text),
                                _truncate_for_log(raw_meta),
                            )
                            st.warning(
                                "XML metadata completion returned unexpected format. "
                                "Continuing with structured XML metadata only."
                            )
                    else:
                        st.warning("Could not extract text from the PMC XML. Using structured XML metadata only.")
            else:
                with st.spinner("Step 1 of 2 — Extracting study metadata from PDF..."):
                    from cbioportal_curator import SYSTEM_PROMPT_CURATOR, _extract_pdf_text

                    pdf_text = _extract_pdf_text(pdf_tmp)
                    if pdf_text.strip():
                        raw_meta = _call_llm_with_retry(
                            config=active_llm_config,
                            system=SYSTEM_PROMPT_CURATOR,
                            user_content=pdf_text[:40000],
                            max_tokens=2000,
                        )
                        try:
                            meta = _parse_llm_json(raw_meta)
                        except Exception:
                            st.warning("Metadata extraction returned unexpected format. Continuing with file classification.")
                            meta = {}
                    else:
                        st.warning("Could not extract text from the PDF. Metadata fields will be blank.")

            with st.spinner(f"Step 2 of 2 — Classifying {len(supp_tmps)} supplementary file(s)..."):
                from cbioportal_curator import _analyse_supplementary_files

                records = _analyse_supplementary_files(supp_tmps)

            summary = {
                "study_id": meta.get("study_id_suggestion") or "—",
                "cancer_type": meta.get("cancer_type") or "—",
                "num_samples": meta.get("num_samples") or "—",
                "reference_genome": meta.get("reference_genome") or "—",
                "files_analysed": len(supp_tmps),
                "sheets_analysed": len(records),
                "high_priority": sum(1 for r in records if r.get("priority") == "HIGH"),
                "medium_priority": sum(1 for r in records if r.get("priority") == "MEDIUM"),
                "not_loadable": sum(1 for r in records if r.get("curability") == "NO"),
                "file_breakdown": [
                    {
                        "file": r.get("file", "—"),
                        "sheet": r.get("sheet", "—"),
                        "cbio_format": r.get("cbio_target_file", "—"),
                        "curability": r.get("curability", "NO"),
                        "priority": r.get("priority", "N/A"),
                        "confidence": r.get("confidence", 0),
                        "verdict": r.get("verdict", ""),
                        "req_present": r.get("required_present", []),
                        "req_missing": r.get("required_missing", []),
                        "opt_present": r.get("optional_present", []),
                    }
                    for r in records
                ],
            }

        except Exception as exc:
            st.error(f"Curation failed: {exc}")
            with st.expander("Error details"):
                st.code(traceback.format_exc())
            st.stop()
        finally:
            if supp_source == "Upload files":
                _safe_cleanup(pdf_tmp or "", *supp_tmps)
            else:
                _safe_cleanup(pdf_tmp or "")

        st.success("Curation complete.")
        try:
            from pdf_report import build_curation_report_filename, save_curation_report_pdf

            pdf_name = build_curation_report_filename(meta, summary)
            pdf_path = save_curation_report_pdf(
                meta,
                summary,
                os.path.join(tempfile.gettempdir(), pdf_name),
            )
            with open(pdf_path, "rb") as handle:
                pdf_bytes = handle.read()
            st.download_button(
                "Download PDF report",
                data=pdf_bytes,
                file_name=pdf_name,
                mime="application/pdf",
            )
            st.caption(f"PDF report created at `{pdf_path}`.")
        except Exception as exc:
            logger.exception("PDF report generation failed: %s", exc)
            st.warning("PDF export is currently unavailable. Check that PDF dependencies are installed.")
        st.divider()
        _render_inline_report(meta, summary)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — File Classification
# ═════════════════════════════════════════════════════════════════════════════
with tab_detect:
    st.subheader("File Classification")
    st.markdown(
        "Upload one supplementary file to detect which cBioPortal format it most closely matches."
    )

    detect_file = st.file_uploader(
        "File to classify",
        type=["xlsx", "xls", "csv", "tsv", "txt", "tab", "maf"],
        key="detect_file",
    )
    use_ai = st.checkbox("Use AI for ambiguous files", value=True, key="use_ai_detection")

    if st.button("Classify File", disabled=detect_file is None):
        if use_ai and not _require_llm_config(provider):
            st.stop()

        try:
            from cbio_detector import detect_file_type
            from file_parser import parse_file
        except Exception as exc:
            st.error(f"Could not load classification modules: {exc}")
            st.stop()

        with st.spinner("Parsing file..."):
            try:
                df = parse_file(detect_file.getvalue(), detect_file.name)
            except Exception as exc:
                st.error(f"Could not read file: {exc}")
                st.stop()

        st.markdown("#### File Preview")
        st.dataframe(df.head(10), width="stretch")

        active_llm_config = _get_provider_config(provider) if use_ai else None
        with st.spinner("Classifying file..."):
            try:
                result = detect_file_type(
                    df,
                    llm_config=active_llm_config,
                )
            except Exception as exc:
                st.error(f"Classification failed: {exc}")
                st.stop()

        st.divider()
        col1, col2, col3 = st.columns(3)
        col1.metric("Detected Format", result.get("type", "—"))
        col2.metric("Confidence", f"{float(result.get('confidence', 0)) * 100:.0f}%")
        col3.metric("Method", "Rule-based" if result.get("method") == "heuristic" else result.get("method", "—"))

        if result.get("reasoning"):
            st.info(result["reasoning"])
        if result.get("low_confidence"):
            st.warning("Confidence is low — please verify the detected format manually.")

        mappings = result.get("column_mappings") or {}
        if mappings:
            st.markdown("#### Suggested Column Mappings")
            st.dataframe(
                pd.DataFrame(list(mappings.items()), columns=["Original Column", "cBioPortal Column"]),
                width="stretch",
                hide_index=True,
            )

        try:
            from spec_match import classify_sheet

            spec_result = classify_sheet(df)
            with st.expander("Detailed classification scores"):
                st.markdown(f"**Best match:** {spec_result.format_key} ({spec_result.confidence:.1f}% confidence)")
                st.markdown(f"**Target file:** {spec_result.target_file}")
                if spec_result.required_missing:
                    st.warning("Missing required columns: " + ", ".join(spec_result.required_missing))
                if spec_result.required_present:
                    st.success("Required columns found: " + ", ".join(spec_result.required_present))
                if spec_result.all_scores:
                    st.dataframe(pd.DataFrame(spec_result.all_scores), width="stretch", hide_index=True)
        except Exception:
            pass
