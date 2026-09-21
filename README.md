# Schede terapia

Strumenti per gestire e stampare le **schede terapia** del Servizio Residenziale Villa Silenzi.

Le schede sono descritte in un unico file `utenti.json`. Da lì si può:

- **modificare** i dati con un editor web locale, senza conoscere la sintassi JSON;
- **generare il PDF** delle schede, un foglio fronte/retro per paziente e per giorno.

Ogni scheda ha due facciate:

| Facciata | Contenuto |
|---|---|
| Fronte | logo e titolo, paziente e data, somministrazioni (Mattino, Pranzo, Cena, Notte ed eventuali altre fasce), SERD inviante, medico SERD, psichiatra CT, note |
| Retro | logo e titolo, paziente e data, terapia al bisogno, tabella di somministrazione della terapia al bisogno |

> ⚠️ **Privacy.** `utenti.json` contiene dati sanitari di persone reali ed è escluso dal repository tramite `.gitignore`, insieme ai suoi backup e ai PDF generati. Non committarli mai.

## Requisiti

- Python 3.9+
- [reportlab](https://pypi.org/project/reportlab/)

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

## Primi passi

Il repository contiene solo `utenti.json.template`, con dati inventati. Per iniziare copialo:

```bash
cp utenti.json.template utenti.json
```

e poi modificalo con l'editor (vedi sotto) o a mano.

## Editor web locale

```bash
venv/bin/python editor.py
```

Si apre il browser su `http://127.0.0.1:8000`. Opzioni: `--port 8080`, `--no-browser`, `--json altro_file.json`.

Dalla pagina si può:

- cercare, aggiungere ed eliminare pazienti;
- modificare SERD, medico e psichiatra;
- aggiungere, togliere e riordinare fasce, farmaci, note e righe "al bisogno";
- **salvare** le modifiche in `utenti.json`;
- **uscire** con il pulsante *Esci*, che spegne il server;
- **generare il PDF** scegliendo pazienti e date (include anche le modifiche non ancora salvate).

Ad ogni salvataggio il file corrente viene copiato nella cartella `backup/` come `utenti_AAAA-MM-GGTHH:MM:SS.json.bak` (per esempio `backup/utenti_2026-09-21T21:58:00.json.bak`); la cartella viene creata se manca. I backup più vecchi di 30 giorni vengono eliminati automaticamente (costante `GIORNI_BACKUP` in `editor.py`).

Il server ascolta **solo su `127.0.0.1`** e rifiuta richieste con un `Host` diverso da localhost: i dati non escono dal computer.

### Avvio su Windows

Su Windows si usa `avvia_editor.bat` (doppio clic, oppure un collegamento sul desktop con la sua icona). Serve Python 3.9 o successivo installato (con il *py launcher*).

- **Primo avvio:** crea `venv`, installa le dipendenze (serve internet) e crea `utenti.json` dal template.
- **Avvio normale:** lancia l'editor **senza finestra console** e apre il browser su `http://127.0.0.1:8000`.
- **Chiusura:** con il pulsante **Esci** nella pagina. Chiudere solo la scheda del browser *non* ferma il server.
- **Già acceso:** se l'editor è già in esecuzione, il file apre solo il browser sull'istanza esistente.
- **Porta occupata:** se la 8000 è usata da un altro programma, mostra un avviso. Per cambiarla modifica `PORT` all'inizio del file.

## Generare il PDF da riga di comando

```bash
venv/bin/python genera_schede.py NOMI DATA_INIZIO [DATA_FINE] [-o file.pdf] [--json utenti.json]
```

| Parametro | Descrizione |
|---|---|
| `NOMI` | cognomi/nomi separati da virgola, senza distinzione di maiuscole e accenti, oppure `TUTTI`. Basta anche una parte del nome (`ros` trova `ROSSI MARIO`) |
| `DATA_INIZIO` | `gg/mm/aaaa` |
| `DATA_FINE` | `gg/mm/aaaa`, facoltativa (default: uguale all'inizio) |
| `-o` | file di output (default: `schede_terapia_AAAAMMGG[_AAAAMMGG].pdf`) |
| `--json` | file dati alternativo |

Esempi:

```bash
# tutti i pazienti, dal 22 al 24 settembre
venv/bin/python genera_schede.py TUTTI 22/09/2026 24/09/2026

# solo due pazienti, un giorno
venv/bin/python genera_schede.py "rossi, verdi" 22/09/2026
```

Il PDF è ordinato per giorno: per ogni giorno, per ogni paziente, fronte e retro (un foglio fronte/retro per paziente).

Le fasce **Mattino, Pranzo, Cena e Notte** vengono sempre stampate, anche vuote, da compilare a mano. Le fasce aggiuntive (per esempio `16:00`) vengono inserite nel punto corretto in base all'orario.

## Formato di `utenti.json`

Un elenco di pazienti. Vedi `utenti.json.template` per un esempio completo.

```json
{
  "paziente": "ROSSI MARIO",
  "serd_inviante": "Serd Esempio",
  "medico_serd": "Dott. Bianchi",
  "psichiatra_ct": null,
  "somministrazioni": [
    {
      "nome": "Mattino",
      "orario": null,
      "farmaci": [{ "farmaco": "Farmaco A 10 mg", "quantita": "1 cp" }]
    }
  ],
  "note": ["testo libero"],
  "al_bisogno": ["Farmaco D 600: 1 cp max 3v/dì se dolore"]
}
```

- `somministrazioni` ha lunghezza variabile: ogni voce è una fascia con `nome`, `orario` (`"hh:mm"` oppure `null`) e l'elenco dei farmaci.
- `psichiatra_ct` e gli altri campi di testo possono essere `null` o vuoti.
- `note` e `al_bisogno` sono elenchi di righe di testo, eventualmente vuoti.

## Struttura del progetto

```
genera_schede.py        generatore dei PDF (riga di comando)
editor.py               server locale: API per utenti.json e PDF
editor.html             interfaccia web dell'editor
avvia_editor.bat        avvio dell'editor su Windows
assets/logo.jpeg        logo stampato sulle schede
utenti.json.template    esempio di dati (inventati)
utenti.json             dati reali (ignorato da git)
backup/                 copie di sicurezza di utenti.json (contenuto ignorato da git)
requirements.txt        dipendenze Python
```

## Licenza

Questo programma è software libero, distribuito con licenza [GNU General Public License v3.0](LICENSE) o successiva.
