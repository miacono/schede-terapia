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
"""Server locale per modificare utenti.json e generare il PDF delle schede terapia.

Uso:
    editor.py [--port 8000] [--json utenti.json] [--no-browser]

Poi si apre http://127.0.0.1:8000 (si apre da solo). Il server ascolta solo
sul computer locale: i dati non escono dalla macchina.

Richiede: reportlab (pip install -r requirements.txt)
"""
import argparse
import io
import json
import os
import shutil
import sys
import threading
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import genera_schede

BASE = Path(__file__).resolve().parent
HTML = BASE / "editor.html"
MAX_BODY = 5 * 1024 * 1024
MAX_GIORNI = 62
GIORNI_BACKUP = 30
CARTELLA_BACKUP = "backup"  # sottocartella accanto al file JSON


def valida(utenti):
    """Controlla la struttura minima attesa dallo script dei PDF. Ritorna un messaggio d'errore o None."""
    if not isinstance(utenti, list):
        return "i dati devono essere un elenco di pazienti"
    visti = set()
    for u in utenti:
        if not isinstance(u, dict):
            return "paziente non valido"
        nome = (u.get("paziente") or "").strip()
        if not nome:
            return "c'è un paziente senza nome"
        if nome.casefold() in visti:
            return f"paziente duplicato: {nome}"
        visti.add(nome.casefold())
        for campo in ("note", "al_bisogno"):
            if not isinstance(u.get(campo, []), list):
                return f"{nome}: '{campo}' deve essere un elenco"
        somm = u.get("somministrazioni", [])
        if not isinstance(somm, list):
            return f"{nome}: 'somministrazioni' deve essere un elenco"
        for s in somm:
            if not isinstance(s, dict) or not str(s.get("nome", "")).strip():
                return f"{nome}: somministrazione senza nome"
            orario = s.get("orario")
            if orario:
                try:
                    datetime.strptime(orario, "%H:%M")
                except ValueError:
                    return f"{nome}: orario '{orario}' non valido (usa hh:mm)"
            if not isinstance(s.get("farmaci", []), list):
                return f"{nome}: 'farmaci' deve essere un elenco"
    return None


def completa(u):
    """Riempie i campi mancanti, così lo script dei PDF trova sempre tutte le chiavi."""
    u = dict(u)
    u["paziente"] = u["paziente"].strip()
    for k in ("serd_inviante", "medico_serd", "psichiatra_ct"):
        u[k] = (u.get(k) or "").strip() or None
    u["note"] = [n for n in u.get("note", []) if str(n).strip()]
    u["al_bisogno"] = [n for n in u.get("al_bisogno", []) if str(n).strip()]
    u["somministrazioni"] = [
        {
            "nome": str(s["nome"]).strip(),
            "orario": s.get("orario") or None,
            "farmaci": [f for f in s.get("farmaci", []) if str(f.get("farmaco", "")).strip()],
        }
        for s in u.get("somministrazioni", [])
    ]
    return u


def cartella_backup(json_path):
    return json_path.parent / CARTELLA_BACKUP


def pulisci_backup(json_path, giorni=GIORNI_BACKUP):
    """Elimina i backup più vecchi di `giorni`. L'età si legge dal timestamp nel nome del file."""
    limite = datetime.now() - timedelta(days=giorni)
    for f in cartella_backup(json_path).glob(f"{json_path.stem}_*.json.bak"):
        try:
            quando = datetime.strptime(f.name[len(json_path.stem) + 1:-len(".json.bak")], "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue  # nome non riconosciuto: non toccare
        if quando < limite:
            f.unlink()


class Handler(BaseHTTPRequestHandler):
    json_path: Path = BASE / "utenti.json"
    port = 8000

    def log_message(self, fmt, *args):
        if sys.stderr:  # con pythonw.exe (Windows, senza console) stderr vale None
            sys.stderr.write("%s\n" % (fmt % args))

    # -- utilità
    def _host_ok(self):
        # difesa da DNS rebinding: accetta solo richieste dirette a localhost
        host = (self.headers.get("Host") or "").split(":")[0]
        return host in ("127.0.0.1", "localhost")

    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code, msg):
        self._send(code, {"errore": msg})

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("richiesta troppo grande")
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def _guard(self):
        if not self._host_ok():
            self._err(403, "host non consentito")
            return False
        return True

    # -- rotte
    def do_GET(self):
        if not self._guard():
            return
        if self.path in ("/", "/index.html"):
            self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/utenti":
            try:
                data = json.loads(self.json_path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                data = []
            self._send(200, data)
        else:
            self._err(404, "non trovato")

    def do_PUT(self):
        if not self._guard():
            return
        if self.path != "/api/utenti":
            return self._err(404, "non trovato")
        try:
            utenti = self._body()
            errore = valida(utenti)
            if errore:
                return self._err(400, errore)
            utenti = [completa(u) for u in utenti]
            backup = None
            if self.json_path.exists():
                ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                cartella = cartella_backup(self.json_path)
                cartella.mkdir(exist_ok=True)
                backup = cartella / f"{self.json_path.stem}_{ts}.json.bak"
                shutil.copy2(self.json_path, backup)
                pulisci_backup(self.json_path)
            tmp = self.json_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(utenti, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.json_path)
            self._send(200, {"ok": True, "pazienti": len(utenti), "backup": f"{CARTELLA_BACKUP}/{backup.name}" if backup else None})
        except (ValueError, json.JSONDecodeError) as e:
            self._err(400, str(e))

    def do_POST(self):
        if not self._guard():
            return
        if self.path != "/api/pdf":
            return self._err(404, "non trovato")
        try:
            req = self._body()
            utenti = req.get("utenti")
            errore = valida(utenti)
            if errore:
                return self._err(400, errore)
            if not utenti:
                return self._err(400, "nessun paziente selezionato")
            utenti = [completa(u) for u in utenti]
            inizio = datetime.strptime(req["data_inizio"], "%Y-%m-%d").date()
            fine = datetime.strptime(req.get("data_fine") or req["data_inizio"], "%Y-%m-%d").date()
            if fine < inizio:
                return self._err(400, "la data di fine precede la data di inizio")
            giorni = [inizio + timedelta(days=i) for i in range((fine - inizio).days + 1)]
            if len(giorni) > MAX_GIORNI:
                return self._err(400, f"massimo {MAX_GIORNI} giorni per volta")
            buf = io.BytesIO()
            genera_schede.genera(utenti, giorni, buf)
            nome = f"schede_terapia_{inizio:%Y%m%d}" + (f"_{fine:%Y%m%d}" if fine != inizio else "") + ".pdf"
            self._send(200, buf.getvalue(), "application/pdf",
                       {"Content-Disposition": f'attachment; filename="{nome}"'})
        except (KeyError, ValueError, TypeError, json.JSONDecodeError) as e:
            self._err(400, f"richiesta non valida: {e}")


def main():
    ap = argparse.ArgumentParser(description="Editor locale di utenti.json + generatore PDF.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--json", default=str(BASE / "utenti.json"), help="file dati (default: utenti.json)")
    ap.add_argument("--no-browser", action="store_true", help="non aprire il browser")
    a = ap.parse_args()

    Handler.json_path = Path(a.json).resolve()
    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}"
    print(f"Editor attivo su {url}  (Ctrl+C per uscire)\nDati: {Handler.json_path}")
    if not a.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nChiuso.")


if __name__ == "__main__":
    main()
