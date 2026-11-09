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
"""Genera il PDF delle schede sostitutivi (foglio firme con il saldo del farmaco).

Ogni scheda va dalla data di inizio al primo martedì (compreso): per ogni giorno e
per ogni orario riporta la quantità da somministrare, lo spazio per la firma
dell'operatore e dell'utente e il saldo rimasto, calcolato dalla quantità iniziale.

Uso:
    src/genera_sostitutivi.py NOMI [-o FILE.pdf] [--json sostitutivi.json]

    NOMI   cognomi/nomi separati da virgola (case insensitive) oppure TUTTI

Esempio:
    src/genera_sostitutivi.py TUTTI
    src/genera_sostitutivi.py rossi -o /tmp/prova.pdf

Richiede: reportlab (pip install reportlab)
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from genera_schede import RADICE, THICK, THIN, X0, X1, intestazione, seleziona, testo

JSON_PREDEFINITO = RADICE / "data" / "sostitutivi.json"
ORARI_PREDEFINITI = ("08:30", "13:00", "18:00", "23:00")
MARTEDI = 1  # date.weekday(): la scheda finisce sempre di martedì
GIORNI = ("lun", "mar", "mer", "gio", "ven", "sab", "dom")

W, H = A4
X_INIZIO = X0 - 8  # la tabella è larga quanto le tabelle "note" e "al bisogno" delle schede terapia
# Separatori interni delle colonne DATA | ORA | Q.TA' | FIRMA OPERATORE | FIRMA UTENTE | SALDO.
COLONNE = (165, 210, 256, 363, 470)  # le due colonne delle firme sono larghe uguale (107 pt)
ALTEZZA_MAX, ALTEZZA_MIN = 20, 13  # altezza delle righe; sotto il minimo si passa a più pagine
# Bordo superiore della tabella: sotto intestazione (H - 125), titolo e campi (60) e header di colonna (12).
Y_TABELLA = H - 125 - 60 - 12


# ---------------------------------------------------------------- dati
def data_fine(inizio):
    """Il primo martedì a partire da `inizio` (lo stesso giorno, se è martedì)."""
    return inizio + timedelta(days=(MARTEDI - inizio.weekday()) % 7)


def periodo(scheda):
    inizio = date.fromisoformat(scheda["data_inizio"])
    return [inizio + timedelta(days=i) for i in range((data_fine(inizio) - inizio).days + 1)]


def minuti(orario):
    h, m = orario.split(":")
    return int(h) * 60 + int(m)


def hhmm(orario):
    """"8:30" -> "08:30"."""
    return f"{minuti(orario) // 60:02d}:{minuti(orario) % 60:02d}"


def numero(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0


def piano(scheda):
    """Elenco di (giorno, [(orario, quantità, saldo dopo la somministrazione)]).
    La quantità di un orario è quella standard, salvo una variazione per quel giorno."""
    orari = sorted(scheda["orari"], key=lambda o: minuti(o["orario"]))
    variazioni = scheda.get("variazioni") or {}
    saldo = scheda["quantita_iniziale"]
    righe = []
    for g in periodo(scheda):
        del_giorno = variazioni.get(g.isoformat(), {})
        somm = []
        for o in orari:
            q = del_giorno.get(o["orario"], o["quantita"])
            saldo = round(saldo - q, 3)  # niente residui tipo 0.30000000000000004
            somm.append((o["orario"], q, saldo))
        righe.append((g, somm))
    return righe


def valida(schede):
    """Controlla la struttura di sostitutivi.json. Ritorna un messaggio d'errore o None."""
    if not isinstance(schede, list):
        return "i dati devono essere un elenco di schede sostitutivi"
    viste = set()
    for s in schede:
        if not isinstance(s, dict):
            return "scheda sostitutivi non valida"
        nome = str(s.get("paziente") or "").strip()
        if not nome:
            return "c'è una scheda sostitutivi senza paziente"
        farmaco = str(s.get("farmaco") or "").strip()
        if not farmaco:
            return f"{nome}: manca il nome del farmaco sostitutivo"
        try:
            inizio = date.fromisoformat(str(s.get("data_inizio")))
        except ValueError:
            return f"{nome}, {farmaco}: data di inizio mancante o non valida"
        chiave = (nome.casefold(), farmaco.casefold(), inizio)
        if chiave in viste:
            return f"scheda duplicata: {nome}, {farmaco}, dal {inizio:%d/%m/%Y}"
        viste.add(chiave)
        if not numero(s.get("quantita_iniziale")):
            return f"{nome}, {farmaco}: la quantità iniziale deve essere un numero (0 o più)"
        orari = s.get("orari")
        if not isinstance(orari, list) or not orari:
            return f"{nome}, {farmaco}: serve almeno un orario"
        visti = set()
        for o in orari:
            if not isinstance(o, dict):
                return f"{nome}, {farmaco}: orario non valido"
            try:
                datetime.strptime(str(o.get("orario")), "%H:%M")
            except ValueError:
                return f"{nome}, {farmaco}: orario '{o.get('orario')}' non valido (usa hh:mm)"
            if hhmm(o["orario"]) in visti:
                return f"{nome}, {farmaco}: orario {o['orario']} ripetuto"
            visti.add(hhmm(o["orario"]))
            if not numero(o.get("quantita")):
                return f"{nome}, {farmaco}: la quantità delle {o['orario']} deve essere un numero (0 o più)"
        variazioni = s.get("variazioni") or {}
        if not isinstance(variazioni, dict):
            return f"{nome}, {farmaco}: 'variazioni' deve essere un oggetto"
        for giorno, quantita in variazioni.items():
            try:
                date.fromisoformat(giorno)
            except ValueError:
                return f"{nome}, {farmaco}: giorno '{giorno}' non valido nelle variazioni"
            if not isinstance(quantita, dict) or not all(numero(q) for q in quantita.values()):
                return f"{nome}, {farmaco}: le variazioni del {giorno} devono essere numeri (0 o più)"
            for orario in quantita:
                try:
                    datetime.strptime(orario, "%H:%M")
                except ValueError:
                    return f"{nome}, {farmaco}: orario '{orario}' non valido nelle variazioni del {giorno}"
    return None


