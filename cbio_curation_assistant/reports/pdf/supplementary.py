"""Build supplementary-analysis PDF sections."""

from __future__ import annotations

from typing import Any

from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from cbio_curation_assistant.reports.pdf.layout import (
    ReportLayout,
    as_text,
    confidence_palette,
    curability_palette,
    priority_palette,
    safe_paragraph_text,
)
from cbio_curation_assistant.reports.presentation import (
    format_curability,
    format_label,
)


def _apply_breakdown_colors(table: Table, breakdown: list[dict[str, Any]]) -> None:
    commands: list[tuple[Any, ...]] = []
    for row_index, row in enumerate(breakdown, start=1):
        confidence_value = float(row.get("confidence", 0) or 0)
        curability_value = format_curability(str(row.get("curability", "")))
        priority_value = as_text(row.get("priority"), default="N/A")
        confidence_text, confidence_bg = confidence_palette(confidence_value)
        curability_text, curability_bg = curability_palette(curability_value)
        priority_text, priority_bg = priority_palette(priority_value)
        for column, text_color, background in (
            (3, confidence_text, confidence_bg),
            (4, curability_text, curability_bg),
            (5, priority_text, priority_bg),
        ):
            commands.extend(
                [
                    (
                        "BACKGROUND",
                        (column, row_index),
                        (column, row_index),
                        colors.HexColor(background),
                    ),
                    (
                        "TEXTCOLOR",
                        (column, row_index),
                        (column, row_index),
                        colors.HexColor(text_color),
                    ),
                    (
                        "FONTNAME",
                        (column, row_index),
                        (column, row_index),
                        "Helvetica-Bold",
                    ),
                ]
            )
    table.setStyle(TableStyle(commands))


def _build_breakdown_table(
    breakdown: list[dict[str, Any]],
    layout: ReportLayout,
) -> Table:
    p = layout.paragraph
    rows = [
        [
            p("File", "BodySmall"),
            p("Sheet", "BodySmall"),
            p("cBioPortal Format", "BodySmall"),
            p("Confidence", "BodySmall"),
            p("Loadable", "BodySmall"),
            p("Priority", "BodySmall"),
            p("Columns Present", "BodySmall"),
            p("Columns Missing", "BodySmall"),
        ]
    ]
    for row in breakdown:
        confidence_value = float(row.get("confidence", 0) or 0)
        rows.append(
            [
                p(row.get("file"), "BodySmall"),
                p(row.get("sheet"), "BodySmall"),
                p(format_label(str(row.get("cbio_format", "—"))), "BodySmall"),
                p(f"{confidence_value:.0f}%", "BodySmall"),
                p(
                    format_curability(str(row.get("curability", ""))),
                    "BodySmall",
                ),
                p(as_text(row.get("priority"), default="N/A"), "BodySmall"),
                p(", ".join(row.get("req_present", [])) or "—", "BodySmall"),
                p(", ".join(row.get("req_missing", [])) or "None", "BodySmall"),
            ]
        )
    table = layout.metric_table(rows, [88, 75, 112, 52, 88, 55, 145, 145])
    _apply_breakdown_colors(table, breakdown)
    return table


def _build_detail_elements(
    breakdown: list[dict[str, Any]],
    layout: ReportLayout,
) -> list[Any]:
    p = layout.paragraph
    elements: list[Any] = []
    if not breakdown:
        return [p("No per-sheet detail is available.")]

    for row in breakdown:
        label = f"{as_text(row.get('file'))} - {as_text(row.get('sheet'))}"
        detail_rows = [
            [p("Field", "BodySmall"), p("Value", "BodySmall")],
            [
                p("Format", "BodySmall"),
                p(format_label(str(row.get("cbio_format", "—"))), "BodySmall"),
            ],
            [
                p("Confidence", "BodySmall"),
                p(f"{float(row.get('confidence', 0) or 0):.0f}%", "BodySmall"),
            ],
            [
                p("Loadable", "BodySmall"),
                p(
                    format_curability(str(row.get("curability", "—"))),
                    "BodySmall",
                ),
            ],
            [p("Priority", "BodySmall"), p(row.get("priority") or "—", "BodySmall")],
            [
                p("Assessment", "BodySmall"),
                p(row.get("verdict") or "—", "BodySmall"),
            ],
            [
                p("Required columns found", "BodySmall"),
                p(", ".join(row.get("req_present", [])) or "—", "BodySmall"),
            ],
            [
                p("Required columns missing", "BodySmall"),
                p(", ".join(row.get("req_missing", [])) or "None", "BodySmall"),
            ],
            [
                p("Optional columns found", "BodySmall"),
                p(", ".join(row.get("opt_present", [])) or "—", "BodySmall"),
            ],
        ]
        elements.append(
            Paragraph(safe_paragraph_text(label), layout.styles["Heading3"])
        )
        detail_table = layout.metric_table(detail_rows, [150, 580])
        confidence_text, confidence_bg = confidence_palette(
            float(row.get("confidence", 0) or 0)
        )
        curability_text, curability_bg = curability_palette(
            format_curability(str(row.get("curability", "—")))
        )
        priority_text, priority_bg = priority_palette(
            as_text(row.get("priority"), default="N/A")
        )
        detail_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (1, 2), (1, 2), colors.HexColor(confidence_bg)),
                    ("TEXTCOLOR", (1, 2), (1, 2), colors.HexColor(confidence_text)),
                    ("FONTNAME", (1, 2), (1, 2), "Helvetica-Bold"),
                    ("BACKGROUND", (1, 3), (1, 3), colors.HexColor(curability_bg)),
                    ("TEXTCOLOR", (1, 3), (1, 3), colors.HexColor(curability_text)),
                    ("FONTNAME", (1, 3), (1, 3), "Helvetica-Bold"),
                    ("BACKGROUND", (1, 4), (1, 4), colors.HexColor(priority_bg)),
                    ("TEXTCOLOR", (1, 4), (1, 4), colors.HexColor(priority_text)),
                    ("FONTNAME", (1, 4), (1, 4), "Helvetica-Bold"),
                ]
            )
        )
        elements.extend((detail_table, Spacer(1, 6)))
    return elements


def build_supplementary_elements(
    summary: dict[str, Any],
    layout: ReportLayout,
) -> list[Any]:
    p = layout.paragraph
    elements: list[Any] = []
    elements.extend(layout.section("Supplementary File Analysis"))
    priority_rows = [
        [
            p("High Priority", "BodySmall"),
            p("Medium Priority", "BodySmall"),
            p("Needs Manual Intervention", "BodySmall"),
        ],
        [
            p(summary.get("high_priority", 0), "BodySmall"),
            p(summary.get("medium_priority", 0), "BodySmall"),
            p(summary.get("not_loadable", 0), "BodySmall"),
        ],
    ]
    elements.extend((layout.metric_table(priority_rows, [180, 180, 210]), Spacer(1, 8)))

    breakdown = summary.get("file_breakdown", []) or []
    if breakdown:
        elements.append(_build_breakdown_table(breakdown, layout))
    else:
        elements.append(p("No supplementary file breakdown was generated."))

    elements.append(Spacer(1, 8))
    elements.extend(layout.section("Per-Sheet Classification Detail"))
    elements.extend(_build_detail_elements(breakdown, layout))
    return elements


__all__ = ["build_supplementary_elements"]
