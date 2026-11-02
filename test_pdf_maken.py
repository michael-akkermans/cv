"""Tests voor pdf_maken.py; de pdf wordt echt gerenderd met Chromium."""

import base64
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import pdf_maken

MARKDOWN = """# Jan Jansen

Engineer

Breda | jan@example.nl

## Profiel

Ik bouw dingen.

## Werkervaring

### Engineer | Bedrijf, Breda | 2020 – heden

Inleiding.

- Iets gebouwd

### Beheerder | Ander Bedrijf, Almere | 2010 – 2020

- Iets beheerd

## Eigen projecten

- Hobby
"""

CSS = "@page { size: A4; margin: 20mm; } body { font: 12pt serif; }"


def test_fonts_insluiten_vervangt_url_door_data_uri(tmp_path):
    (tmp_path / "fonts").mkdir()
    (tmp_path / "fonts" / "a.woff2").write_bytes(b"inhoud")
    css = "src: url(fonts/a.woff2) format('woff2'); background: url(plaatje.png);"
    verwacht = base64.b64encode(b"inhoud").decode()
    assert pdf_maken.fonts_insluiten(css, tmp_path) == (
        f"src: url(data:font/woff2;base64,{verwacht}) format('woff2'); "
        "background: url(plaatje.png);"
    )


def test_kop_maken_splitst_contact_over_regels():
    kop = "<h1>Jan</h1>\n<p>Engineer</p>\n<p>Breda | jan@example.nl | site.nl</p>\n"
    assert pdf_maken.kop_maken(kop) == (
        "<header><h1>Jan</h1>"
        '<p class="functie">Engineer</p>'
        '<p class="contact">Breda\njan@example.nl\nsite.nl</p></header>'
    )


def test_kop_maken_weigert_onvolledige_kop():
    with pytest.raises(ValueError, match="naam, functie en contactregel"):
        pdf_maken.kop_maken("<h1>Jan</h1>\n<p>Engineer</p>\n")


def test_functie_opmaken_maakt_per_functie_een_article():
    sectie = (
        "<h2>Werk</h2>\n"
        "<h3>Rol | Bedrijf | 2020</h3>\n<p>Tekst</p>\n"
        "<h3>Oud | Ander | 2010</h3>\n"
    )
    assert pdf_maken.functie_opmaken(sectie) == (
        "<h2>Werk</h2>\n"
        '<article><h3><span class="titel">Rol</span> '
        '<span class="bedrijf">Bedrijf</span> '
        '<span class="datum">2020</span></h3>\n<p>Tekst</p>\n</article>'
        '<article><h3><span class="titel">Oud</span> '
        '<span class="bedrijf">Ander</span> '
        '<span class="datum">2010</span></h3>\n</article>'
    )


def test_functie_opmaken_laat_sectie_zonder_functies_staan():
    sectie = "<h2>Talen</h2>\n<ul>\n<li>Nederlands</li>\n</ul>\n"
    assert pdf_maken.functie_opmaken(sectie) == sectie


def test_body_maken_geeft_elke_sectie_een_klasse_uit_het_eerste_woord():
    body = pdf_maken.body_maken(MARKDOWN)
    assert body.startswith('<div class="pagina"><header><h1>Jan Jansen</h1>')
    assert body.endswith("</section></div>")
    assert '<section class="profiel"><h2>Profiel</h2>' in body
    assert '<section class="werkervaring"><h2>Werkervaring</h2>' in body
    assert '<section class="eigen"><h2>Eigen projecten</h2>' in body
    assert body.count("<article>") == 2


def test_html_maken_zet_taal_titel_stijl_en_body():
    document = pdf_maken.html_maken("<p>Body</p>", "p { color: red }")
    assert document == (
        '<!doctype html><html lang="nl"><head><meta charset="utf-8">'
        "<title>Cv Michael Akkermans</title><style>p { color: red }</style></head>"
        "<body><p>Body</p></body></html>"
    )


def test_pdf_schrijven_en_lezen_geeft_de_tekst_terug(tmp_path):
    doel = tmp_path / "uit.pdf"
    pdf_maken.pdf_schrijven(pdf_maken.html_maken("<p>Hallo Wereld</p>", CSS), doel)
    assert doel.read_bytes().startswith(b"%PDF")
    assert "Hallo Wereld" in pdf_maken.pdf_lezen(doel)


