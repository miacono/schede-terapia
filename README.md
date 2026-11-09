# Schede terapia

Strumenti per gestire e stampare le **schede terapia** del Servizio Residenziale Villa Silenzi.

Le schede sono descritte in un unico file, `data/utenti.json`. Da lì si può:

- **modificare** i dati con un editor web locale, senza conoscere la sintassi JSON;
- **generare il PDF** delle schede, un foglio fronte/retro per utente e per giorno.

Ogni scheda ha due facciate:

| Facciata | Contenuto |
|---|---|
| Fronte | logo e titolo, utente e data, somministrazioni (Mattino, Pranzo, Cena, Notte ed eventuali altre fasce), SERD inviante, medico SERD, psichiatra CT, note |
| Retro | logo e titolo, utente e data, terapia al bisogno, tabella di somministrazione della terapia al bisogno |

> ⚠️ **Privacy.** `data/utenti.json` contiene dati sanitari di persone reali. Tutta la cartella `data/` (tranne il template) è esclusa dal repository tramite `.gitignore`, insieme ai PDF generati. Non committarli mai.

## Requisiti

- Python 3.9+
- [reportlab](https://pypi.org/project/reportlab/)

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Su Windows (prompt dei comandi) i comandi di questo file usano `venv\Scripts\python.exe` al posto di `venv/bin/python`:

```bat
py -3 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe src\genera_schede.py TUTTI 22/09/2026
```

## Primi passi

Il repository contiene solo `data/utenti.json.template`, con dati inventati. Al primo avvio l'editor lo copia in `data/utenti.json`, che poi si modifica con l'editor (vedi sotto) o a mano. Per usare solo la riga di comando, copialo a mano:

```bash
cp data/utenti.json.template data/utenti.json
```

### Aggiornamento dalla versione con i dati nella cartella principale

Fino alla versione precedente `utenti.json` e `backup/` stavano nella cartella principale. All'avvio l'editor li sposta da solo in `data/`, **senza mai sovrascrivere** un file già presente:

- se `data/utenti.json` esiste già, il vecchio `utenti.json` non viene toccato e compare un avviso: va controllato ed eliminato a mano;
- un vecchio backup con lo stesso nome di uno già presente in `data/backup/` resta dov'è, con un avviso;
- se lo spostamento non riesce, l'editor si ferma senza toccare niente.

## Editor web locale

```bash
venv/bin/python src/editor.py
```

Si apre il browser su `http://127.0.0.1:8000`. Opzioni: `--port 8080`, `--no-browser`, `--json altro_file.json`.

L'editor ha tre schede: **Utenti** e **Farmaci** (da `utenti.json`) e **Sostitutivi** (da `sostitutivi.json`, nella stessa cartella di `utenti.json`; se non esiste ancora si parte da un elenco vuoto). In alto ci sono anche i pulsanti per **salvare** le modifiche e per **uscire** (*Esci* spegne il server).

Dalla scheda *Utenti* si può:

- cercare, aggiungere ed eliminare utenti (eliminando un utente si elimina anche la sua scheda farmaci);
- modificare cognome e nome, SERD inviante, medico SERD e psichiatra;
- passare alla scheda farmaci o alle schede sostitutivi dell'utente.

Dalla scheda *Farmaci* si può:

- scegliere l'utente dall'elenco a sinistra (con la ricerca) o dal menu a tendina; l'utente scelto resta lo stesso anche nella scheda *Utenti*;
- aggiungere, togliere e riordinare fasce, farmaci, note e righe "al bisogno";
- **generare il PDF** scegliendo utenti e date (include anche le modifiche non ancora salvate).

Dalla scheda *Sostitutivi* si può:

- creare, cercare ed eliminare schede sostitutivi, scegliendo l'utente da un menu a tendina;
- indicare farmaco, quantità iniziale, unità di misura e data di inizio: la fine (il martedì) si calcola da sola;
- modificare gli orari (predefiniti 08.30, 13.00, 18.00, 23.00; si possono scrivere anche col punto) e la quantità standard di ciascuno;
- cambiare la quantità di un singolo giorno nella tabella *giorno per giorno*, che mostra totale e saldo di ogni giorno e avvisa se la quantità iniziale non basta o avanza;
- creare con un clic la scheda della **settimana successiva**, con gli stessi orari e quantità;
- **generare il PDF** delle schede scelte.

Gli utenti si aggiungono solo dalla scheda *Utenti*. Rinominando un utente si aggiornano anche le sue schede sostitutivi; non lo si può eliminare finché ne ha. Il pulsante *Salva modifiche* salva tutti e due i file, ciascuno con il suo backup, e rifiuta schede sostitutivi di utenti che non ci sono nell'elenco utenti.

Ad ogni salvataggio il file corrente (`utenti.json` o `sostitutivi.json`) viene copiato nella cartella `backup/` accanto al file dei dati (quindi `data/backup/`) come `utenti_AAAA-MM-GGTHH-MM-SS.json.bak` o `sostitutivi_AAAA-MM-GGTHH-MM-SS.json.bak` (per esempio `data/backup/utenti_2026-09-26T18-08-22.json.bak`); la cartella viene creata se manca. I backup più vecchi di 1 anno vengono eliminati automaticamente (costante `GIORNI_BACKUP` in `src/editor.py`).

Il server ascolta **solo su `127.0.0.1`** e rifiuta richieste con un `Host` diverso da localhost: i dati non escono dal computer.

### Avvio su Windows

Su Windows si usa `avvia_editor.bat` (doppio clic, oppure un collegamento sul desktop con la sua icona). Serve Python 3.9 o successivo installato (con il *py launcher* oppure `python` nel PATH).

- **Primo avvio:** crea `venv` e installa le dipendenze (serve internet); l'editor crea `data/utenti.json` dal template.
- **Avvio normale:** lancia l'editor **senza finestra console** e apre il browser su `http://127.0.0.1:8000`.
- **Chiusura:** con il pulsante **Esci** nella pagina. Chiudere solo la scheda del browser *non* ferma il server.
- **Già acceso:** se l'editor è già in esecuzione, si apre solo il browser sull'istanza esistente.
- **Porta occupata:** se la 8000 è usata da un altro programma, compare un avviso. Per cambiarla modifica `PORT` all'inizio del file.

## Generare il PDF da riga di comando

```bash
venv/bin/python src/genera_schede.py NOMI DATA_INIZIO [DATA_FINE] [-o file.pdf] [--json data/utenti.json]
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
# tutti gli utenti, dal 22 al 24 settembre
venv/bin/python src/genera_schede.py TUTTI 22/09/2026 24/09/2026

# solo due utenti, un giorno
venv/bin/python src/genera_schede.py "rossi, verdi" 22/09/2026
```

Il PDF è ordinato per giorno: per ogni giorno, per ogni utente, fronte e retro (un foglio fronte/retro per utente).

Le fasce **Mattino, Pranzo, Cena e Notte** vengono sempre stampate, anche vuote, da compilare a mano. Le fasce aggiuntive (per esempio `16:00`) vengono inserite nel punto corretto in base all'orario.

## Schede sostitutivi

Oltre alle schede terapia, il programma gestisce le **schede sostitutivi**: il foglio firme di un farmaco sostitutivo consegnato in quantità fissa, con il saldo che scala a ogni somministrazione. I dati stanno in un file separato, `data/sostitutivi.json` (esempio: `data/sostitutivi.json.template`).

Per ogni scheda si indicano utente, farmaco, unità di misura, quantità iniziale, data di inizio e gli **orari** con la quantità di ciascuno (predefiniti 08:30, 13:00, 18:00 e 23:00, modificabili). La scheda **finisce sempre di martedì**: va dalla data di inizio al primo martedì (compreso; se l'inizio è di martedì, la scheda dura un giorno). Per ogni giorno si può cambiare la quantità di un orario (*variazioni*), senza toccare gli altri giorni.

Il PDF ha una pagina per scheda (di più solo se gli orari sono molti): per ogni giorno e orario la quantità (`--` se nulla), lo spazio per la firma dell'operatore e dell'utente e il saldo rimasto. Un saldo negativo, cioè una quantità iniziale che non basta, è stampato in grassetto.

```bash
venv/bin/python src/genera_sostitutivi.py NOMI [-o file.pdf] [--json data/sostitutivi.json]
```

`NOMI` funziona come per le schede terapia (`TUTTI`, oppure parti di nomi separate da virgola). Il file predefinito è `schede_sostitutivi_AAAAMMGG.pdf`, con la data di inizio più vecchia tra le schede scelte.

## Formato di `utenti.json`

Un elenco di utenti. Vedi `data/utenti.json.template` per un esempio completo.

> Fino alla versione precedente la chiave `utente` (in `utenti.json` e in `sostitutivi.json`) si chiamava `paziente`. I file nel vecchio formato si leggono ancora: l'editor li riscrive con il nuovo nome al primo salvataggio.

```json
{
  "utente": "ROSSI MARIO",
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

## Formato di `sostitutivi.json`

Un elenco di schede sostitutivi:

```json
{
  "utente": "VERDI ANNA",
  "farmaco": "Sostitutivo B sciroppo",
  "unita": "ml",
  "quantita_iniziale": 60,
  "data_inizio": "2026-11-12",
  "orari": [
    { "orario": "08:30", "quantita": 5 },
    { "orario": "18:00", "quantita": 2.5 }
  ],
  "variazioni": { "2026-11-14": { "08:30": 7.5 } }
}
```

- `data_inizio` è in formato `aaaa-mm-gg`; la fine (il primo martedì) si calcola da sola.
- Le quantità sono numeri (anche decimali, con il punto), espressi nell'`unita` indicata (default `mg`).
- `variazioni` associa a un giorno le quantità diverse da quella standard, per orario. Le variazioni fuori dal periodo o uguali alla quantità standard vengono tolte al salvataggio.
- `utente` deve coincidere con il nome di un utente di `utenti.json` (l'editor lo controlla al salvataggio).
- Lo stesso utente può avere più schede (farmaci o settimane diverse).

## Struttura del progetto

```
avvia_editor.bat        avvio dell'editor su Windows
src/                    il programma:
  genera_schede.py        generatore dei PDF (riga di comando)
  genera_sostitutivi.py   generatore dei PDF delle schede sostitutivi
  editor.py               server locale: API per utenti.json e PDF
  editor.html             interfaccia web dell'editor
  assets/logo.jpeg        logo stampato sulle schede
data/                   i dati (ignorati da git, tranne il template):
  utenti.json.template    esempio di dati (inventati)
  utenti.json             dati reali
  sostitutivi.json.template  esempio di schede sostitutivi (inventate)
  sostitutivi.json        schede sostitutivi reali
  backup/                 copie di sicurezza di utenti.json e sostitutivi.json
requirements.txt        dipendenze Python
```

## Licenza

Questo programma è software libero, distribuito con licenza [GNU General Public License v3.0](LICENSE) o successiva.
