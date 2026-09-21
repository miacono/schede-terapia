#!/usr/bin/env python3
# Schede terapia - gestione e stampa delle schede terapia di Villa Silenzi
# Copyright (C) 2026 Matteo Iacono
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Genera il PDF delle schede terapia (fronte/retro per paziente, un foglio per giorno).

Uso:
    genera_schede.py NOMI DATA_INIZIO [DATA_FINE] [-o FILE.pdf] [--json utenti.json]

    NOMI          cognomi/nomi separati da virgola (case insensitive) oppure TUTTI
    DATA_INIZIO   gg/mm/aaaa
    DATA_FINE     gg/mm/aaaa (facoltativa, default = DATA_INIZIO)

Esempio:
    genera_schede.py TUTTI 22/09/2026 24/09/2026
    genera_schede.py "rossi, verdi" 22/09/2026

Richiede: reportlab (pip install reportlab)
"""
import argparse
import json
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

BASE = Path(__file__).resolve().parent
LOGO = BASE / "assets" / "logo.jpeg"
TITOLO = "SERVIZIO RESIDENZIALE VILLA SILENZI"

W, H = A4
X0, X1 = 80, 540  # bordi sinistro/destro delle tabelle
THICK, THIN = 1.6, 0.6

# Fasce sempre stampate (anche vuote, da compilare a mano) con righe minime e ordine.
STANDARD = {
    "MATTINO": (8 * 60, 6),
    "PRANZO": (13 * 60, 4),
    "CENA": (19 * 60, 6),
    "NOTTE": (22 * 60, 6),
}
RIGHE_EXTRA = 4  # righe minime per fasce non standard (es. 16:00)


# ---------------------------------------------------------------- dati
def norm(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").casefold().strip()


def seleziona(utenti, nomi):
    if norm(nomi) == "tutti":
        return utenti
    scelti = []
    for token in (t for t in nomi.split(",") if t.strip()):
        t = norm(token)
        trovati = [u for u in utenti if t in norm(u["paziente"])]
        if not trovati:
            sys.exit(f"Errore: nessun paziente corrisponde a '{token.strip()}'.")
        if len(trovati) > 1:
            elenco = ", ".join(u["paziente"] for u in trovati)
            print(f"Attenzione: '{token.strip()}' corrisponde a più pazienti: {elenco}", file=sys.stderr)
        scelti += [u for u in trovati if u not in scelti]
    return scelti


def blocchi(utente):
    """Elenco ordinato di (nome, farmaci, righe): fasce standard + eventuali extra."""
    trovati = {}
    for s in utente["somministrazioni"]:
        trovati[s["nome"].upper()] = s
    voci = []
    for nome, (ordine, righe) in STANDARD.items():
        voci.append((ordine, nome, trovati.pop(nome, {}).get("farmaci", []), righe))
    for nome, s in trovati.items():
        ordine = 12 * 60
        if s.get("orario"):
            h, m = s["orario"].split(":")
            ordine = int(h) * 60 + int(m)
        voci.append((ordine, s["nome"].upper(), s["farmaci"], RIGHE_EXTRA))
    voci.sort(key=lambda v: v[0])
    return [(n, f, max(r, len(f))) for _, n, f, r in voci]


def data_str(d):
    return f"{d.day}/{d.month}/{d.year}"


# ---------------------------------------------------------------- disegno
def testo(c, x, y, s, size=9, font="Helvetica", align="left"):
    c.setFont(font, size)
    {"left": c.drawString, "center": c.drawCentredString, "right": c.drawRightString}[align](x, y, s)


def intestazione(c, paziente, data):
    """Logo, titolo, paziente e data. Ritorna la y sotto l'intestazione."""
    top = H - 55
    testo(c, 320, top, TITOLO, 13, "Helvetica-Bold", "center")
    c.drawImage(str(LOGO), 62, top - 62, width=82, height=82 * 204 / 354, mask="auto")
    for i, (lab, val) in enumerate((("PAZIENTE:", paziente), ("DATA:", data))):
        y = top - 28 - i * 19
        testo(c, 200, y, lab, 10)
        c.setLineWidth(THIN)
        c.line(275, y - 3, 455, y - 3)
        testo(c, 365, y, val, 10, align="center")
    return top - 70


def tabella(c, x0, x1, ytop, righe, h, colonne, celle=None, spessa=True):
    """Griglia di `righe` righe alte h; colonne = x dei separatori interni.
    celle = lista di righe, ciascuna lista di testi per colonna."""
    ybot = ytop - righe * h
    c.setLineWidth(THIN)
    for i in range(1, righe):
        c.line(x0, ytop - i * h, x1, ytop - i * h)
    for x in colonne:
        c.line(x, ytop, x, ybot)
    c.setLineWidth(THICK if spessa else THIN)
    c.rect(x0, ybot, x1 - x0, ytop - ybot)
    if celle:
        xs = [x0] + list(colonne) + [x1]
        size = min(9.5, h - 6)
        for i, riga in enumerate(celle):
            for j, val in enumerate(riga):
                if val:
                    testo(c, xs[j] + 4, ytop - i * h - h / 2 - size * 0.35, val, size)
    return ybot


