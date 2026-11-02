# cv

Cv in markdown, met een script dat er een pdf van maakt.

- **Bron:** `cv.md`. De kop van een functie is
  `### Titel | Bedrijf, plaats | periode`.
- **Opmaak:** `stijl.css`, met de lettertypen in `fonts/` (SIL Open Font License).
- **Pdf:** `Michael-Akkermans-cv.pdf`.

## Pdf maken

Vanuit de repo-root van `~/os`, omdat het script de Python-omgeving daar gebruikt:

```bash
uv run cv/pdf_maken.py
```

Het script stopt met een fout als de pdf langer is dan twee pagina's, of als een
woord niet heel uit de pdf te lezen is.

## Tests

```bash
uv run pytest cv -o testpaths=cv --cov=cv --cov-branch --cov-fail-under=100
```