def test_pdf_schrijven_volgt_de_paginamaat_en_achtergrond_uit_de_css(tmp_path):
    doel = tmp_path / "uit.pdf"
    css = "@page { size: A5; margin: 0; } body { background: #000; margin: 0; }"
    document = pdf_maken.html_maken('<div style="height:100mm">x</div>', css)
    pdf_maken.pdf_schrijven(document, doel)
    inhoud = doel.read_bytes()
    assert b"/MediaBox [0 0 420 " in inhoud
    assert b"/StructTreeRoot" in inhoud
    pixels = subprocess.run(
        ["pdftoppm", "-r", "10", str(doel)], capture_output=True, check=True
    ).stdout
    assert pixels.startswith(b"P6\n59 83\n255\n\x00\x00\x00")


def test_pdf_lezen_faalt_bij_een_kapot_bestand(tmp_path):
    kapot = tmp_path / "kapot.pdf"
    kapot.write_bytes(b"geen pdf")
    with pytest.raises(Exception, match="pdftotext"):
        pdf_maken.pdf_lezen(kapot)


def test_woorden_splitst_op_witruimte_en_koppelteken():
    assert pdf_maken.woorden(" AI-\nagents  en\n(2013-2015) ") == {
        "AI",
        "agents",
        "en",
        "(2013",
        "2015)",
    }


def test_woorden_normaliseert_ligaturen():
    assert pdf_maken.woorden("ﬁles") == {"files"}


def test_ontbrekende_woorden_vindt_gebroken_woord():
    body = "<h2>Werkervaring</h2><p>Jira &amp; Confluence</p>"
    assert pdf_maken.ontbrekende_woorden(body, "WERKERVARI NG Jira & Confluence") == [
        "Werkervaring"
    ]


def test_ontbrekende_woorden_sorteert():
    assert pdf_maken.ontbrekende_woorden("<p>zebra aap</p>", "") == ["aap", "zebra"]


def test_ontbrekende_woorden_leeg_als_alles_er_staat():
    assert pdf_maken.ontbrekende_woorden("<p>Jira</p>", "Jira") == []


def test_maximum_is_twee_pagina_s():
    assert pdf_maken.MAX_PAGINAS == 2


def test_paginas_tellen():
    assert pdf_maken.paginas_tellen("een\ftwee\f") == 2


def schrijf_bron(map_: Path, markdown: str) -> tuple[Path, Path, Path]:
    bron = map_ / "cv.md"
    bron.write_text(markdown, encoding="utf-8")
    stijl = map_ / "stijl.css"
    stijl.write_text(CSS, encoding="utf-8")
    return bron, stijl, map_ / "uit.pdf"


def test_main_slaagt_en_meldt_de_pagina_s(tmp_path, capsys):
    assert pdf_maken.main(*schrijf_bron(tmp_path, MARKDOWN)) == 0
    assert capsys.readouterr().out == "uit.pdf: 1 pagina's, alle woorden leesbaar.\n"


def test_main_slaagt_op_precies_het_maximum(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_maken, "MAX_PAGINAS", 1)
    assert pdf_maken.main(*schrijf_bron(tmp_path, MARKDOWN)) == 0


def test_main_weigert_een_te_lang_cv(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(pdf_maken, "MAX_PAGINAS", 0)
    assert pdf_maken.main(*schrijf_bron(tmp_path, MARKDOWN)) == 1
    uitvoer = capsys.readouterr()
    assert "Te lang: 1 pagina's, maximaal 0." in uitvoer.err
    assert uitvoer.out == ""


def test_main_weigert_niet_leesbare_woorden(tmp_path, monkeypatch, capsys):
    bron, stijl, doel = schrijf_bron(tmp_path, MARKDOWN)
    stijl.write_text(CSS + "h2 { letter-spacing: 3em; }", encoding="utf-8")
    assert pdf_maken.main(bron, stijl, doel) == 1
    uitvoer = capsys.readouterr()
    assert "Niet heel leesbaar: " in uitvoer.err
    assert "Werkervaring" in uitvoer.err
    assert uitvoer.out == ""


def test_echt_cv_past_op_twee_pagina_s(tmp_path, capsys):
    doel = tmp_path / "cv.pdf"
    assert pdf_maken.main(doel=doel) == 0
    assert "alle woorden leesbaar" in capsys.readouterr().out
