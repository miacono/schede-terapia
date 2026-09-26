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
    src/editor.py [--port 8000] [--json utenti.json] [--no-browser]

Poi si apre http://127.0.0.1:8000 (si apre da solo). Il server ascolta solo
sul computer locale: i dati non escono dalla macchina.

Richiede: reportlab (pip install -r requirements.txt)
"""
import argparse
import io
import json
import os
import shutil
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import genera_schede

BASE = Path(__file__).resolve().parent  # cartella src/
RADICE = BASE.parent  # cartella del programma
DATI = RADICE / "data"
JSON_PREDEFINITO = DATI / "utenti.json"
TEMPLATE = DATI / "utenti.json.template"
HTML = BASE / "editor.html"
MAX_BODY = 5 * 1024 * 1024
MAX_GIORNI = 62
GIORNI_BACKUP = 365
CARTELLA_BACKUP = "backup"  # sottocartella accanto al file JSON (data/backup/)
# Timestamp nel nome dei backup: niente ":" perché Windows non li ammette nei nomi di file.
FORMATO_BACKUP = "%Y-%m-%dT%H-%M-%S"


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
            quando = datetime.strptime(f.name[len(json_path.stem) + 1:-len(".json.bak")], FORMATO_BACKUP)
        except ValueError:
            continue  # nome non riconosciuto: non toccare
        if quando < limite:
            try:
                f.unlink()
            except OSError:
                pass  # su Windows un file aperto non si cancella: ci si riprova al prossimo salvataggio


def sostituisci(tmp, dest, tentativi=10, attesa=0.1):
    """os.replace con qualche nuovo tentativo: su Windows fallisce se `dest` è aperto
    in quel momento da un altro programma (antivirus, sincronizzazione cloud, una lettura in corso)."""
    for i in range(tentativi):
        try:
            os.replace(tmp, dest)
            return
        except PermissionError:
            if i == tentativi - 1:
                raise
            time.sleep(attesa)


def sposta_senza_sovrascrivere(src, dst):
    """Sposta `src` in `dst` solo se `dst` non esiste ancora; ritorna False se esiste già.
    Niente os.rename o shutil.move: su Linux sovrascrivono in silenzio un file esistente.
    La creazione esclusiva ("xb") invece fallisce allo stesso modo su Linux e su Windows."""
    dati = src.read_bytes()
    try:
        f = open(dst, "xb")
    except FileExistsError:
        return False
    try:
        with f:
            f.write(dati)
        if dst.read_bytes() != dati:
            raise OSError(f"la copia di {src} in {dst} non corrisponde all'originale")
        shutil.copystat(src, dst)
    except BaseException:
        dst.unlink()  # creato poco fa da questa funzione: si torna alla situazione di partenza
        raise
    src.unlink()  # l'originale si cancella solo dopo che la copia è stata verificata
    return True


def prepara_dati(json_path):
    """Sposta in data/ i dati della vecchia struttura (utenti.json e backup/ nella cartella del
    programma) e crea utenti.json dal template se manca. Non sovrascrive mai un file esistente.
    Ritorna gli avvisi da mostrare all'utente."""
    avvisi = []
    json_path.parent.mkdir(exist_ok=True)

    vecchio = RADICE / json_path.name
    if vecchio.is_file() and not sposta_senza_sovrascrivere(vecchio, json_path):
        avvisi.append(f"Ci sono due file dei dati: si usa {json_path}.\n"
                      f"Il vecchio {vecchio} non è stato toccato: controllalo e, se non serve più, eliminalo.")

    vecchi_backup = RADICE / CARTELLA_BACKUP
    if vecchi_backup.is_dir():
        nuovi_backup = cartella_backup(json_path)
        nuovi_backup.mkdir(exist_ok=True)
        rimasti = 0
        for f in sorted(vecchi_backup.iterdir()):
            if f.is_file() and f.name != ".gitkeep" and not sposta_senza_sovrascrivere(f, nuovi_backup / f.name):
                rimasti += 1
        if rimasti:
            avvisi.append(f"{rimasti} backup in {vecchi_backup} hanno lo stesso nome di backup già presenti "
                          f"in {nuovi_backup} e non sono stati spostati: controllali a mano.")
        # la vecchia cartella si toglie solo se è rimasto al più il segnaposto vuoto di git
        segnaposto = vecchi_backup / ".gitkeep"
        if [f.name for f in vecchi_backup.iterdir()] == [".gitkeep"] and segnaposto.stat().st_size == 0:
            segnaposto.unlink()
        try:
            vecchi_backup.rmdir()  # fallisce, lasciandola dov'è, se non è vuota
        except OSError:
            pass

    if not json_path.exists():
        dati = TEMPLATE.read_bytes()
        try:
            with open(json_path, "xb") as f:
                f.write(dati)
        except FileExistsError:
            pass
    return avvisi


