from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


def _as_text(value: Any, default: str = "—") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _join_values(value: Any, default: str = "—") -> str:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(items) if items else default
    return _as_text(value, default=default)


def _format_curability(value: str) -> str:
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


def _safe_paragraph_text(value: Any) -> str:
    text = _as_text(value)
    return escape(text).replace("\n", "<br/>")


def build_curation_report_pdf(meta: dict[str, Any], summary: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title="cBioPortal Curation Report",
        author="cBioAbstractor",
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle",
        parent=styles["Title"],
        fontSize=20,
        leading=24,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#3E6A8E"),
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#3E6A8E"),
        spaceBefore=8,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="BodySmall",
        parent=styles["BodyText"],
        fontSize=8.5,
        leading=10.5,
    ))
    styles.add(ParagraphStyle(
        name="LabelSmall",
        parent=styles["BodyText"],
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor("#404040"),
    ))

    def p(text: Any, style_name: str = "BodyText") -> Paragraph:
        return Paragraph(_safe_paragraph_text(text), styles[style_name])

    def section(title: str) -> list[Any]:
        return [Paragraph(escape(title), styles["SectionHeading"])]

    def metric_table(rows: list[list[Any]], col_widths: list[int]) -> Table:
        table = Table(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCEAF6")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#24425C")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEADING", (0, 0), (-1, -1), 10),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C6D6E3")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        for row_index in range(1, len(rows)):
            if row_index % 2 == 1:
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor("#F8FBFE")),
                ]))
        return table

    def status_color(confidence: float, curability: str, priority: str) -> tuple[Any, Any, Any]:
        confidence_color = colors.HexColor("#843C0C")
        if confidence >= 70:
            confidence_color = colors.HexColor("#375623")
        elif confidence >= 40:
            confidence_color = colors.HexColor("#7F6000")

        curability_color = {
            "Yes": colors.HexColor("#375623"),
            "Partly curatable": colors.HexColor("#7F6000"),
            "Needs manual intervention": colors.HexColor("#843C0C"),
        }.get(curability, colors.black)

        priority_color = {
            "HIGH": colors.HexColor("#843C0C"),
            "MEDIUM": colors.HexColor("#7F6000"),
            "LOW": colors.HexColor("#375623"),
            "N/A": colors.HexColor("#595959"),
        }.get(priority, colors.black)

        return confidence_color, curability_color, priority_color

    def footer(canvas, doc_obj) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#595959"))
        canvas.drawRightString(doc_obj.pagesize[0] - 12 * mm, 7 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    elements: list[Any] = []

    study_title = meta.get("study_title") or summary.get("study_id") or "Untitled study"
    publication = " ".join(
        str(item).strip()
        for item in [meta.get("journal", ""), meta.get("year", "")]
        if str(item).strip()
    )
    citation_bits = [
        publication,
        f"DOI: {meta.get('doi')}" if meta.get("doi") else "",
        f"PMID: {meta.get('pmid')}" if meta.get("pmid") else "",
    ]
    citation = " | ".join(bit for bit in citation_bits if bit)

    elements.append(Paragraph("cBioAbstractor Curation Report", styles["ReportTitle"]))
    elements.append(Paragraph(_safe_paragraph_text(study_title), styles["Heading2"]))
    if citation:
        elements.append(Paragraph(_safe_paragraph_text(citation), styles["LabelSmall"]))
    elements.append(Spacer(1, 8))

    elements.extend(section("Study Overview"))
    overview_rows = [[p("Field", "BodySmall"), p("Value", "BodySmall")]]
    key_findings = meta.get("key_findings") or []
    overview_fields = [
        ("Study title", meta.get("study_title")),
        ("Study ID suggestion", meta.get("study_id_suggestion") or summary.get("study_id")),
        ("Cancer type", meta.get("cancer_type") or summary.get("cancer_type")),
        ("Cancer type full", meta.get("cancer_type_full")),
        ("Number of samples", meta.get("num_samples") or summary.get("num_samples")),
        ("Number of patients", meta.get("num_patients")),
        ("Reference genome", meta.get("reference_genome") or summary.get("reference_genome")),
        ("Sequencing types", _join_values(meta.get("sequencing_types"))),
        ("PMID", meta.get("pmid")),
        ("DOI", meta.get("doi")),
        ("First author surname", meta.get("first_author_surname")),
        ("Year", meta.get("year")),
        ("Journal", meta.get("journal")),
        ("Publication", publication),
        ("Description", meta.get("description")),
        ("Meta description", meta.get("meta_description")),
        ("Primary site", meta.get("primary_site")),
        ("Cohort description", meta.get("cohort_description")),
        ("Data repositories", _join_values(meta.get("data_repositories"))),
        ("Corresponding author(s)", meta.get("corresponding_authors")),
        ("Key findings", "\n".join(f"- {item}" for item in key_findings) if key_findings else "—"),
    ]
    for label, value in overview_fields:
        overview_rows.append([p(label, "BodySmall"), p(value, "BodySmall")])

    elements.append(metric_table(overview_rows, [150, 580]))
    elements.append(Spacer(1, 8))

    elements.extend(section("Supplementary File Analysis"))
    priority_rows = [
        [p("High Priority", "BodySmall"), p("Medium Priority", "BodySmall"), p("Needs Manual Intervention", "BodySmall")],
        [
            p(summary.get("high_priority", 0), "BodySmall"),
            p(summary.get("medium_priority", 0), "BodySmall"),
            p(summary.get("not_loadable", 0), "BodySmall"),
        ],
    ]
    elements.append(metric_table(priority_rows, [180, 180, 210]))
    elements.append(Spacer(1, 8))

    breakdown = summary.get("file_breakdown", []) or []
    if breakdown:
        table_rows = [[
            p("File", "BodySmall"),
            p("Sheet", "BodySmall"),
            p("cBioPortal Format", "BodySmall"),
            p("Confidence", "BodySmall"),
            p("Loadable", "BodySmall"),
            p("Priority", "BodySmall"),
            p("Columns Present", "BodySmall"),
            p("Columns Missing", "BodySmall"),
        ]]
        for row in breakdown:
            confidence_value = float(row.get("confidence", 0) or 0)
            curability_value = _format_curability(str(row.get("curability", "")))
            priority_value = _as_text(row.get("priority"), default="N/A")
            table_rows.append([
                p(row.get("file"), "BodySmall"),
                p(row.get("sheet"), "BodySmall"),
                p(_format_label(str(row.get("cbio_format", "—"))), "BodySmall"),
                p(f"{confidence_value:.0f}%", "BodySmall"),
                p(curability_value, "BodySmall"),
                p(priority_value, "BodySmall"),
                p(", ".join(row.get("req_present", [])) or "—", "BodySmall"),
                p(", ".join(row.get("req_missing", [])) or "None", "BodySmall"),
            ])

        breakdown_table = metric_table(table_rows, [88, 75, 112, 52, 88, 55, 145, 145])
        style_commands: list[tuple[Any, ...]] = []
        for row_index, row in enumerate(breakdown, start=1):
            confidence_value = float(row.get("confidence", 0) or 0)
            curability_value = _format_curability(str(row.get("curability", "")))
            priority_value = _as_text(row.get("priority"), default="N/A")
            confidence_color, curability_color, priority_color = status_color(
                confidence_value,
                curability_value,
                priority_value,
            )
            style_commands.extend([
                ("TEXTCOLOR", (3, row_index), (3, row_index), confidence_color),
                ("FONTNAME", (3, row_index), (3, row_index), "Helvetica-Bold"),
                ("TEXTCOLOR", (4, row_index), (4, row_index), curability_color),
                ("FONTNAME", (4, row_index), (4, row_index), "Helvetica-Bold"),
                ("TEXTCOLOR", (5, row_index), (5, row_index), priority_color),
                ("FONTNAME", (5, row_index), (5, row_index), "Helvetica-Bold"),
            ])
        breakdown_table.setStyle(TableStyle(style_commands))
        elements.append(breakdown_table)
    else:
        elements.append(p("No supplementary file breakdown was generated."))

    elements.append(Spacer(1, 8))
    elements.extend(section("Per-Sheet Classification Detail"))
    if breakdown:
        for row in breakdown:
            label = f"{_as_text(row.get('file'))} - {_as_text(row.get('sheet'))}"
            detail_rows = [
                [p("Field", "BodySmall"), p("Value", "BodySmall")],
                [p("Format", "BodySmall"), p(_format_label(str(row.get("cbio_format", "—"))), "BodySmall")],
                [p("Confidence", "BodySmall"), p(f"{float(row.get('confidence', 0) or 0):.0f}%", "BodySmall")],
                [p("Loadable", "BodySmall"), p(_format_curability(str(row.get("curability", "—"))), "BodySmall")],
                [p("Priority", "BodySmall"), p(row.get("priority") or "—", "BodySmall")],
                [p("Assessment", "BodySmall"), p(row.get("verdict") or "—", "BodySmall")],
                [p("Required columns found", "BodySmall"), p(", ".join(row.get("req_present", [])) or "—", "BodySmall")],
                [p("Required columns missing", "BodySmall"), p(", ".join(row.get("req_missing", [])) or "None", "BodySmall")],
                [p("Optional columns found", "BodySmall"), p(", ".join(row.get("opt_present", [])) or "—", "BodySmall")],
            ]
            elements.append(Paragraph(_safe_paragraph_text(label), styles["Heading3"]))
            elements.append(metric_table(detail_rows, [150, 580]))
            elements.append(Spacer(1, 6))
    else:
        elements.append(p("No per-sheet detail is available."))

    elements.extend(section("Suggested Study Metadata"))
    meta_rows = [
        [p("Field", "BodySmall"), p("Value", "BodySmall")],
        [p("cancer_study_identifier", "BodySmall"), p(summary.get("study_id") or "—", "BodySmall")],
        [p("name", "BodySmall"), p(meta.get("study_title") or "—", "BodySmall")],
        [p("description", "BodySmall"), p(meta.get("meta_description") or meta.get("description") or "—", "BodySmall")],
        [p("cancer_type", "BodySmall"), p(meta.get("cancer_type") or "—", "BodySmall")],
        [p("short_name", "BodySmall"), p(meta.get("study_id_suggestion") or "—", "BodySmall")],
        [p("pmid", "BodySmall"), p(meta.get("pmid") or "—", "BodySmall")],
        [p("groups", "BodySmall"), p("PUBLIC", "BodySmall")],
    ]
    elements.append(metric_table(meta_rows, [180, 550]))

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def build_curation_report_filename(meta: dict[str, Any], summary: dict[str, Any]) -> str:
    raw_name = (
        summary.get("study_id")
        or meta.get("study_id_suggestion")
        or meta.get("study_title")
        or "cbioportal_curation_report"
    )
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", str(raw_name).strip()).strip("._")
    stem = slug or "cbioportal_curation_report"
    return f"{stem}_curation_report.pdf"


def save_curation_report_pdf(
    meta: dict[str, Any],
    summary: dict[str, Any],
    output_path: str | Path | None = None,
) -> str:
    destination = Path(output_path) if output_path else Path(build_curation_report_filename(meta, summary))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(build_curation_report_pdf(meta, summary))
    return str(destination)
