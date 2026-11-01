"""
PDF analysis report generation (reportlab).

One page-per-need layout: header, category score table, findings, strengths /
weaknesses / recommendations, job match (when available), and the mandatory
"estimated score" disclaimer. Downloaded from the UI after every analysis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

import config
from config import get_logger

logger = get_logger("report_pdf")

# Palette used consistently across ReportIQ documents.
NAVY = colors.HexColor("#12203c")
INDIGO = colors.HexColor("#5468ff")
SLATE = colors.HexColor("#5b6478")
LIGHT = colors.HexColor("#f1f4fb")
GREEN = colors.HexColor("#2dba8e")
AMBER = colors.HexColor("#e9a13b")
RED = colors.HexColor("#e35d6a")


def _style(name: str, **kw) -> ParagraphStyle:
    """Fresh paragraph style (never touches the sample stylesheet registry)."""
    defaults = {"fontName": "Helvetica", "fontSize": 9, "leading": 12}
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


def _score_color(score: float) -> colors.Color:
    if score >= 75:
        return GREEN
    if score >= 50:
        return AMBER
    return RED


class ReportPDFBuilder:
    """Render a ReportIQ analysis report as a branded PDF."""

    TITLE = "ResumeIQ — Resume Analysis Report"
    FOOTER = ("ResumeIQ generates an estimated ATS compatibility score using its own "
              "documented heuristics. It is not certified by any ATS vendor.")

    def build(self, report: dict[str, Any], out_path: str | Path) -> Path:
        """Create the PDF and return the written path."""
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(
            str(path), pagesize=A4,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=16 * mm, bottomMargin=16 * mm,
            title=self.TITLE, author="ResumeIQ")
        story: list[Any] = []
        self._header(story, report)
        self._overview(story, report)
        self._score_table(story, report)
        self._findings(story, report)
        self._strengths_weaknesses(story, report)
        self._recommendations(story, report)
        match = report.get("job_match")
        if match and (match.get("matching") or match.get("missing") or match.get("partial")):
            self._job_match(story, match)
        self._disclaimer(story)
        doc.build(story, onFirstPage=self._page_decor, onLaterPages=self._page_decor)
        logger.info("Report written to %s", path)
        return path

    # ------------------------------------------------------------------ #
    # sections
    # ------------------------------------------------------------------ #

    def _header(self, story: list, report: dict) -> None:
        h1 = _style("H1", fontName="Helvetica-Bold", fontSize=20, textColor=NAVY, spaceAfter=2)
        sub = _style("sub", fontName="Helvetica", fontSize=10, textColor=SLATE)
        story.append(Paragraph(self.TITLE, h1))
        meta = (f"File: {report.get('file_name', 'resume')}  ·  "
                f"Type: {report.get('file_type', '?').upper()}  ·  "
                f"Words: {report.get('word_count', 0)}  ·  Pages: {report.get('pages', '?')}")
        story.append(Paragraph(meta, sub))
        story.append(Spacer(1, 6))

    def _overview(self, story: list, report: dict) -> None:
        overall = float(report.get("ats", {}).get("overall", 0))
        h2 = _style("H2", fontName="Helvetica-Bold", fontSize=13, textColor=NAVY, spaceBefore=6)
        big = _style("big", fontName="Helvetica-Bold", fontSize=26,
                     textColor=NAVY, alignment=TA_CENTER)
        box = Table(
            [[Paragraph(f"{overall:.0f}", big),
              Paragraph(f"<b>Estimated ATS compatibility score</b><br/>out of 100 — "
                        f"see the disclaimer at the end of this report.",
                        _style("cap", fontSize=9, textColor=SLATE, leading=13))]],
            colWidths=[38 * mm, 130 * mm])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#dfe6f5")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(box)
        _ = h2
        story.append(Spacer(1, 6))

    def _score_table(self, story: list, report: dict) -> None:
        cats = report.get("ats", {}).get("categories", {})
        if not cats:
            return
        h2 = _style("H2", fontName="Helvetica-Bold", fontSize=13, textColor=NAVY, spaceBefore=8)
        story.append(Paragraph("Category scores", h2))
        data = [["Category", "Score", "Weight", "Visual"]]
        for name, cat in cats.items():
            score = float(cat.get("score", 0))
            cells = [
                name.title().replace("_", " "),
                f"{score:.0f}/100",
                f"{100 * float(cat.get('weight', 0)):.0f}%",
                self._mini_bar(score),
            ]
            data.append(cells)
        table = Table(data, colWidths=[52 * mm, 20 * mm, 20 * mm, 78 * mm], hAlign="LEFT")
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e3e8f2")),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(table)
        story.append(Spacer(1, 4))

    def _mini_bar(self, score: float) -> Table:
        filled = max(1, int(score))
        bar = Table([["", ""]], colWidths=[filled * 1.0 * mm + 1, 60 * mm])
        bar.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), _score_color(score)),
            ("BACKGROUND", (1, 0), (1, 0), LIGHT),
            ("LINEBELOW", (0, 0), (-1, -1), 4, colors.white),
        ]))
        wrap = Table([[bar]], colWidths=[62 * mm])
        wrap.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e9edf7")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d7def0")),
            ("LEFTPADDING", (0, 0), (-1, -1), 1), ("TOPPADDING", (0, 0), (-1, -1), 1),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1), ("RIGHTPADDING", (0, 0), (-1, -1), 1),
        ]))
        return wrap

    def _findings(self, story: list, report: dict) -> None:
        ats = report.get("ats", {})
        h2 = _style("H2", fontName="Helvetica-Bold", fontSize=13, textColor=NAVY, spaceBefore=8)
        story.append(Paragraph("Findings & checks", h2))
        bullet = _style("li", fontSize=9.5, leading=13, textColor=SLATE, leftIndent=8)

        for name, cat in ats.get("categories", {}).items():
            icon = {"pass": "✔", "warn": "▲", "fail": "✖"}
            lines: list[str] = []
            for check in cat.get("checks", []):
                mark = icon.get(check.get("status"), "•")
                detail = f" — {check['detail']}" if check.get("detail") else ""
                lines.append(f"{mark} {check['label']}{detail}")
            if not lines:
                continue
            block = [Paragraph(f"<b>{name.title().replace('_', ' ')}</b>", bullet)]
            for line in lines:
                block.append(Paragraph(line, bullet))
            story.append(KeepTogether(block))

        writing = ats.get("writing") or {}
        if writing.get("spelling") or writing.get("grammar"):
            story.append(Paragraph("<b>Writing quality</b>", bullet))
            for issue in (writing.get("spelling") or [])[:12]:
                story.append(Paragraph(f"• {issue['message']} → {issue.get('suggestion', '')}", bullet))
            for issue in (writing.get("grammar") or [])[:12]:
                story.append(Paragraph(f"• {issue['message']} → {issue.get('suggestion', '')}", bullet))

    def _strengths_weaknesses(self, story: list, report: dict) -> None:
        ats = report.get("ats", {})
        h2 = _style("H2", fontName="Helvetica-Bold", fontSize=13, textColor=NAVY, spaceBefore=8)
        story.append(Paragraph("Strengths & weaknesses", h2))
        cols = Table(
            [[Paragraph("<b>Strengths</b>", _style("sh", fontName="Helvetica-Bold", fontSize=10, textColor=GREEN)),
              Paragraph("<b>Weaknesses</b>", _style("wh", fontName="Helvetica-Bold", fontSize=10, textColor=RED))],
             [Paragraph("• " + "<br/>• ".join(ats.get("strengths") or []) or "—", _style("s", fontSize=9, leading=13)),
              Paragraph("• " + "<br/>• ".join(ats.get("weaknesses") or []) or "—", _style("w", fontSize=9, leading=13))]],
            colWidths=[86 * mm, 86 * mm])
        cols.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#dde3f2")),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d2ea")),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(cols)

    def _recommendations(self, story: list, report: dict) -> None:
        h2 = _style("H2", fontName="Helvetica-Bold", fontSize=13, textColor=NAVY, spaceBefore=8)
        story.append(Paragraph("Top recommendations", h2))
        li = _style("li2", fontSize=9.5, leading=13, leftIndent=10, textColor=SLATE)
        tips = report.get("ats", {}).get("recommendations") or []
        if not tips:
            story.append(Paragraph("No critical recommendations — keep iterating.", li))
        for i, tip in enumerate(tips[:14], start=1):
            story.append(Paragraph(f"{i}. {tip}", li))

    def _job_match(self, story: list, match: dict) -> None:
        h2 = _style("H2", fontName="Helvetica-Bold", fontSize=13, textColor=NAVY, spaceBefore=8)
        story.append(Paragraph(f"Job description match — {match.get('job_title') or 'Unnamed role'}", h2))
        body = _style("jb", fontSize=9.5, leading=13, textColor=SLATE)
        story.append(Paragraph(f"Match score (estimated): <b>{match.get('match_score', 0):.0f}%</b>", body))
        if match.get("matching"):
            story.append(Paragraph("<b>Matching skills:</b> " + ", ".join(match["matching"]), body))
        if match.get("partial"):
            story.append(Paragraph("<b>Partial matches:</b> " + ", ".join(match["partial"]), body))
        if match.get("missing"):
            story.append(Paragraph("<b>Missing in resume:</b> " + ", ".join(match["missing"]), body))

    def _disclaimer(self, story: list) -> None:
        story.append(Spacer(1, 10))
        note = _style("note", fontSize=8, leading=11, textColor=SLATE)
        story.append(Paragraph(
            f"<i>{self.FOOTER} Findings marked 'heuristic' are pattern-based warnings that "
            f"may require human verification.</i>", note))

    # -- page decorations ----------------------------------------------------
    def _page_decor(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.setFillColor(NAVY)
        canvas.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 4.4 * mm, "ResumeIQ · confidential")
        canvas.setFillColor(SLATE)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(18 * mm, 9 * mm, f"Generated by ResumeIQ v{config.APP_VERSION}")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {doc.page}")
        canvas.restoreState()