class Handler(BaseHTTPRequestHandler):
    json_path: Path = JSON_PREDEFINITO
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
        # un sito esterno non deve poter comandare il server dal browser dell'utente
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost"):
            self._err(403, "origine non consentita")
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
                # utf-8-sig: accetta anche il BOM che il Blocco note di Windows può aggiungere
                data = json.loads(self.json_path.read_text(encoding="utf-8-sig"))
            except FileNotFoundError:
                data = []
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                return self._err(500, f"{self.json_path.name} non leggibile (deve essere JSON in UTF-8): {e}")
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
        except (ValueError, json.JSONDecodeError) as e:
            return self._err(400, str(e))
        tmp = self.json_path.with_suffix(".json.tmp")
        try:
            backup = None
            if self.json_path.exists():
                ts = datetime.now().strftime(FORMATO_BACKUP)
                cartella = cartella_backup(self.json_path)
                cartella.mkdir(exist_ok=True)
                backup = cartella / f"{self.json_path.stem}_{ts}.json.bak"
                shutil.copy2(self.json_path, backup)
                pulisci_backup(self.json_path)
            tmp.write_text(json.dumps(utenti, ensure_ascii=False, indent=2), encoding="utf-8")
            sostituisci(tmp, self.json_path)
        except OSError as e:
            try:
                tmp.unlink()
            except OSError:
                pass
            return self._err(500, f"salvataggio non riuscito (il file è forse aperto in un altro programma?): {e}")
        self._send(200, {"ok": True, "pazienti": len(utenti), "backup": f"{CARTELLA_BACKUP}/{backup.name}" if backup else None})

    def do_POST(self):
        if not self._guard():
            return
        if self.path == "/api/esci":
            self._send(200, {"ok": True})
            # shutdown() blocca finché serve_forever() non termina: va chiamato da un altro thread
            threading.Thread(target=self.server.shutdown, daemon=True).start()
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


class Server(ThreadingHTTPServer):
    # Su Windows SO_REUSEADDR lascerebbe aprire a un secondo processo una porta già in uso:
    # lì si chiede l'uso esclusivo. Su Linux invece serve per poter riavviare subito il server.
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def editor_attivo(url):
    """True se su `url` risponde già un editor delle schede (ignorando eventuali proxy di sistema)."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url + "/api/utenti", timeout=2) as r:
            return r.status == 200 and r.headers.get_content_type() == "application/json"
    except (OSError, ValueError):
        return False


def avvisa(msg, errore=True):
    """Mostra un messaggio anche quando non c'è console (pythonw.exe su Windows: stderr vale None)."""
    if sys.stderr:
        print(msg, file=sys.stderr)
    elif os.name == "nt":
        import ctypes
        icona = 0x10 if errore else 0x30  # icona di errore / di avviso
        ctypes.windll.user32.MessageBoxW(None, msg, "Schede terapia", icona)


def main():
    ap = argparse.ArgumentParser(description="Editor locale di utenti.json + generatore PDF.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--json", default=str(JSON_PREDEFINITO), help="file dati (default: data/utenti.json)")
    ap.add_argument("--no-browser", action="store_true", help="non aprire il browser")
    a = ap.parse_args()

    Handler.json_path = Path(a.json).resolve()
    url = f"http://127.0.0.1:{a.port}"
    try:
        server = Server(("127.0.0.1", a.port), Handler)
    except OSError as e:
        if editor_attivo(url):
            # l'editor è già acceso: basta aprire il browser su quello
            print(f"Editor già attivo su {url}")
            if not a.no_browser:
                webbrowser.open(url)
            return
        avvisa(f"Impossibile avviare l'editor sulla porta {a.port}: forse è usata da un altro programma.\n"
               f"Chiudilo oppure usa un'altra porta (--port, o PORT in avvia_editor.bat).\n\n{e}")
        sys.exit(1)
    if Handler.json_path == JSON_PREDEFINITO:
        # dopo l'avvio del server, così due istanze lanciate insieme non spostano i file in contemporanea
        try:
            for msg in prepara_dati(Handler.json_path):
                avvisa(msg, errore=False)
        except OSError as e:
            server.server_close()
            avvisa(f"Impossibile preparare la cartella dei dati: {e}\nNessun file è stato sovrascritto.")
            sys.exit(1)
    print(f"Editor attivo su {url}  (Ctrl+C o pulsante Esci)\nDati: {Handler.json_path}")
    if not a.no_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("\nChiuso.")


if __name__ == "__main__":
    main()