def pagina_fronte(c, u, data):
    y = intestazione(c, u["paziente"], data)
    testo(c, 155, y - 12, "FARMACO", 7, "Helvetica-Oblique", "center")
    y -= 20
    cols = (210, 256, 400)
    for x, lab in zip((233, 328, 470), ("Q.TA'", "OPERATORE", "UTENTE")):
        testo(c, x, y - 6, lab, 7, "Helvetica-Oblique", "center")
    y -= 12

    voci = blocchi(u)
    n_righe = sum(r for _, _, r in voci)
    n_note = max(len(u["note"]), 2)
    # spazio: footer (serd/medico/psichiatra + note) e distanze tra blocchi
    footer = 75 + n_note * 15
    gap = 22
    disponibile = y - 45 - footer - gap * (len(voci) - 1)
    h = min(19.2, disponibile / n_righe)

    for nome, farmaci, righe in voci:
        celle = [[f["farmaco"], f.get("quantita")] for f in farmaci]
        ybot = tabella(c, X0, X1, y, righe, h, cols, celle)
        c.saveState()
        c.translate(X0 - 8, (y + ybot) / 2)
        c.rotate(90)
        testo(c, 0, 0, nome, 9, align="center")
        c.restoreState()
        y = ybot - gap

    y += gap - 22
    for lab, val in (
        ("SERD INVIANTE:", u["serd_inviante"]),
        ("MEDICO SERD:", u["medico_serd"]),
        ("PSICHIATRA CT:", u["psichiatra_ct"]),
    ):
        testo(c, 168, y, lab, 8, "Helvetica-Oblique", "right")
        c.setLineWidth(THIN)
        c.line(190, y - 3, 322, y - 3)
        if val:
            testo(c, 256, y, val.strip(), 8, align="center")
        y -= 18
    testo(c, X0 - 8, y - 2, "NOTE:", 7, "Helvetica-Oblique")
    tabella(c, X0 - 8, X1, y - 6, n_note, 15, (), [[n] for n in u["note"]])


def pagina_retro(c, u, data):
    y = intestazione(c, u["paziente"], data)
    testo(c, X0 - 8, y - 10, "AL BISOGNO:", 7, "Helvetica-Oblique")
    n = max(len(u["al_bisogno"]), 7)
    y = tabella(c, X0 - 8, X1, y - 14, n, 18.5, (), [[b] for b in u["al_bisogno"]])

    y -= 45
    cols = (227, 273, 321, 410)
    xs = [X0 - 8] + list(cols) + [X1]
    for i, lab in enumerate(("FARMACO", "ORE", "Q.TA'", "OPERATORE", "UTENTE")):
        testo(c, (xs[i] + xs[i + 1]) / 2, y, lab, 7, "Helvetica-Oblique", "center")
    tabella(c, X0 - 8, X1, y - 6, 9, 19.5, cols)


def genera(utenti, giorni, out):
    c = canvas.Canvas(out if hasattr(out, "write") else str(out), pagesize=A4)
    c.setTitle("Schede terapia")
    for g in giorni:
        for u in utenti:
            for pagina in (pagina_fronte, pagina_retro):
                pagina(c, u, data_str(g))
                c.showPage()
    c.save()


# ---------------------------------------------------------------- cli
def parse_data(s):
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        raise argparse.ArgumentTypeError(f"data non valida '{s}' (formato gg/mm/aaaa)")


def main():
    ap = argparse.ArgumentParser(description="Genera il PDF delle schede terapia.")
    ap.add_argument("nomi", help="nomi separati da virgola (case insensitive) oppure TUTTI")
    ap.add_argument("data_inizio", type=parse_data, help="gg/mm/aaaa")
    ap.add_argument("data_fine", type=parse_data, nargs="?", help="gg/mm/aaaa (facoltativa)")
    ap.add_argument("-o", "--output", help="file PDF di output")
    ap.add_argument("--json", default=str(BASE / "utenti.json"), help="file dati (default: utenti.json)")
    a = ap.parse_args()

    fine = a.data_fine or a.data_inizio
    if fine < a.data_inizio:
        ap.error("la data di fine precede la data di inizio")

    utenti = json.loads(Path(a.json).read_text(encoding="utf-8"))
    scelti = seleziona(utenti, a.nomi)
    giorni = [a.data_inizio + timedelta(days=i) for i in range((fine - a.data_inizio).days + 1)]

    out = a.output or f"schede_terapia_{a.data_inizio:%Y%m%d}" + (f"_{fine:%Y%m%d}" if a.data_fine else "") + ".pdf"
    genera(scelti, giorni, out)
    print(f"{out}: {len(scelti)} pazienti x {len(giorni)} giorni = {len(scelti) * len(giorni) * 2} pagine")


if __name__ == "__main__":
    main()
