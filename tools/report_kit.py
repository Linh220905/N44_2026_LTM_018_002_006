"""python-docx helpers for a Vietnamese academic report (Times New Roman 13, A4).

Captions use real SEQ fields so Word/LibreOffice can build the lists of figures/tables;
equations are converted from LaTeX to native Word math (OMML) through pandoc.
"""
import copy
import functools
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

FONT, MONO = "Times New Roman", "Courier New"
BODY_PT, TABLE_PT = 13, 12
TEXT_WIDTH_CM = 16.0  # A4 21 cm - left 3 cm - right 2 cm


def _fonts(rpr_parent, name):
    rpr = rpr_parent.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in list(rfonts.attrib):
        del rfonts.attrib[attr]
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rfonts.set(qn(attr), name)


def _field(paragraph, instruction, placeholder=""):
    """Insert a complex field (begin / instr / separate / result / end)."""
    def fld(kind):
        run = paragraph.add_run()
        el = OxmlElement("w:fldChar")
        el.set(qn("w:fldCharType"), kind)
        run._r.append(el)
        return run
    fld("begin")
    run = paragraph.add_run()
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruction} "
    run._r.append(instr)
    fld("separate")
    result = paragraph.add_run(placeholder)
    fld("end")
    return result


class Report:
    def __init__(self, header_left, header_right):
        self.doc = Document()
        self.header_left, self.header_right = header_left, header_right
        self.counts = {"Hình": 0, "Bảng": 0}
        self._styles()
        sec = self.doc.sections[0]
        sec.page_width, sec.page_height = Cm(21), Cm(29.7)
        sec.left_margin, sec.right_margin = Cm(3), Cm(2)
        sec.top_margin, sec.bottom_margin = Cm(2), Cm(2)
        sec.header_distance = sec.footer_distance = Cm(1.0)

    # ---------- styles ----------
    def _styles(self):
        st = self.doc.styles
        normal = st["Normal"]
        normal.font.name, normal.font.size = FONT, Pt(BODY_PT)
        _fonts(normal.element, FONT)
        pf = normal.paragraph_format
        pf.line_spacing_rule, pf.line_spacing = WD_LINE_SPACING.MULTIPLE, 1.5
        pf.space_before, pf.space_after = Pt(0), Pt(6)
        pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        for level, (size, bold, italic, before, after) in {1: (14, True, False, 12, 6), 2: (13, True, False, 10, 4),
                                                            3: (13, True, True, 8, 4)}.items():
            s = st[f"Heading {level}"]
            s.font.name, s.font.size, s.font.bold, s.font.italic = FONT, Pt(size), bold, italic
            s.font.color.rgb = None
            _fonts(s.element, FONT)
            rpr = s.element.get_or_add_rPr()
            color = rpr.find(qn("w:color"))
            if color is not None:
                rpr.remove(color)
            s.paragraph_format.space_before, s.paragraph_format.space_after = Pt(before), Pt(after)
            s.paragraph_format.line_spacing = 1.3
            s.paragraph_format.keep_with_next = True
            s.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
        cap = st["Caption"]
        cap.font.name, cap.font.size, cap.font.bold, cap.font.italic = FONT, Pt(12), True, False
        cap.font.color.rgb = None
        _fonts(cap.element, FONT)
        cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_before, cap.paragraph_format.space_after = Pt(4), Pt(10)
        cap.paragraph_format.line_spacing = 1.15
        for name in ("TOC Heading", "Title"):
            if name in [s.name for s in st]:
                _fonts(st[name].element, FONT)

    # ---------- header / footer ----------
    def body_section(self):
        """New section with header (left/right text, bottom rule) and centred page number from 1."""
        sec = self.doc.add_section(WD_SECTION.NEW_PAGE)
        sec.header.is_linked_to_previous = False
        sec.footer.is_linked_to_previous = False
        sec.different_first_page_header_footer = False
        pg = OxmlElement("w:pgNumType")
        pg.set(qn("w:start"), "1")
        sec._sectPr.append(pg)
        hp = sec.header.paragraphs[0]
        hp.text = ""
        hp.style = self.doc.styles["Normal"]  # Header style carries centre/right tabs that break the layout
        hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        hp.paragraph_format.line_spacing = 1.0
        hp.paragraph_format.space_after = Pt(0)
        hp.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT)
        run = hp.add_run(f"{self.header_left}\t{self.header_right}")
        run.font.size, run.font.italic = Pt(11), True
        self._border(hp, "bottom")
        fp = sec.footer.paragraphs[0]
        fp.style = self.doc.styles["Normal"]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _field(fp, "PAGE", "1").font.size = Pt(12)
        return sec

    @staticmethod
    def _border(paragraph, side):
        ppr = paragraph._p.get_or_add_pPr()
        bdr = OxmlElement("w:pBdr")
        el = OxmlElement(f"w:{side}")
        for k, v in (("val", "single"), ("sz", "6"), ("space", "1"), ("color", "000000")):
            el.set(qn(f"w:{k}"), v)
        bdr.append(el)
        ppr.append(bdr)

    # ---------- text ----------
    def para(self, text="", *, align=None, indent=True, size=None, bold=False, italic=False, after=None,
             before=None, spacing=None, keep_next=False):
        p = self.doc.add_paragraph()
        if indent and align in (None, WD_ALIGN_PARAGRAPH.JUSTIFY):
            p.paragraph_format.first_line_indent = Cm(1)
        if align is not None:
            p.alignment = align
        if after is not None:
            p.paragraph_format.space_after = Pt(after)
        if before is not None:
            p.paragraph_format.space_before = Pt(before)
        if spacing is not None:
            p.paragraph_format.line_spacing = spacing
        p.paragraph_format.keep_with_next = keep_next
        self.rich(p, text, size=size, bold=bold, italic=italic)
        return p

    @staticmethod
    def rich(p, text, size=None, bold=False, italic=False):
        """**bold**, *italic*, `mono` inline markup."""
        for part in re.split(r"(\*\*.+?\*\*|`.+?`|(?<!\*)\*(?!\*).+?(?<!\*)\*(?!\*)|[_^]\{[^}]*\})", text):
            if not part:
                continue
            run_bold, run_italic, mono, script = bold, italic, False, None
            if part.startswith("**") and re.search(r"[_^]\{", part):
                Report.rich(p, part[2:-2], size=size, bold=True, italic=italic)
                continue
            if part.startswith("**"):
                part, run_bold = part[2:-2], True
            elif part.startswith("`"):
                part, mono = part[1:-1], True
            elif part.startswith(("_{", "^{")):
                part, script = part[2:-1], part[0]
            elif part.startswith("*"):
                part, run_italic = part[1:-1], True
            run = p.add_run(part)
            run.bold, run.italic = run_bold or None, run_italic or None
            if script == "_":
                run.font.subscript = True
            elif script == "^":
                run.font.superscript = True
            if mono:
                run.font.name = MONO
                _fonts(run._r, MONO)
                run.font.size = Pt((size or BODY_PT) - 1.5)
            elif size:
                run.font.size = Pt(size)

    def bullets(self, items, numbered=False):
        for i, item in enumerate(items, 1):
            p = self.doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1.0)
            p.paragraph_format.first_line_indent = Cm(-0.6)
            p.paragraph_format.space_after = Pt(3)
            p.add_run(f"{i}." if numbered else "–").bold = numbered or None
            p.add_run(" " * 2)
            self.rich(p, item)

    def heading(self, text, level):
        return self.doc.add_heading(text, level)

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    # ---------- captions, figures, tables ----------
    def caption(self, label, text):
        self.counts[label] += 1
        p = self.doc.add_paragraph(style="Caption")
        p.add_run(f"{label} ")
        _field(p, f"SEQ {label} \\* ARABIC", str(self.counts[label]))
        p.add_run(f". {text}")
        if label == "Bảng":
            p.paragraph_format.keep_with_next = True
        return self.counts[label]

    def figure(self, path, text, width_cm=15.5):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.line_spacing = 1.0
        p.add_run().add_picture(str(path), width=Cm(width_cm))
        return self.caption("Hình", text)

    def table(self, rows, caption=None, widths=None, header=True, size=TABLE_PT, align=None, mono_cols=()):
        if caption:
            n = self.caption("Bảng", caption)
        tbl = self.doc.add_table(rows=len(rows), cols=len(rows[0]))
        tbl.style = "Table Grid"
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        widths = widths or [TEXT_WIDTH_CM / len(rows[0])] * len(rows[0])
        for r, row in enumerate(rows):
            tr = tbl.rows[r]
            trpr = tr._tr.get_or_add_trPr()
            cant = OxmlElement("w:cantSplit")
            trpr.append(cant)
            if r == 0 and header:
                trpr.append(OxmlElement("w:tblHeader"))
            for c, value in enumerate(row):
                cell = tr.cells[c]
                cell.width = Cm(widths[c])
                p = cell.paragraphs[0]
                p.paragraph_format.first_line_indent = Cm(0)
                p.paragraph_format.line_spacing = 1.15
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.space_before = Pt(1)
                p.paragraph_format.alignment = (WD_ALIGN_PARAGRAPH.CENTER if (r == 0 and header) else
                                                (align[c] if align else WD_ALIGN_PARAGRAPH.LEFT))
                for k, line in enumerate(str(value).split("\n")):
                    if k:
                        p = cell.add_paragraph()
                        p.paragraph_format.line_spacing = 1.15
                        p.paragraph_format.space_after = Pt(1)
                        p.paragraph_format.alignment = align[c] if align else WD_ALIGN_PARAGRAPH.LEFT
                    text = f"`{line}`" if c in mono_cols and r > 0 and line else line
                    self.rich(p, text, size=size, bold=(r == 0 and header))
        self._fix_grid(tbl, widths)
        spacer = self.doc.add_paragraph()
        spacer.paragraph_format.space_after = Pt(2)
        spacer.paragraph_format.line_spacing = 1.0
        return tbl

    @staticmethod
    def _shade(cell):
        tcpr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        for k, v in (("val", "clear"), ("color", "auto"), ("fill", "E7E6E6")):
            shd.set(qn(f"w:{k}"), v)
        tcpr.append(shd)

    @staticmethod
    def _fix_grid(tbl, widths):
        grid = tbl._tbl.tblGrid
        for gc, w in zip(grid.findall(qn("w:gridCol")), widths):
            gc.set(qn("w:w"), str(int(w * 567)))
        tblpr = tbl._tbl.tblPr
        lay = OxmlElement("w:tblLayout")
        lay.set(qn("w:type"), "fixed")
        tblpr.append(lay)

    def algorithm(self, title, lines):
        """Pseudocode box (no source code in the report, per grading rules)."""
        tbl = self.doc.add_table(rows=1, cols=1)  # one unsplittable cell keeps title and body together
        tbl.style = "Table Grid"
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        head = tbl.rows[0].cells[0].paragraphs[0]
        head.paragraph_format.first_line_indent = Cm(0)
        head.paragraph_format.line_spacing = 1.15
        head.paragraph_format.space_after = Pt(2)
        head.paragraph_format.keep_with_next = True
        self.rich(head, title, size=12, bold=True)
        self._border(head, "bottom")
        cell = tbl.rows[0].cells[0]
        for i, line in enumerate(lines):
            p = cell.add_paragraph()
            p.paragraph_format.first_line_indent = Cm(0)
            p.paragraph_format.line_spacing = 1.0
            p.paragraph_format.space_after = Pt(0)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.keep_with_next = i < len(lines) - 1
            run = p.add_run(line)
            run.font.name, run.font.size = MONO, Pt(9.5)
            _fonts(run._r, MONO)
        for row in tbl.rows:
            row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        self._fix_grid(tbl, [TEXT_WIDTH_CM])
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)

    # ---------- equations ----------
    def equation(self, latex, number=None):
        p = self.doc.add_paragraph()
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM / 2), WD_TAB_ALIGNMENT.CENTER)
        p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT)
        p.add_run("\t")
        p._p.append(copy.deepcopy(_omml(latex)))
        if number:
            p.add_run(f"\t({number})")
        return p

    # ---------- front matter ----------
    def toc(self, title, instruction):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(12)
        r = p.add_run(title)
        r.bold, r.font.size = True, Pt(14)
        q = self.doc.add_paragraph()
        q.paragraph_format.first_line_indent = Cm(0)
        _field(q, instruction, "(Nhấn F9 hoặc chuột phải › Update Field để cập nhật)")

    def cover_frame(self):
        """Request a double-line border on the cover page only; applied in save()."""
        self._cover_border = True

    def end_cover(self):
        """Close the cover in its own section so the border cannot spread to later pages."""
        self.doc.add_section(WD_SECTION.NEW_PAGE)

    def _apply_cover_border(self):
        for section in self.doc.sections:
            for old in section._sectPr.findall(qn("w:pgBorders")):
                section._sectPr.remove(old)
        if not getattr(self, "_cover_border", False):
            return
        sectpr = self.doc.sections[0]._sectPr
        borders = OxmlElement("w:pgBorders")
        borders.set(qn("w:offsetFrom"), "text")
        for side in ("top", "left", "bottom", "right"):
            el = OxmlElement(f"w:{side}")
            for key, val in (("val", "thinThickSmallGap"), ("sz", "24"), ("space", "6"), ("color", "000000")):
                el.set(qn(f"w:{key}"), val)
            borders.append(el)
        # schema order: pgBorders must precede lnNumType/pgNumType/cols/... in sectPr
        anchor = None
        for tag in ("w:lnNumType", "w:pgNumType", "w:cols", "w:formProt", "w:vAlign", "w:noEndnote",
                    "w:titlePg", "w:textDirection", "w:bidi", "w:rtlGutter", "w:docGrid"):
            anchor = sectpr.find(qn(tag))
            if anchor is not None:
                break
        if anchor is not None:
            anchor.addprevious(borders)
        else:
            sectpr.append(borders)

    def logos(self, paths, height_cm=3.2):
        p = self.doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(18)
        for i, path in enumerate(paths):
            if i:
                p.add_run("\u00a0" * 6)
            p.add_run().add_picture(str(path), height=Cm(height_cm))

    def _force_fonts(self):
        """Every style and the document defaults use Times New Roman (code styles keep Courier New)."""
        defaults = self.doc.styles.element.find(qn("w:docDefaults"))
        if defaults is not None:
            rpr = defaults.find(qn("w:rPrDefault") + "/" + qn("w:rPr"))
            if rpr is not None:
                rfonts = rpr.find(qn("w:rFonts"))
                if rfonts is None:
                    rfonts = OxmlElement("w:rFonts")
                    rpr.insert(0, rfonts)
                for attr in list(rfonts.attrib):
                    del rfonts.attrib[attr]
                for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
                    rfonts.set(qn(attr), FONT)
        for style in self.doc.styles:
            if style.type in (1, 2) and style.name not in ("Macro Text", "HTML Code", "HTML Preformatted"):
                _fonts(style.element, FONT)

    def save(self, path):
        self._apply_cover_border()
        self._force_fonts()
        settings = self.doc.settings.element
        upd = OxmlElement("w:updateFields")
        upd.set(qn("w:val"), "true")
        settings.append(upd)
        self.doc.save(str(path))