def completa(s):
    """Normalizza una scheda già validata: toglie spazi e le variazioni che non servono più
    (fuori dal periodo, per orari tolti o uguali alla quantità standard)."""
    s = dict(s)
    s["paziente"] = s["paziente"].strip()
    s["farmaco"] = s["farmaco"].strip()
    s["unita"] = (s.get("unita") or "").strip() or "mg"
    s["orari"] = sorted(({"orario": hhmm(o["orario"]), "quantita": o["quantita"]} for o in s["orari"]),
                        key=lambda o: minuti(o["orario"]))
    standard = {o["orario"]: o["quantita"] for o in s["orari"]}
    giorni = {g.isoformat() for g in periodo(s)}
    variazioni = {}
    for giorno, quantita in sorted((s.get("variazioni") or {}).items()):
        utili = {hhmm(k): v for k, v in quantita.items() if hhmm(k) in standard and v != standard[hhmm(k)]}
        if giorno in giorni and utili:
            variazioni[giorno] = utili
    s["variazioni"] = variazioni
    return s


def qta_str(q):
    """40 -> "40", 2.5 -> "2,5" (virgola decimale all'italiana)."""
    return f"{q:g}".replace(".", ",")


def giorno_str(g):
    return f"{GIORNI[g.weekday()]} {g.day:02d}/{g.month:02d}/{g.year}"


# ---------------------------------------------------------------- disegno
def testata(c, s, pagina, pagine):
    giorni = periodo(s)
    y = intestazione(c, s["paziente"], f"{giorni[0]:%d/%m/%Y} - {giorni[-1]:%d/%m/%Y}")
    titolo = "SCHEDA SOSTITUTIVO" + (f" ({pagina}/{pagine})" if pagine > 1 else "")
    testo(c, (X_INIZIO + X1) / 2, y - 14, titolo, 11, "Helvetica-Bold", "center")
    y -= 38
    for x, lab, val, fine in ((X_INIZIO, "FARMACO:", s["farmaco"], 330),
                              (350, "QU.TA' INIZIALE:", f"{qta_str(s['quantita_iniziale'])} {s['unita']}", X1)):
        testo(c, x, y, lab, 8, "Helvetica-Oblique")
        inizio = x + c.stringWidth(lab, "Helvetica-Oblique", 8) + 6
        c.setLineWidth(THIN)
        c.line(inizio, y - 3, fine, y - 3)
        testo(c, (inizio + fine) / 2, y, val, 10, align="center")
    return y - 22  # = Y_TABELLA + 12


