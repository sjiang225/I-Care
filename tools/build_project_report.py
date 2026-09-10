#!/usr/bin/env python3
"""Build the formal I-Care project development report DOCX.

The source of truth for prose is deliverables/I-Care项目开发完整汇报.md.
The DOCX follows the documents skill's standard_business_brief preset with a
named CJK-font override (Hiragino Sans GB for East Asian glyphs) and an
editorial-cover first page.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "deliverables" / "I-Care项目开发完整汇报.md"
OUTPUT = ROOT / "deliverables" / "I-Care项目开发完整汇报.docx"
TMP = ROOT / "qa" / "project_report"
ARCH_IMG = TMP / "architecture.png"

# standard_business_brief preset tokens
PAGE_W_DXA = 12240
PAGE_H_DXA = 15840
MARGIN_DXA = 1440
CONTENT_W_DXA = 9360
HEADER_FOOTER_DXA = 708  # 0.492 in
TABLE_INDENT_DXA = 120
CELL_MARGINS = {"top": 80, "bottom": 80, "start": 120, "end": 120}

BLUE = "2E74B5"
DARK_BLUE = "1F4D78"
NAVY = "183B56"
MUTED = "667085"
LIGHT_GRAY = "F2F4F7"
MID_GRAY = "D0D5DD"
INK = "1D2939"
TEAL = "2F7D7A"
LIGHT_TEAL = "E8F4F3"
WHITE = "FFFFFF"

# Named font override for reliable bilingual rendering in Word/LibreOffice.
# Arial Unicode MS is present on the target macOS system and contains the full
# Chinese glyph set; using one family also avoids mixed-baseline substitution.
LATIN_FONT = "Arial Unicode MS"
CJK_FONT = "Arial Unicode MS"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, **kwargs: int) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for side in ("top", "start", "bottom", "end"):
        value = kwargs.get(side)
        if value is None:
            continue
        node = tc_mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_width(cell, width_dxa: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_dxa))
    tc_w.set(qn("w:type"), "dxa")


def set_table_geometry(table, widths: list[int], indent: int = TABLE_INDENT_DXA) -> None:
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")

    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), str(indent))
    tbl_ind.set(qn("w:type"), "dxa")

    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)

    for row in table.rows:
        row.height = None
        for i, cell in enumerate(row.cells):
            set_cell_width(cell, widths[i])
            set_cell_margins(cell, **CELL_MARGINS)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def set_table_borders(table, color: str = MID_GRAY, size: int = 4) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = borders.find(qn(f"w:{edge}"))
        if el is None:
            el = OxmlElement(f"w:{edge}")
            borders.append(el)
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(size))
        el.set(qn("w:color"), color)


def set_run_font(run, size: float | None = None, color: str | None = None,
                 bold: bool | None = None, italic: bool | None = None,
                 font: str = LATIN_FONT) -> None:
    run.font.name = font
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.rFonts
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    fonts.set(qn("w:ascii"), font)
    fonts.set(qn("w:hAnsi"), font)
    fonts.set(qn("w:eastAsia"), CJK_FONT)
    if size is not None:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic


def set_paragraph_borders(paragraph, *, left: str | None = None,
                          bottom: str | None = None, fill: str | None = None) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    if fill:
        shd = OxmlElement("w:shd")
        shd.set(qn("w:fill"), fill)
        p_pr.append(shd)
    if left or bottom:
        p_bdr = OxmlElement("w:pBdr")
        if left:
            el = OxmlElement("w:left")
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), "18")
            el.set(qn("w:space"), "8")
            el.set(qn("w:color"), left)
            p_bdr.append(el)
        if bottom:
            el = OxmlElement("w:bottom")
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), "8")
            el.set(qn("w:space"), "4")
            el.set(qn("w:color"), bottom)
            p_bdr.append(el)
        p_pr.append(p_bdr)


def add_field(paragraph, instruction: str, size: float = 9) -> None:
    run = paragraph.add_run()
    set_run_font(run, size=size, color=MUTED)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = "1"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instr, separate, text, end])


def configure_page(section) -> None:
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.top_margin = Inches(1)
    section.right_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.header_distance = Inches(0.492)
    section.footer_distance = Inches(0.492)


def configure_styles(doc: Document) -> None:
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = LATIN_FONT
    normal.font.size = Pt(11)
    normal._element.rPr.rFonts.set(qn("w:ascii"), LATIN_FONT)
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), LATIN_FONT)
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), CJK_FONT)
    pf = normal.paragraph_format
    pf.alignment = WD_ALIGN_PARAGRAPH.LEFT
    pf.space_before = Pt(0)
    pf.space_after = Pt(6)
    pf.line_spacing = 1.10
    pf.widow_control = True

    heading_tokens = {
        "Heading 1": (16, BLUE, 16, 8),
        "Heading 2": (13, BLUE, 12, 6),
        "Heading 3": (12, DARK_BLUE, 8, 4),
    }
    for name, (size, color, before, after) in heading_tokens.items():
        style = styles[name]
        style.font.name = LATIN_FONT
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style._element.rPr.rFonts.set(qn("w:ascii"), LATIN_FONT)
        style._element.rPr.rFonts.set(qn("w:hAnsi"), LATIN_FONT)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), CJK_FONT)
        sp = style.paragraph_format
        sp.space_before = Pt(before)
        sp.space_after = Pt(after)
        sp.keep_with_next = True
        sp.keep_together = True

    for name in ("List Bullet", "List Number"):
        style = styles[name]
        style.font.name = LATIN_FONT
        style.font.size = Pt(11)
        style._element.rPr.rFonts.set(qn("w:ascii"), LATIN_FONT)
        style._element.rPr.rFonts.set(qn("w:hAnsi"), LATIN_FONT)
        style._element.rPr.rFonts.set(qn("w:eastAsia"), CJK_FONT)
        sp = style.paragraph_format
        sp.space_after = Pt(8)
        sp.line_spacing = 1.167


def create_numbering(doc: Document) -> tuple[int, int]:
    numbering = doc.part.numbering_part.element
    existing_abs = [int(e.get(qn("w:abstractNumId"))) for e in numbering.findall(qn("w:abstractNum"))]
    existing_num = [int(e.get(qn("w:numId"))) for e in numbering.findall(qn("w:num"))]
    next_abs = max(existing_abs or [0]) + 1
    next_num = max(existing_num or [0]) + 1

    def add_abstract(abs_id: int, fmt: str, text: str, font: str | None = None) -> None:
        abstract = OxmlElement("w:abstractNum")
        abstract.set(qn("w:abstractNumId"), str(abs_id))
        multi = OxmlElement("w:multiLevelType")
        multi.set(qn("w:val"), "singleLevel")
        abstract.append(multi)
        lvl = OxmlElement("w:lvl")
        lvl.set(qn("w:ilvl"), "0")
        start = OxmlElement("w:start")
        start.set(qn("w:val"), "1")
        num_fmt = OxmlElement("w:numFmt")
        num_fmt.set(qn("w:val"), fmt)
        lvl_text = OxmlElement("w:lvlText")
        lvl_text.set(qn("w:val"), text)
        suff = OxmlElement("w:suff")
        suff.set(qn("w:val"), "tab")
        ppr = OxmlElement("w:pPr")
        tabs = OxmlElement("w:tabs")
        tab = OxmlElement("w:tab")
        tab.set(qn("w:val"), "num")
        tab.set(qn("w:pos"), "720")
        tabs.append(tab)
        ind = OxmlElement("w:ind")
        ind.set(qn("w:left"), "720")
        ind.set(qn("w:hanging"), "360")
        spacing = OxmlElement("w:spacing")
        spacing.set(qn("w:after"), "160")
        spacing.set(qn("w:line"), "280")
        spacing.set(qn("w:lineRule"), "auto")
        ppr.extend([tabs, ind, spacing])
        lvl.extend([start, num_fmt, lvl_text, suff, ppr])
        if font:
            rpr = OxmlElement("w:rPr")
            rfonts = OxmlElement("w:rFonts")
            rfonts.set(qn("w:ascii"), font)
            rfonts.set(qn("w:hAnsi"), font)
            rpr.append(rfonts)
            lvl.append(rpr)
        abstract.append(lvl)
        numbering.insert(0, abstract)

    def add_num(num_id: int, abs_id: int) -> None:
        num = OxmlElement("w:num")
        num.set(qn("w:numId"), str(num_id))
        abstract_id = OxmlElement("w:abstractNumId")
        abstract_id.set(qn("w:val"), str(abs_id))
        num.append(abstract_id)
        numbering.append(num)

    add_abstract(next_abs, "bullet", "•", "Symbol")
    add_num(next_num, next_abs)
    bullet_num_id = next_num
    add_abstract(next_abs + 1, "decimal", "%1.")
    # Numbered lists receive a fresh num instance per contiguous list so each
    # new procedure/recommendation block restarts at 1.
    add_num(next_num + 1, next_abs + 1)
    number_abstract_id = next_abs + 1
    return bullet_num_id, number_abstract_id


def new_numbering_instance(doc: Document, abstract_id: int) -> int:
    numbering = doc.part.numbering_part.element
    existing = [int(e.get(qn("w:numId"))) for e in numbering.findall(qn("w:num"))]
    num_id = max(existing or [0]) + 1
    num = OxmlElement("w:num")
    num.set(qn("w:numId"), str(num_id))
    abstract = OxmlElement("w:abstractNumId")
    abstract.set(qn("w:val"), str(abstract_id))
    num.append(abstract)
    override = OxmlElement("w:lvlOverride")
    override.set(qn("w:ilvl"), "0")
    start = OxmlElement("w:startOverride")
    start.set(qn("w:val"), "1")
    override.append(start)
    num.append(override)
    numbering.append(num)
    return num_id


def apply_numbering(paragraph, num_id: int) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    num_pr = p_pr.find(qn("w:numPr"))
    if num_pr is None:
        num_pr = OxmlElement("w:numPr")
        p_pr.append(num_pr)
    ilvl = OxmlElement("w:ilvl")
    ilvl.set(qn("w:val"), "0")
    num_id_el = OxmlElement("w:numId")
    num_id_el.set(qn("w:val"), str(num_id))
    num_pr.extend([ilvl, num_id_el])


def add_inline(paragraph, text: str, *, default_size: float | None = None,
               default_color: str | None = None) -> None:
    # Supports the small subset used by the report: **bold** and `code`.
    pattern = re.compile(r"(\*\*.*?\*\*|`.*?`)")
    pos = 0
    for match in pattern.finditer(text):
        if match.start() > pos:
            run = paragraph.add_run(text[pos:match.start()])
            set_run_font(run, size=default_size, color=default_color)
        token = match.group(0)
        if token.startswith("**"):
            run = paragraph.add_run(token[2:-2])
            set_run_font(run, size=default_size, color=default_color, bold=True)
        else:
            run = paragraph.add_run(token[1:-1])
            set_run_font(run, size=(default_size or 11) - 0.5, color=DARK_BLUE,
                         font="Menlo")
            run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), CJK_FONT)
        pos = match.end()
    if pos < len(text):
        run = paragraph.add_run(text[pos:])
        set_run_font(run, size=default_size, color=default_color)


def add_body_paragraph(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 1.10
    p.paragraph_format.widow_control = True
    add_inline(p, text)


def add_list_item(doc: Document, text: str, num_id: int, style: str) -> None:
    p = doc.add_paragraph(style=style)
    apply_numbering(p, num_id)
    p.paragraph_format.left_indent = Inches(0.5)
    p.paragraph_format.first_line_indent = Inches(-0.25)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.167
    add_inline(p, text)


def add_callout(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.18)
    p.paragraph_format.right_indent = Inches(0.12)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.line_spacing = 1.10
    set_paragraph_borders(p, left=TEAL, fill=LIGHT_TEAL)
    add_inline(p, text, default_color=INK)


def table_widths(ncols: int, rows: list[list[str]]) -> list[int]:
    if ncols == 2:
        # Date/status/label tables receive a compact first column.
        max_first = max(len(r[0]) for r in rows if r)
        if max_first <= 14:
            return [2160, 7200]
        return [2880, 6480]
    if ncols == 3:
        return [2592, 2160, 4608]
    if ncols == 4:
        return [1440, 2520, 2520, 2880]
    base = CONTENT_W_DXA // ncols
    widths = [base] * ncols
    widths[-1] += CONTENT_W_DXA - sum(widths)
    return widths


def add_table(doc: Document, rows: list[list[str]]) -> None:
    ncols = len(rows[0])
    table = doc.add_table(rows=len(rows), cols=ncols)
    widths = table_widths(ncols, rows)
    set_table_geometry(table, widths)
    set_table_borders(table)
    set_repeat_table_header(table.rows[0])

    for r_idx, row in enumerate(rows):
        for c_idx, text in enumerate(row):
            cell = table.rows[r_idx].cells[c_idx]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            if r_idx == 0:
                set_cell_shading(cell, LIGHT_GRAY)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.08
            add_inline(p, text, default_size=9.5,
                       default_color=INK)
            for run in p.runs:
                if r_idx == 0:
                    run.bold = True
                    run.font.color.rgb = RGBColor.from_string(DARK_BLUE)
    after = doc.add_paragraph()
    after.paragraph_format.space_before = Pt(0)
    after.paragraph_format.space_after = Pt(2)
    after.add_run("")


def draw_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int],
               color: str = "#7B8A9A", width: int = 6) -> None:
    draw.line([start, end], fill=color, width=width)
    x, y = end
    if end[1] >= start[1]:
        draw.polygon([(x, y), (x - 13, y - 22), (x + 13, y - 22)], fill=color)
    else:
        draw.polygon([(x, y), (x - 13, y + 22), (x + 13, y + 22)], fill=color)


def draw_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], title: str,
             detail: str, fill: str, outline: str, title_font, detail_font) -> None:
    draw.rounded_rectangle(xy, radius=22, fill=fill, outline=outline, width=4)
    x0, y0, x1, y1 = xy
    title_box = draw.multiline_textbbox((0, 0), title, font=title_font, spacing=4,
                                        align="center")
    title_w = title_box[2] - title_box[0]
    draw.multiline_text(((x0 + x1 - title_w) / 2, y0 + 22), title,
                        font=title_font, fill="#183B56", spacing=4, align="center")
    detail_box = draw.multiline_textbbox((0, 0), detail, font=detail_font, spacing=5,
                                         align="center")
    detail_w = detail_box[2] - detail_box[0]
    draw.multiline_text(((x0 + x1 - detail_w) / 2, y0 + 70), detail,
                        font=detail_font, fill="#475467", spacing=5, align="center")


def build_architecture_image() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1800, 1040), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    font_path = "/System/Library/Fonts/Hiragino Sans GB.ttc"
    title_font = ImageFont.truetype(font_path, 39)
    detail_font = ImageFont.truetype(font_path, 27)
    small_font = ImageFont.truetype(font_path, 24)

    # Top-to-bottom flow.
    draw_box(draw, (610, 40, 1190, 170), "用户端 PWA",
             "Next.js · 文字/语音 · Markdown · 趋势图",
             "#EAF2F8", "#2E74B5", title_font, detail_font)
    draw_arrow(draw, (900, 170), (900, 225))
    draw_box(draw, (560, 225, 1240, 365), "FastAPI API 层",
             "SSE 流式回答 · 可选鉴权 · 历史/Wellbeing API",
             "#F2F4F7", "#667085", title_font, detail_font)
    draw_arrow(draw, (900, 365), (900, 420))
    draw_box(draw, (520, 420, 1280, 560), "Coordinator",
             "安全预检 → 意图路由 → 确定性 Agent Plan",
             "#E8F4F3", "#2F7D7A", title_font, detail_font)

    centers = [235, 675, 1125, 1565]
    for cx in centers:
        draw.line([(900, 560), (900, 620), (cx, 620), (cx, 675)],
                  fill="#7B8A9A", width=5)
        draw.polygon([(cx, 675), (cx - 12, 653), (cx + 12, 653)], fill="#7B8A9A")

    boxes = [
        ((45, 675, 425, 850), "Education", "RAG 检索\n带引用的照护指导"),
        ((485, 675, 865, 850), "Emotion", "急性情绪支持\n压力与情绪记录"),
        ((935, 675, 1315, 850), "Peer Companion", "归属感与正常化\n透明 AI 身份"),
        ((1375, 675, 1755, 850), "Resources", "NJ 设施/热线\n主题视频推荐"),
    ]
    fills = ["#EDF4FB", "#FFF4E8", "#F2EEFA", "#EEF7ED"]
    outlines = ["#2E74B5", "#C46A20", "#7153A6", "#4C8A4B"]
    for (xy, title, detail), fill, outline in zip(boxes, fills, outlines):
        draw_box(draw, xy, title, detail, fill, outline, title_font, detail_font)

    draw.rounded_rectangle((285, 920, 1515, 1015), radius=20, fill="#F8FAFC",
                           outline="#98A2B3", width=3)
    storage = "SQLite 数据层：175 个知识切块  |  users / tokens / conversations / messages / wellbeing_logs"
    bbox = draw.textbbox((0, 0), storage, font=small_font)
    draw.text(((1800 - (bbox[2] - bbox[0])) / 2, 951), storage,
              font=small_font, fill="#344054")
    img.save(ARCH_IMG, quality=95)


def add_architecture(doc: Document) -> None:
    build_architecture_image()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(4)
    p.add_run().add_picture(str(ARCH_IMG), width=Inches(6.35))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_before = Pt(0)
    cap.paragraph_format.space_after = Pt(8)
    run = cap.add_run("图 1　I-Care 当前原型架构与多智能体数据流")
    set_run_font(run, size=9.5, color=MUTED, italic=True)


def add_header_footer(section) -> None:
    section.different_first_page_header_footer = True
    # Regular running header, intentionally without a bottom border.
    header = section.header
    hp = header.paragraphs[0]
    hp.clear()
    table = header.add_table(rows=1, cols=2, width=Inches(6.5))
    set_table_geometry(table, [5400, 3960], indent=0)
    for cell in table.rows[0].cells:
        set_cell_margins(cell, top=0, bottom=0, start=0, end=0)
    lp = table.cell(0, 0).paragraphs[0]
    rp = table.cell(0, 1).paragraphs[0]
    rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_run_font(lp.add_run("I-Care"), size=9, color=MUTED, bold=True)
    set_run_font(rp.add_run("项目开发完整汇报"), size=9, color=MUTED)

    footer = section.footer
    fp = footer.paragraphs[0]
    fp.clear()
    ftable = footer.add_table(rows=1, cols=2, width=Inches(6.5))
    set_table_geometry(ftable, [7200, 2160], indent=0)
    for cell in ftable.rows[0].cells:
        set_cell_margins(cell, top=0, bottom=0, start=0, end=0)
    left = ftable.cell(0, 0).paragraphs[0]
    right = ftable.cell(0, 1).paragraphs[0]
    right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    set_run_font(left.add_run("©2026 Rutgers, The State University of New Jersey"),
                 size=8.5, color=MUTED)
    set_run_font(right.add_run("第 "), size=9, color=MUTED)
    add_field(right, "PAGE", 9)
    set_run_font(right.add_run(" 页"), size=9, color=MUTED)

    first_footer = section.first_page_footer
    first_p = first_footer.paragraphs[0]
    first_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_run_font(first_p.add_run(
        "©2026 Rutgers, The State University of New Jersey, All rights reserved."
    ), size=8.5, color=MUTED)


def add_cover(doc: Document) -> None:
    # editorial_cover first-page pattern, adapted for a formal technical report.
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(90)

    kicker = doc.add_paragraph()
    kicker.alignment = WD_ALIGN_PARAGRAPH.CENTER
    kicker.paragraph_format.space_after = Pt(16)
    set_run_font(kicker.add_run("PROJECT DEVELOPMENT REPORT"), size=10.5,
                 color=TEAL, bold=True)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_after = Pt(8)
    set_run_font(title.add_run("I-Care 项目开发完整汇报"), size=30,
                 color=NAVY, bold=True)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(14)
    set_run_font(subtitle.add_run("面向痴呆症家庭照护者的多智能体智能照护系统"),
                 size=15, color=DARK_BLUE)

    descriptor = doc.add_paragraph()
    descriptor.alignment = WD_ALIGN_PARAGRAPH.CENTER
    descriptor.paragraph_format.space_after = Pt(56)
    set_run_font(descriptor.add_run("RAG  ·  Multi-Agent  ·  Wellbeing  ·  NJ Resources"),
                 size=10.5, color=MUTED, bold=True)

    meta_lines = [
        ("项目形态", "Web / Progressive Web App（PWA）研究原型"),
        ("汇报范围", "需求分析、技术设计、系统开发、数据处理与初步质量评测"),
        ("开发记录", "2026年6月30日—2026年7月15日"),
        ("报告日期", "2026年8月"),
        ("汇报人", "____________________"),
    ]
    for label, value in meta_lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(5)
        set_run_font(p.add_run(f"{label}："), size=10.5, color=INK, bold=True)
        set_run_font(p.add_run(value), size=10.5, color=INK)

    doc.add_page_break()


def add_contents(doc: Document) -> None:
    p = doc.add_paragraph(style="Heading 1")
    add_inline(p, "目录")
    entries = [
        "执行摘要",
        "1. 项目背景与目标",
        "2. 总体方案与实际技术架构",
        "3. 阶段一：需求分析与技术设计",
        "4. 阶段二：M0 前后端脚手架与基础体验",
        "5. 阶段三：M1 Care2Caregivers RAG 知识库",
        "6. 阶段四：M2 Education Agent",
        "7. 阶段五：M2 多智能体框架、情绪支持与安全护栏",
        "8. 阶段六：M3 情绪与压力趋势可视化",
        "9. 阶段七：M4 New Jersey 本地资源与视频整合",
        "10. 阶段八：M6 压力趋势反馈到对话",
        "11. 阶段九：专业化界面与交互完善",
        "12. 阶段十：M8 Peer Companion 虚拟同伴",
        "13. 阶段十一：M9 用户账户、历史记录与数据隔离",
        "14. 阶段十二：稳定性修复与工程维护",
        "15. 质量评测：82 个真实照护者问题",
        "16. 项目主要成果汇总",
        "17. 关键设计决策与解决的问题",
        "18. Proposal 要求对照与当前完成度",
        "19. 当前未完成内容与风险",
        "20. 下一阶段建议",
        "21. 结论",
        "附录 A—D：文件对应、Git 里程碑、汇报陈述与证据",
    ]
    for entry in entries:
        ep = doc.add_paragraph()
        ep.paragraph_format.left_indent = Inches(0.15)
        ep.paragraph_format.space_before = Pt(0)
        ep.paragraph_format.space_after = Pt(3)
        ep.paragraph_format.line_spacing = 1.0
        set_run_font(ep.add_run(entry), size=10.5, color=INK)
    add_callout(doc, "阅读说明：正文中的“已完成”均对应现有代码或实施记录；“尚未完成”与“下一步”不会计入当前成果。")
    doc.add_page_break()


def parse_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    i = start
    while i < len(lines) and lines[i].strip().startswith("|"):
        cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
        # Skip markdown separator row.
        if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            rows.append(cells)
        i += 1
    return rows, i


def build_document() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    # The first source block is cover metadata; the builder supplies a polished cover.
    marker = "<!-- PAGEBREAK -->"
    body = text.split(marker, 1)[1].lstrip()
    lines = body.splitlines()

    doc = Document()
    doc.core_properties.title = "I-Care 项目开发完整汇报"
    doc.core_properties.subject = "面向痴呆症家庭照护者的多智能体智能照护系统"
    doc.core_properties.author = "I-Care Project Team"
    doc.core_properties.keywords = "I-Care, dementia caregivers, RAG, multi-agent, wellbeing"

    section = doc.sections[0]
    configure_page(section)
    configure_styles(doc)
    add_header_footer(section)
    bullet_id, number_abstract_id = create_numbering(doc)
    add_cover(doc)
    add_contents(doc)

    i = 0
    para_buf: list[str] = []
    active_number_id: int | None = None

    def flush_paragraph() -> None:
        nonlocal para_buf
        if para_buf:
            add_body_paragraph(doc, " ".join(s.strip() for s in para_buf))
            para_buf = []

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        if not line:
            flush_paragraph()
            # Blank lines terminate a numbered sequence only when the next item
            # is not another numbered line; handled below via look-ahead.
            i += 1
            continue
        if line == marker:
            flush_paragraph()
            active_number_id = None
            doc.add_page_break()
            i += 1
            continue
        if line == "<!-- ARCHITECTURE -->":
            flush_paragraph()
            active_number_id = None
            add_architecture(doc)
            i += 1
            continue
        if line.startswith("|"):
            flush_paragraph()
            active_number_id = None
            rows, i = parse_table(lines, i)
            if rows:
                add_table(doc, rows)
            continue
        if line.startswith("# "):
            flush_paragraph()
            active_number_id = None
            p = doc.add_paragraph(style="Heading 1")
            add_inline(p, line[2:].strip())
            i += 1
            continue
        if line.startswith("## "):
            flush_paragraph()
            active_number_id = None
            p = doc.add_paragraph(style="Heading 2")
            add_inline(p, line[3:].strip())
            i += 1
            continue
        if line.startswith("### "):
            flush_paragraph()
            active_number_id = None
            p = doc.add_paragraph(style="Heading 3")
            add_inline(p, line[4:].strip())
            i += 1
            continue
        if line.startswith("> "):
            flush_paragraph()
            active_number_id = None
            add_callout(doc, line[2:].strip())
            i += 1
            continue
        if re.match(r"^-\s+", line):
            flush_paragraph()
            active_number_id = None
            add_list_item(doc, re.sub(r"^-\s+", "", line), bullet_id, "List Bullet")
            i += 1
            continue
        if re.match(r"^\d+\.\s+", line):
            flush_paragraph()
            if active_number_id is None:
                active_number_id = new_numbering_instance(doc, number_abstract_id)
            add_list_item(doc, re.sub(r"^\d+\.\s+", "", line), active_number_id, "List Number")
            i += 1
            continue
        if line == "---":
            flush_paragraph()
            active_number_id = None
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(8)
            set_paragraph_borders(p, bottom=MID_GRAY)
            i += 1
            continue
        active_number_id = None
        para_buf.append(line.rstrip("  "))
        i += 1
    flush_paragraph()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build_document()
