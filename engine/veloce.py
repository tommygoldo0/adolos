"""
ADOLOS – controllo del giro veloce
==================================
Guarda su Notion solo le schede su cui una persona ha deciso (Approvata, Pubblicata, Scartata) e dice
se è cambiato qualcosa rispetto all'ultimo giro. Dura pochi secondi e non tocca il sito.

    python engine/veloce.py controlla              guarda una volta
    python engine/veloce.py controlla --attesa 9   resta di guardia 9 minuti, guardando ogni minuto

Risultato: scrive "cambiato=true" o "cambiato=false" per GitHub Actions (file $GITHUB_OUTPUT).
Se è cambiato qualcosa, il workflow lancia "python engine/adolos.py --veloce", che aggiorna sito e carosello.

Se Notion non risponde o mancano le chiavi, esce con errore: il workflow diventa rosso e il sito resta com'è.
Questo file non approva niente: legge soltanto. L'approvazione resta di una persona.
"""

import json
import os
import sys
import time
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
STATO = ENGINE / "veloce_stato.json"


PAUSA = 60            # secondi tra un controllo e l'altro quando si resta di guardia
MAX_ERRORI = 3        # letture di Notion fallite di fila prima di fermarsi con errore


def controlla(attesa_minuti=0):
    import redazione
    if not redazione.notion_attivo():
        print("ERRORE giro veloce: mancano NOTION_TOKEN o NOTION_DB_REDAZIONE nei Secrets")
        return 2
    try:
        vecchia = json.loads(STATO.read_text(encoding="utf-8")).get("impronta", "")
    except Exception:
        vecchia = ""                      # primo giro, o file mancante: si fa il giro
    fine = time.time() + attesa_minuti * 60
    cambiato, errori, controlli = False, 0, 0
    while True:
        try:                              # i clic su Telegram cambiano Notion: si leggono prima
            import telegram
            telegram.leggi_risposte()
        except Exception as e:
            print("Errore nella lettura dei clic di Telegram:", str(e)[:160], flush=True)
        dec = redazione.leggi_redazione(solo_decise=True)
        controlli += 1
        if dec.get("errore"):
            errori += 1
            print(f"ERRORE giro veloce: schede Notion non lette ({errori} di fila):", dec["errore"], flush=True)
            if errori >= MAX_ERRORI or time.time() >= fine:
                return 2
        else:
            errori = 0
            cambiato = redazione.impronta(dec) != vecchia
            if cambiato or time.time() >= fine:
                break
        time.sleep(PAUSA)
    print(f"Giro veloce: {controlli} controlli. {len(dec['si'])} schede approvate o pubblicate, {len(dec['no'])} scartate. "
          + ("Qualcosa è cambiato: aggiorno il sito." if cambiato else "Niente di nuovo."))
    uscita = os.environ.get("GITHUB_OUTPUT")
    if uscita:
        with open(uscita, "a", encoding="utf-8") as f:
            f.write(f"cambiato={'true' if cambiato else 'false'}\n")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["controlla"] and (len(args) == 1 or (len(args) == 3 and args[1] == "--attesa" and args[2].isdigit())):
        sys.exit(controlla(int(args[2]) if len(args) == 3 else 0))
    print("Uso: python engine/veloce.py controlla [--attesa MINUTI]")
    sys.exit(1)
