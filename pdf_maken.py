"""Maakt van cv.md een pdf en controleert die.

Gebruik, vanuit de repo-root van ~/os: uv run cv/pdf_maken.py

De pdf mag maximaal MAX_PAGINAS pagina's hebben, en elk woord uit het cv moet
heel uit de pdf te lezen zijn; anders stopt het script met exitcode 1.
"""

import base64
import html
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from markdown_it import MarkdownIt
from playwright.sync_api import sync_playwright

MAP = Path(__file__).parent
BRON = MAP / "cv.md"
STIJL = MAP / "stijl.css"
DOEL = MAP / "Michael-Akkermans-cv.pdf"
MAX_PAGINAS = 2


def fonts_insluiten(css: str, map_: Path) -> str:
    """Vervangt elke url(fonts/...) door een data-uri, zodat de html op zichzelf staat."""

    def data_uri(treffer: re.Match) -> str:
        data = (map_ / treffer.group(1)).read_bytes()
        return f"url(data:font/woff2;base64,{base64.b64encode(data).decode()})"

    return re.sub(r"url\((fonts/[^)]+)\)", data_uri, css)


def kop_maken(kop_html: str) -> str:
    """Maakt de kop uit de eerste drie blokken: naam, functie en contactregel."""
    treffer = re.match(
        r"<h1>(.*?)</h1>\s*<p>(.*?)</p>\s*<p>(.*?)</p>", kop_html, re.DOTALL
    )
    if treffer is None:
        raise ValueError("cv.md begint niet met naam, functie en contactregel")
    naam, functie, contact = treffer.groups()
    contact = contact.replace(" | ", "\n")
    return (
        f"<header><h1>{naam}</h1>"
        f'<p class="functie">{functie}</p>'
        f'<p class="contact">{contact}</p></header>'
    )


def functie_opmaken(sectie: str) -> str:
    """Zet elke functie in een eigen article, met titel, bedrijf en datum apart."""
    sectie = re.sub(
        r"<h3>(.*?) \| (.*?) \| (.*?)</h3>",
        r'<h3><span class="titel">\1</span> <span class="bedrijf">\2</span> '
        r'<span class="datum">\3</span></h3>',
        sectie,
    )
    begin, *functies = re.split(r"(?=<h3>)", sectie)
    return begin + "".join(f"<article>{functie}</article>" for functie in functies)


def body_maken(markdown: str) -> str:
    """Zet de markdown om naar de body, met per h2 een section."""
    kop, *secties = re.split(r"(?=<h2>)", MarkdownIt().render(markdown))
    delen = [kop_maken(kop)]
    for sectie in secties:
        titel = re.match(r"<h2>(\w+)", sectie).group(1).lower()
        delen.append(f'<section class="{titel}">{functie_opmaken(sectie)}</section>')
    return f'<div class="pagina">{"".join(delen)}</div>'


def html_maken(body: str, css: str) -> str:
    """Bouwt het volledige html-document."""
    return (
        '<!doctype html><html lang="nl"><head><meta charset="utf-8">'
        f"<title>Cv Michael Akkermans</title><style>{css}</style></head>"
        f"<body>{body}</body></html>"
    )


def pdf_schrijven(document: str, doel: Path) -> None:
    """Rendert het html-document met Chromium naar een pdf."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        pagina = browser.new_page()
        pagina.set_content(document, wait_until="load")
        pagina.evaluate("document.fonts.ready")
        pagina.pdf(
            path=str(doel),
            prefer_css_page_size=True,
            print_background=True,
            tagged=True,
        )
        browser.close()


def pdf_lezen(pdf: Path) -> str:
    """Leest de tekst uit de pdf, zoals software van een recruiter dat doet."""
    resultaat = subprocess.run(
        ["pdftotext", str(pdf), "-"], capture_output=True, text=True, check=True
    )
    return resultaat.stdout


def woorden(tekst: str) -> set[str]:
    """Geeft de woorden; koppeltekens scheiden ook, want de pdf breekt daar af."""
    return set(re.split(r"[\s-]+", unicodedata.normalize("NFKC", tekst))) - {""}


def ontbrekende_woorden(body: str, pdf_tekst: str) -> list[str]:
    """Geeft de woorden uit de body die niet heel in de tekst van de pdf staan."""
    zonder_tags = html.unescape(re.sub(r"<[^>]+>", " ", body))
    return sorted(woorden(zonder_tags) - woorden(pdf_tekst))


def paginas_tellen(pdf_tekst: str) -> int:
    """Telt de pagina's: pdftotext sluit elke pagina af met een form feed."""
    return pdf_tekst.count("\f")


def main(bron: Path = BRON, stijl: Path = STIJL, doel: Path = DOEL) -> int:
    """Maakt de pdf en geeft 0 als hij aan de eisen voldoet, anders 1."""
    body = body_maken(bron.read_text(encoding="utf-8"))
    css = fonts_insluiten(stijl.read_text(encoding="utf-8"), stijl.parent)
    pdf_schrijven(html_maken(body, css), doel)

    pdf_tekst = pdf_lezen(doel)
    paginas = paginas_tellen(pdf_tekst)
    ontbrekend = ontbrekende_woorden(body, pdf_tekst)
    if paginas > MAX_PAGINAS:
        print(f"Te lang: {paginas} pagina's, maximaal {MAX_PAGINAS}.", file=sys.stderr)
    if ontbrekend:
        print(f"Niet heel leesbaar: {', '.join(ontbrekend)}", file=sys.stderr)
    if paginas > MAX_PAGINAS or ontbrekend:
        return 1
    print(f"{doel.name}: {paginas} pagina's, alle woorden leesbaar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