@functools.lru_cache(maxsize=None)
def _omml(latex):
    with tempfile.TemporaryDirectory() as tmp:
        md, out = Path(tmp, "e.md"), Path(tmp, "e.docx")
        md.write_text(f"$${latex}$$\n", encoding="utf-8")
        subprocess.run(["pandoc", str(md), "-o", str(out)], check=True)
        xml = zipfile.ZipFile(out).read("word/document.xml").decode()
    match = re.search(r"<m:oMath>.*</m:oMath>", xml, re.S)
    if not match:
        raise ValueError(f"pandoc could not convert: {latex}")
    ns = ('xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
          'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"')
    element = parse_xml(match.group(0).replace("<m:oMath>", f"<m:oMath {ns}>", 1))
    for rpr in list(element.iter(qn("w:rPr"))):
        rpr.getparent().remove(rpr)
    # every math run carries an explicit Times New Roman so viewers do not fall back to other fonts
    for mr in element.iter(qn("m:r")):
        rpr = OxmlElement("w:rPr")
        rfonts = OxmlElement("w:rFonts")
        for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rfonts.set(qn(attr), FONT)
        rpr.append(rfonts)
        mrpr = mr.find(qn("m:rPr"))
        (mrpr.addnext if mrpr is not None else lambda e: mr.insert(0, e))(rpr)
    return element
