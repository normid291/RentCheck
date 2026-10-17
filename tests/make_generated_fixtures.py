"""
Build the fixtures used by tests/test_document_type.py.

Two groups are produced here (real downloads are fetched by
``tests/fetch_real_fixtures.py`` -- see fixtures/manifest.json for sources):

* ``fixtures/real/``       : documents derived from the *real* downloads
                             (an image scan of a real deed, an OCR-only
                             scanned PDF built from a real lease, and a
                             .docx carrying real lease text).
* ``fixtures/generated/``  : documents generated with Pillow / python-docx to
                             cover categories that are hard to obtain as public
                             samples (invoice, bank statement, CV, random
                             photos).

Run from the repo root:

    python tests/make_generated_fixtures.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

try:
    from docx import Document
except Exception:  # pragma: no cover
    Document = None

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = os.path.join(HERE, "fixtures", "real")
GEN = os.path.join(HERE, "fixtures", "generated")
os.makedirs(REAL, exist_ok=True)
os.makedirs(GEN, exist_ok=True)


def _font(size: int) -> "ImageFont.FreeTypeFont":
    for name in ("arial.ttf", "calibri.ttf", "DejaVuSans.ttf"):
        for base in (r"C:\Windows\Fonts", "/usr/share/fonts/truetype/dejavu"):
            p = os.path.join(base, name)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _lines_image(path: str, title: str, lines: list[str], size=(1000, 1300), bg="white") -> None:
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    d.text((60, 60), title, fill="black", font=_font(40))
    y = 150
    for ln in lines:
        d.text((60, y), ln, fill=(20, 20, 20), font=_font(26))
        y += 42
    img.save(path)
    print("wrote", os.path.relpath(path))


def render_pdf_pages(pdf_path: str, pages: int, scale: float = 2.0) -> list[Image.Image]:
    pdf = pdfium.PdfDocument(pdf_path)
    out = []
    for i in range(min(pages, len(pdf))):
        out.append(pdf[i].render(scale=scale).to_pil().convert("RGB"))
    return out


def build_real_derived() -> None:
    # 1. Image "photo" of a real Nigerian Deed of Lease (real text, image input).
    deed = os.path.join(REAL, "ng_deed_of_lease.pdf")
    if os.path.exists(deed):
        pages = render_pdf_pages(deed, 1)
        if pages:
            pages[0].save(os.path.join(REAL, "ng_deed_scan.png"))
            print("wrote tests/fixtures/real/ng_deed_scan.png")

    # 2. OCR-only scanned PDF built from a real US residential lease
    #    (rendered to images -> a PDF with no text layer).
    lease = os.path.join(REAL, "us_simple_lease_esign.pdf")
    if os.path.exists(lease):
        imgs = render_pdf_pages(lease, 2, scale=1.6)
        if imgs:
            imgs[0].save(
                os.path.join(REAL, "us_simple_lease_scanned.pdf"),
                save_all=True,
                append_images=imgs[1:],
                resolution=150.0,
            )
            print("wrote tests/fixtures/real/us_simple_lease_scanned.pdf")

    # 3. A .docx carrying the real Deed of Lease text.
    if Document is not None and os.path.exists(deed):
        from app.services.extractor import extract_text

        text = extract_text(open(deed, "rb").read(), "application/pdf", "ng_deed_of_lease.pdf")
        # Also keep the plain text, used to exercise the "paste text" path.
        with open(os.path.join(REAL, "ng_deed_text.txt"), "w", encoding="utf-8") as fh:
            fh.write(text)
        print("wrote tests/fixtures/real/ng_deed_text.txt")
        doc = Document()
        for para in text.split("\n"):
            if para.strip():
                doc.add_paragraph(para.strip())
        doc.save(os.path.join(REAL, "ng_deed_real.docx"))
        print("wrote tests/fixtures/real/ng_deed_real.docx")


def build_generated() -> None:
    # Invoice (image) -> NOT tenancy
    _lines_image(
        os.path.join(GEN, "invoice.png"),
        "INVOICE",
        [
            "Invoice No: INV-2043        Date: 2024-03-11",
            "From: Bright Supplies Ltd, 12 Marina Road, Lagos",
            "Bill To: Adewale Trading Co.",
            "",
            "Description                 Qty     Unit Price     Amount",
            "A4 paper (reams)             10        3.50          35.00",
            "Printer ink cartridges        2       22.00          44.00",
            "Delivery / logistics          1       12.00          12.00",
            "",
            "Subtotal: 91.00",
            "VAT (7.5%): 6.83",
            "TOTAL DUE: NGN 97.83",
            "",
            "Payment due within 14 days. Thank you for your business.",
        ],
    )

    # Bank statement (image) -> NOT tenancy
    _lines_image(
        os.path.join(GEN, "bank_statement.png"),
        "ACCOUNT STATEMENT",
        [
            "Bank: Zenith Bank Plc",
            "Account Name: Chidi Okeke      Account No: 0123456789",
            "Statement Period: 01 Feb 2024 - 29 Feb 2024",
            "",
            "Date        Description                   Debit      Credit",
            "02-Feb      Salary credit                            250,000.00",
            "05-Feb      POS purchase - supermarket     18,500.00",
            "11-Feb      Transfer to savings            50,000.00",
            "17-Feb      Utility bill - electricity      9,200.00",
            "26-Feb      Rent payment                  120,000.00",
            "",
            "Opening balance: 40,120.55",
            "Closing balance: 91,420.55",
            "",
            "This is a computer generated statement and does not require a signature.",
        ],
    )

    # CV (image) -> NOT tenancy
    _lines_image(
        os.path.join(GEN, "cv.png"),
        "CURRICULUM VITAE",
        [
            "Name: Grace Adeyemi",
            "Email: grace.adeyemi@example.com   Phone: +234 800 000 0000",
            "",
            "PROFILE",
            "Results driven software engineer with 6 years of experience",
            "building web applications and APIs.",
            "",
            "EXPERIENCE",
            "Senior Engineer, Fintech Ltd (2021 - present)",
            "  - Led migration of payments platform to microservices",
            "  - Mentored four junior engineers",
            "Engineer, Startup Co (2018 - 2021)",
            "",
            "EDUCATION",
            "BSc Computer Science, University of Lagos (2017)",
            "",
            "SKILLS: Python, SQL, React, Docker, AWS",
            "REFERENCES available on request",
        ],
    )

    # Random photos -> NOT tenancy (no text at all)
    _photo_landscape(os.path.join(GEN, "landscape.png"))
    _photo_food(os.path.join(GEN, "food.png"))
    _photo_person(os.path.join(GEN, "person.png"))

    # Other-language documents (generated from plain text). A tenancy agreement
    # in Spanish/German must pass; a non-tenancy one in French must not.
    _write_text(
        os.path.join(GEN, "es_arrendamiento.txt"),
        """CONTRATO DE ARRENDAMIENTO DE VIVIENDA