def tabella_giorni(c, ytop, giorni, h, unita):
    """Una fascia di righe per giorno: la data occupa tutta la fascia, le righe sono gli orari."""
    xs = (X_INIZIO,) + COLONNE + (X1,)
    for i, lab in enumerate(("DATA", "ORA", f"Q.TA' ({unita})", "FIRMA OPERATORE", "FIRMA UTENTE", "SALDO")):
        testo(c, (xs[i] + xs[i + 1]) / 2, ytop + 4, lab, 7, "Helvetica-Oblique", "center")
    size = min(9.5, h - 6)
    y = ytop
    for g, somm in giorni:
        ybot = y - len(somm) * h
        c.setLineWidth(THIN)
        for i in range(1, len(somm)):
            c.line(COLONNE[0], y - i * h, X1, y - i * h)
        for x in COLONNE:
            c.line(x, y, x, ybot)
        testo(c, (xs[0] + xs[1]) / 2, (y + ybot) / 2 - size * 0.35, giorno_str(g), size, align="center")
        for i, (orario, q, saldo) in enumerate(somm):
            yt = y - i * h - h / 2 - size * 0.35
            testo(c, (xs[1] + xs[2]) / 2, yt, orario.replace(":", "."), size, align="center")
            testo(c, (xs[2] + xs[3]) / 2, yt, qta_str(q) if q else "--", size, align="center")
            testo(c, (xs[5] + xs[6]) / 2, yt, qta_str(saldo), size,
                  "Helvetica-Bold" if saldo < 0 else "Helvetica", "center")
        c.setLineWidth(THICK * 0.7)  # separa i giorni
        c.line(X_INIZIO, ybot, X1, ybot)
        y = ybot
    c.setLineWidth(THICK)
    c.rect(X_INIZIO, y, X1 - X_INIZIO, ytop - y)


def pagine_scheda(s, disponibile):
    """Divide i giorni in pagine e sceglie l'altezza delle righe."""
    giorni = piano(s)
    per_giorno = len(s["orari"])
    h = min(ALTEZZA_MAX, disponibile / (len(giorni) * per_giorno))
    if h >= ALTEZZA_MIN:
        return [giorni], h
    n = max(1, int(disponibile // (ALTEZZA_MIN * per_giorno)))
    blocchi = [giorni[i:i + n] for i in range(0, len(giorni), n)]
    return blocchi, min(ALTEZZA_MAX, disponibile / (n * per_giorno))


def genera(schede, out):
    c = canvas.Canvas(out if hasattr(out, "write") else str(out), pagesize=A4)
    c.setTitle("Schede sostitutivi")
    for s in schede:
        blocchi, h = pagine_scheda(s, Y_TABELLA - 45)
        for i, giorni in enumerate(blocchi, 1):
            y = testata(c, s, i, len(blocchi))
            tabella_giorni(c, y - 12, giorni, h, s["unita"])
            c.showPage()
    c.save()


# ---------------------------------------------------------------- cli
def main():
    ap = argparse.ArgumentParser(description="Genera il PDF delle schede sostitutivi.")
    ap.add_argument("nomi", help="nomi separati da virgola (case insensitive) oppure TUTTI")
    ap.add_argument("-o", "--output", help="file PDF di output")
    ap.add_argument("--json", default=str(JSON_PREDEFINITO), help="file dati (default: data/sostitutivi.json)")
    a = ap.parse_args()

    try:
        # utf-8-sig: accetta anche il BOM che il Blocco note di Windows può aggiungere
        schede = json.loads(Path(a.json).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        sys.exit(f"Errore: impossibile leggere '{a.json}' (deve essere JSON in UTF-8): {e}")
    errore = valida(schede)
    if errore:
        sys.exit(f"Errore in '{a.json}': {errore}")
    scelte = [completa(s) for s in seleziona(schede, a.nomi)]
    if not scelte:
        sys.exit(f"Errore: nessuna scheda sostitutivi in '{a.json}'.")
    for s in scelte:
        saldo = piano(s)[-1][1][-1][2]
        if saldo < 0:
            print(f"Attenzione: {s['paziente']}, {s['farmaco']}: la quantità iniziale non basta "
                  f"(saldo finale {qta_str(saldo)} {s['unita']})", file=sys.stderr)

    inizio = min(date.fromisoformat(s["data_inizio"]) for s in scelte)
    out = a.output or f"schede_sostitutivi_{inizio:%Y%m%d}.pdf"
    try:
        genera(scelte, out)
    except OSError as e:
        # tipico su Windows: il PDF è ancora aperto nel lettore, che lo blocca
        sys.exit(f"Errore: impossibile scrivere '{out}' (il file è forse aperto in un altro programma?): {e}")
    print(f"{out}: {len(scelte)} schede sostitutivi")


if __name__ == "__main__":
    main()
