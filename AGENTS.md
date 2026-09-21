# AGENTS.md

Indicazioni per gli agenti di codifica (e per chi contribuisce) su questo repository.
Il progetto genera le schede terapia in PDF per Villa Silenzi e offre un editor web locale per i dati. Vedi `README.md` per l'uso.

## Panoramica

| File | Ruolo |
|---|---|
| `genera_schede.py` | generatore dei PDF (riga di comando e libreria, usata anche da `editor.py`) |
| `editor.py` | server locale (solo `127.0.0.1`): API su `utenti.json` e generazione PDF |
| `editor.html` | interfaccia dell'editor (un solo file, senza dipendenze esterne) |
| `assets/logo.jpeg` | logo stampato sulle schede |
| `utenti.json.template` | esempio con dati inventati |
| `utenti.json` | dati reali, **mai versionati** |
| `backup/` | copie di sicurezza di `utenti.json` (contenuto ignorato, resta solo `.gitkeep`) |

Dipendenze: solo `reportlab` (`requirements.txt`). Il resto è libreria standard.

## Comandi utili

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/python genera_schede.py rossi 22/09/2026 --json utenti.json.template -o /tmp/prova.pdf
venv/bin/python editor.py --no-browser --port 8765 --json /tmp/copia/utenti.json
python3 -m py_compile genera_schede.py editor.py
```

Non ci sono test automatici: si verifica generando un PDF dal template e guardandolo (per esempio con `pdftoppm -r 72 -png`).

## Privacy e dati (regole tassative)

- `utenti.json` contiene dati sanitari di persone reali. Non va mai committato, incollato in un messaggio di commit, in una issue o in un esempio.
- Negli esempi, nella documentazione, nei messaggi di commit e nei test usa **solo dati inventati** (come quelli in `utenti.json.template`: `ROSSI MARIO`, `VERDI ANNA`, `Farmaco A 10 mg`…). Mai nomi di pazienti, medici o SERD reali.
- Prova le funzioni che scrivono (salvataggi, backup, pulizie) su una **copia** dei dati (`--json /tmp/.../utenti.json`), non su `utenti.json`.
- `sorgenti/`, i PDF generati e i backup sono in `.gitignore`. Se un dato reale finisce in un commit già pubblicato, la cronologia va riscritta (chiedi prima conferma al proprietario: è un force-push).
- Il server dell'editor deve restare legato a `127.0.0.1` e continuare a rifiutare `Host` diversi da localhost.

## Convenzioni di codice

- Interfaccia, messaggi d'errore, commenti e documentazione in **italiano**; identificatori come già presenti nel codice.
- Ogni nuovo file sorgente (`.py`, `.html`) porta l'intestazione GPL-3.0-or-later già presente negli altri file (Copyright Matteo Iacono).
- Le misure del layout PDF sono costanti in `genera_schede.py` (`X0`, `X1`, `COLONNE`, `X_ORE`…): le colonne devono restare allineate tra fronte e retro. Se ne cambi una, ricontrolla entrambe le facciate.
- Nessuna dipendenza nuova senza necessità: se serve, aggiornala in `requirements.txt` e nel README.
- Aggiorna `README.md` quando cambia il comportamento visibile (parametri, formato di `utenti.json`, struttura delle cartelle).

## Conventional Commits

I messaggi di commit seguono [Conventional Commits 1.0](https://www.conventionalcommits.org/it/v1.0.0/):

```
<tipo>(<ambito facoltativo>): <descrizione>

[corpo facoltativo: cosa e perché, non il come]

[footer facoltativi, per esempio BREAKING CHANGE: ...]
```

- **Tipi**: `feat` (nuova funzionalità), `fix` (correzione di un difetto), `docs`, `style` (solo formattazione), `refactor`, `perf`, `test`, `build` (dipendenze, packaging), `ci`, `chore` (manutenzione varia).
- **Ambiti** usati qui: `pdf` (`genera_schede.py`), `editor` (`editor.py`, `editor.html`), `data` (template e formato dei dati), `docs`, `repo` (`.gitignore`, licenza, struttura). Sono facoltativi.
- **Descrizione**: in italiano, all'imperativo o all'infinito ("allinea…", "aggiunge…"), minuscola, senza punto finale, al massimo ~72 caratteri.
- **Breaking change**: `!` dopo tipo/ambito (`feat(data)!: …`) e/o footer `BREAKING CHANGE:`. Cambiare il formato di `utenti.json` in modo non retrocompatibile lo è.
- Esempi:
  - `fix(pdf): allinea l'header FARMACO agli altri header di colonna`
  - `feat(editor): salva i backup nella cartella backup/`
  - `docs: aggiunge AGENTS.md`
- I messaggi precedenti a questo file non seguono la convenzione: non vanno riscritti.

## Commit atomici

Un commit = **una sola modifica logica**, completa e coerente.

- Deve poter essere compreso, rivisto e annullato (`git revert`) da solo, e a ogni commit il programma deve ancora funzionare (`py_compile` e generazione di un PDF dal template).
- Non mescolare tipi diversi (una `fix` con un `refactor` o con `docs`), né modifiche a parti indipendenti.
- Se una modifica alla documentazione accompagna un cambio di comportamento, può stare nello stesso commit del cambio; una documentazione generale va a parte.
- Se in un file convivono più modifiche logiche, separale con `git add -p` (o applicando patch parziali con `git apply --cached`) e committa una alla volta.
- **Aggiungi i file per nome** (`git add percorso…`), mai `git add -A` o `git add .`: potresti includere dati reali, backup o cartelle estranee. Controlla sempre `git status` e `git diff --cached` prima di committare.
- Non committare file generati (PDF, `venv/`, `__pycache__/`, backup).

## Conventional Branching

Ogni modifica nasce su un branch dedicato e di breve durata, creato da `main` aggiornato. Nome:

```
<tipo>/<descrizione-breve-in-kebab-case>
```

- Lo `<tipo>` è lo stesso dei Conventional Commits: `feat/`, `fix/`, `docs/`, `refactor/`, `chore/`, `perf/`, `test/`, `build/`, `ci/`.
- Descrizione breve, minuscola, parole separate da `-`, senza spazi né maiuscole. Facoltativo il riferimento a una issue: `fix/12-allinea-tabelle`.
- Esempi: `feat/editor-genera-pdf`, `fix/pdf-table-alignment`, `docs/agents-md`, `chore/aggiorna-gitignore`.
- **Un branch = un obiettivo.** Più commit atomici dello stesso obiettivo possono stare sullo stesso branch; obiettivi diversi vanno su branch diversi.
- `main` è sempre in uno stato funzionante e con cronologia **lineare**: si integra con fast-forward (`git merge --ff-only`) o rebase, senza commit di merge. Dopo l'integrazione si cancella il branch.
- Non fare commit direttamente su `main`. Non riscrivere la cronologia di `main` senza esplicita autorizzazione del proprietario.
- Per il push: `git push origin <branch>` per pubblicare un branch da rivedere; `git push origin main` solo dopo l'integrazione. Con più persone coinvolte, passa da una pull request.