Entre el arrendador, D. Juan Perez, y el arrendatario, D. Carlos Gomez, se celebra el
presente contrato de arrendamiento de la vivienda situada en la calle Mayor 12.
La duracion del arrendamiento sera de un ano, prorrogable. La renta mensual sera de
900 euros, pagadera los primeros cinco dias de cada mes. El arrendatario entrega una
fianza de dos mensualidades. El arrendador se compromete a realizar las reparaciones
necesarias para el mantenimiento de la vivienda. El arrendatario no podra subarrendar
la vivienda sin el consentimiento por escrito del arrendador. Cualquier obra de mejora
requerira autorizacion. Las partes firman el contrato por duplicado.
""",
    )
    _write_text(
        os.path.join(GEN, "de_mietvertrag.txt"),
        """MIETVERTRAG

Zwischen dem Vermieter, Herrn Klaus Mueller, und dem Mieter, Herrn Peter Schmidt,
wird der folgende Mietvertrag ueber die Wohnung in der Hauptstrasse 5 geschlossen.
Die Mietzeit betraegt zwei Jahre. Die monatliche Miete betraegt 1.200 Euro und ist bis
zum dritten Werktag eines jeden Monats im Voraus zu zahlen. Der Mieter leistet eine
Kaution in Hoehe von drei Monatsmieten. Der Mieter darf die Wohnung nicht ohne
schriftliche Zustimmung des Vermieters untervermieten. Der Vermieter ist fuer
Instandhaltung und Reparaturen verantwortlich. Beide Parteien unterschreiben diesen
Mietvertrag.
""",
    )
    _write_text(
        os.path.join(GEN, "fr_contrat_travail.txt"),
        """CONTRAT DE TRAVAIL A DUREE INDETERMINEE

Entre la societe ABC SARL, sise a Paris, representee par son dirigeant, et Monsieur
Jean Dupont, demeurant a Lyon, il est conclu un contrat de travail a duree indeterminee.
Le salarie exercera les fonctions d'ingenieur logiciel. La remuneration mensuelle brute
est fixee a 4.000 euros. La periode d'essai est de trois mois. Le salarie beneficiera
des conges payes prevus par la loi. Le present contrat est soumis a la convention
collective applicable a l'entreprise.
""",
    )


def _write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print("wrote", os.path.relpath(path))


def _photo_landscape(path: str) -> None:
    img = Image.new("RGB", (1200, 800), (135, 206, 235))
    d = ImageDraw.Draw(img)
    for y in range(800):  # sky gradient
        d.line([(0, y), (1200, y)], fill=(120 + y // 12, 170 + y // 20, 235))
    d.ellipse((900, 80, 1040, 220), fill=(255, 230, 120))  # sun
    d.polygon([(0, 620), (300, 380), (620, 620)], fill=(80, 120, 70))  # hills
    d.polygon([(500, 620), (850, 340), (1200, 620)], fill=(60, 100, 55))
    d.rectangle((0, 620, 1200, 800), fill=(70, 140, 70))  # foreground
    img.save(path)
    print("wrote tests/fixtures/generated/landscape.png")


def _photo_food(path: str) -> None:
    img = Image.new("RGB", (1000, 1000), (240, 230, 210))
    d = ImageDraw.Draw(img)
    d.ellipse((120, 120, 880, 880), fill=(250, 250, 250), outline=(200, 200, 200), width=6)
    for i, c in enumerate([(200, 60, 50), (240, 200, 60), (90, 160, 70), (230, 150, 60)]):
        (x, y) = [(360, 360), (560, 400), (460, 560), (620, 600)][i]
        d.ellipse((x, y, x + 150, y + 150), fill=c)
    img.save(path)
    print("wrote tests/fixtures/generated/food.png")


def _photo_person(path: str) -> None:
    img = Image.new("RGB", (800, 1000), (225, 225, 235))
    d = ImageDraw.Draw(img)
    d.ellipse((280, 120, 520, 360), fill=(90, 80, 70))  # head
    d.polygon([(200, 1000), (400, 380), (600, 1000)], fill=(40, 60, 120))  # body
    img.save(path)
    print("wrote tests/fixtures/generated/person.png")


if __name__ == "__main__":
    build_real_derived()
    build_generated()
    print("done")
