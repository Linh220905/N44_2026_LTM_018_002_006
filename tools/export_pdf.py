#!/usr/bin/env python3
"""Refresh TOC/lists of figures & tables in LibreOffice, then save final .docx and .pdf.

Run with the system Python that has the LibreOffice UNO bridge:
    /usr/bin/python3 tools/export_pdf.py
LibreOffice writes level-2/3 TOC entries with a direct tab that loses the dot leader in
Word Online / Google Docs; every index paragraph is given an explicit dotted right tab here.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue
from com.sun.star.style.TabAlign import RIGHT

ROOT = Path(__file__).resolve().parents[1]
DOCX = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "docs" / "BAO_CAO_DRONE_LIGHT_SHOW.docx"
PDF = DOCX.with_suffix(".pdf")
PORT = 2093
TEXT_WIDTH_MM100 = 16000  # 16 cm text column


def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def connect(profile: str):
    office = subprocess.Popen([os.environ.get("SOFFICE", "soffice"), "--headless", "--invisible", "--norestore",
                               f"-env:UserInstallation=file://{profile}",
                               f"--accept=socket,host=localhost,port={PORT};urp;"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    for _ in range(60):
        if office.poll() is not None:
            raise RuntimeError("LibreOffice exited during startup; check SOFFICE and installed system libraries")
        try:
            ctx = resolver.resolve(f"uno:socket,host=localhost,port={PORT};urp;StarOffice.ComponentContext")
            return office, ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        except Exception:  # office still starting
            time.sleep(0.5)
    office.kill()
    raise RuntimeError("LibreOffice did not start")


def dotted_tabs(doc) -> int:
    stop = uno.createUnoStruct("com.sun.star.style.TabStop")
    stop.Position, stop.Alignment, stop.FillChar = TEXT_WIDTH_MM100, RIGHT, "."
    fixed = 0
    styles = doc.getStyleFamilies().getByName("ParagraphStyles")
    names = [n for n in styles.getElementNames() if n.startswith(("Contents", "Figure Index", "Table index",
                                                                    "Illustration Index"))]
    for name in names:
        styles.getByName(name).ParaTabStops = (stop,)
    paragraphs = doc.getText().createEnumeration()
    while paragraphs.hasMoreElements():
        para = paragraphs.nextElement()
        if para.supportsService("com.sun.star.text.Paragraph") and para.ParaStyleName in names:
            indent = para.ParaLeftMargin
            local = uno.createUnoStruct("com.sun.star.style.TabStop")
            local.Position, local.Alignment, local.FillChar = TEXT_WIDTH_MM100 - indent, RIGHT, "."
            para.ParaTabStops = (local,)
            fixed += 1
    return fixed


def math_fonts(doc) -> int:
    """Equations become LibreOffice Math objects on import; give them Times New Roman."""
    objects = doc.getEmbeddedObjects()
    done = 0
    for name in objects.getElementNames():
        model = objects.getByName(name).getEmbeddedObject()
        if model is None or not model.supportsService("com.sun.star.formula.FormulaProperties"):
            continue
        for prop_name in ("FontNameVariables", "FontNameFunctions", "FontNameNumbers", "FontNameText",
                          "FontSerif"):
            try:
                model.setPropertyValue(prop_name, "Times New Roman")
            except Exception:  # property absent in this LibreOffice version
                pass
        done += 1
    return done


def main() -> None:
    profile = tempfile.mkdtemp(prefix="lo-profile-")
    work = Path(tempfile.mkdtemp(prefix="lo-work-")) / DOCX.name
    shutil.copy(DOCX, work)  # never open the user's file in place (it may be open in an editor)
    office, desktop = connect(profile)
    try:
        doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(str(work)), "_blank", 0, (prop("Hidden", True),))
        if doc is None:
            sys.exit("cannot open document")
        doc.getTextFields().refresh()
        indexes = doc.getDocumentIndexes()
        for _ in range(2):  # second pass: page numbers settle after the indexes grow
            for i in range(indexes.getCount()):
                indexes.getByIndex(i).update()
            doc.refresh()
        fixed = dotted_tabs(doc)
        formulas = math_fonts(doc)
        doc.refresh()
        doc.storeToURL(uno.systemPathToFileUrl(str(work)), (prop("FilterName", "MS Word 2007 XML"),))
        doc.storeToURL(uno.systemPathToFileUrl(str(PDF)), (prop("FilterName", "writer_pdf_Export"),))
        pages = doc.getCurrentController().getPropertyValue("PageCount")
        count = indexes.getCount()
        doc.close(True)
    finally:
        office.terminate()
        office.wait(timeout=20)
        shutil.rmtree(profile, ignore_errors=True)
    shutil.copy(work, DOCX)
    print(f"indexes={count} dotted_entries={fixed} formulas={formulas} pages={pages}\nsaved {DOCX}\nsaved {PDF}")


if __name__ == "__main__":
    main()
