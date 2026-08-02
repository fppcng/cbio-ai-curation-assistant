"""Shared ReportLab layout primitives for curation reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Table, TableStyle


def as_text(value: Any, default: str = "—") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def join_values(value: Any, default: str = "—") -> str:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(items) if items else default
    return as_text(value, default=default)


def safe_paragraph_text(value: Any) -> str:
    return escape(as_text(value)).replace("\n", "<br/>")


def confidence_palette(value: Any) -> tuple[str, str]:
    try:
        numeric = float(value)
    except Exception:
        return ("#595959", "#F2F2F2")
    if numeric >= 70:
        return ("#375623", "#E2EFDA")
    if numeric >= 40:
        return ("#7F6000", "#FFF2CC")
    return ("#843C0C", "#FCE4D6")


def curability_palette(value: str) -> tuple[str, str]:
    return {
        "Yes": ("#375623", "#E2EFDA"),
        "Partly curatable": ("#7F6000", "#FFF2CC"),
        "Needs manual intervention": ("#843C0C", "#FCE4D6"),
        "—": ("#595959", "#F2F2F2"),
    }.get(value, ("#595959", "#F2F2F2"))


def priority_palette(value: str) -> tuple[str, str]:
    return {
        "HIGH": ("#843C0C", "#FCE4D6"),
        "MEDIUM": ("#7F6000", "#FFF2CC"),
        "LOW": ("#375623", "#E2EFDA"),
        "N/A": ("#595959", "#F2F2F2"),
        "—": ("#595959", "#F2F2F2"),
    }.get(value, ("#595959", "#F2F2F2"))


@dataclass(frozen=True, slots=True)
class ReportLayout:
    styles: StyleSheet1

    def paragraph(self, text: Any, style_name: str = "BodyText") -> Paragraph:
        return Paragraph(safe_paragraph_text(text), self.styles[style_name])

    def section(self, title: str) -> list[Any]:
        return [Paragraph(escape(title), self.styles["SectionHeading"])]

    def metric_table(self, rows: list[list[Any]], col_widths: list[int]) -> Table:
        table = Table(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
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
                ]
            )
        )
        for row_index in range(1, len(rows)):
            if row_index % 2 == 1:
                table.setStyle(
                    TableStyle(
                        [
                            (
                                "BACKGROUND",
                                (0, row_index),
                                (-1, row_index),
                                colors.HexColor("#F8FBFE"),
                            )
                        ]
                    )
                )
        return table


def build_report_layout() -> ReportLayout:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#3E6A8E"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#3E6A8E"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=10.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="LabelSmall",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=10.5,
            textColor=colors.HexColor("#404040"),
        )
    )
    return ReportLayout(styles)


def draw_footer(canvas, doc_obj) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#595959"))
    canvas.drawRightString(
        doc_obj.pagesize[0] - 12 * mm,
        7 * mm,
        f"Page {canvas.getPageNumber()}",
    )
    canvas.restoreState()


__all__ = [
    "ReportLayout",
    "as_text",
    "build_report_layout",
    "confidence_palette",
    "curability_palette",
    "draw_footer",
    "join_values",
    "priority_palette",
    "safe_paragraph_text",
]
