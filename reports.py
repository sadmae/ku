"""CSV and PDF summaries. No Streamlit imports."""

from __future__ import annotations

import math
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from calc import DemandResult, NodesResult, PaybackResult
from texts import t

FONT_CANDIDATES = (
    (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ),
)


def fmt_int(value: float | None) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "—"
    rounded = int(round(value))
    sign = "-" if rounded < 0 else ""
    return sign + f"{abs(rounded):,}".replace(",", " ")


def fmt_pct(value: float | None) -> str:
    if value is None or not isinstance(value, (int, float)) or not math.isfinite(value):
        return "—"
    return f"{value * 100:.1f}".replace(".", ",") + "%"


def fmt_pb(value: float | None) -> str:
    if value is None or not isinstance(value, (int, float)):
        return "—"
    if math.isinf(value):
        return "∞"
    if not math.isfinite(value):
        return "—"
    return f"{value:.1f}".replace(".", ",")


def summary_rows(
    lang: str,
    demand: DemandResult,
    nodes: NodesResult,
) -> list[tuple[str, str]]:
    return [
        (t(lang, "csv_metric"), t(lang, "csv_value")),
        (t(lang, "csv_revenue"), fmt_int(demand.revenue)),
        (t(lang, "csv_marketing"), fmt_int(demand.marketing_spend)),
        (t(lang, "csv_ku"), fmt_pct(demand.ku)),
        (t(lang, "csv_min"), fmt_pct(demand.ku_min)),
        (t(lang, "csv_max"), fmt_pct(demand.ku_max)),
        (t(lang, "csv_nodes"), fmt_pct(nodes.ku_nodes)),
        (t(lang, "csv_unc"), fmt_int(nodes.uncovered)),
        (t(lang, "csv_exposure"), fmt_int(nodes.total_exposure)),
    ]


def csv_bytes(rows: list[tuple[str, str]]) -> bytes:
    lines = [f"{_csv_cell(left)};{_csv_cell(right)}" for left, right in rows]
    return ("\ufeff" + "\n".join(lines) + "\n").encode("utf-8")


def find_fonts() -> tuple[Path, Path] | None:
    for regular, bold in FONT_CANDIDATES:
        if regular.is_file() and bold.is_file():
            return regular, bold
    return None


def pdf_bytes(
    lang: str,
    demand: DemandResult,
    nodes: NodesResult,
    payback: PaybackResult,
    narrative: list[str],
) -> bytes | None:
    fonts = find_fonts()
    if fonts is None:
        return None
    regular, bold = fonts
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("Body", "", str(regular))
    pdf.add_font("Body", "B", str(bold))
    pdf.add_page()
    _pdf_text(pdf, t(lang, "title"), 16, bold=True)
    _pdf_text(pdf, t(lang, "sub"), 10)
    pdf.ln(2)
    _pdf_text(pdf, t(lang, "s4t"), 13, bold=True)
    for left, right in summary_rows(lang, demand, nodes)[1:]:
        _pdf_text(pdf, f"{left}: {right}", 11)
    pdf.ln(2)
    for paragraph in narrative:
        _pdf_text(pdf, paragraph, 11)
    if payback.rows:
        pdf.ln(1)
        _pdf_text(pdf, t(lang, "s3t"), 12, bold=True)
        for row in payback.rows:
            name = row.option.name.strip() or "—"
            mark = " *" if row.is_best else ""
            _pdf_text(
                pdf,
                f"{name}{mark}: {t(lang, 'th_pb')} {fmt_pb(row.payback)}, "
                f"{t(lang, 'th_safe')} {fmt_int(row.safe_price)}",
                11,
            )
    pdf.ln(2)
    _pdf_text(pdf, t(lang, "disc"), 9)
    return bytes(pdf.output())


def _pdf_text(pdf: FPDF, text: str, size: int, bold: bool = False) -> None:
    pdf.set_font("Body", "B" if bold else "", size)
    pdf.multi_cell(
        0,
        size * 0.55,
        text,
        align="L",
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )


def _csv_cell(value: str) -> str:
    text = str(value).replace('"', '""')
    if any(char in text for char in ';"\n'):
        return f'"{text}"'
    return text
