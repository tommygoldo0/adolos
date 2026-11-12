"""
ADOLOS – controllo del giro veloce
==================================
Guarda su Notion solo le schede su cui una persona ha deciso (Approvata, Pubblicata, Scartata) e dice
se è cambiato qualcosa rispetto all'ultimo giro. Dura pochi secondi e non tocca il sito.

    python engine/veloce.py controlla

Risultato: scrive "cambiato=true" o "cambiato=false" per GitHub Actions (file $GITHUB_OUTPUT).
Se è cambiato qualcosa, il workflow lancia "python engine/adolos.py --veloce", che aggiorna sito e carosello.

Se Notion non risponde o mancano le chiavi, esce con errore: il workflow diventa rosso e il sito resta com'è.
Questo file non approva niente: legge soltanto. L'approvazione resta di una persona.
"""

import json
import os
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
STATO = ENGINE / "veloce_stato.json"


def controlla():
    import redazione
    if not redazione.notion_attivo():
        print("ERRORE giro veloce: mancano NOTION_TOKEN o NOTION_DB_REDAZIONE nei Secrets")
        return 2
    dec = redazione.leggi_redazione(solo_decise=True)
    if dec.get("errore"):
        print("ERRORE giro veloce: schede Notion non lette:", dec["errore"])
        return 2
    nuova = redazione.impronta(dec)
    try:
        vecchia = json.loads(STATO.read_text(encoding="utf-8")).get("impronta", "")
    except Exception:
        vecchia = ""                      # primo giro, o file mancante: si fa il giro
    cambiato = nuova != vecchia
    print(f"Giro veloce: {len(dec['si'])} schede approvate o pubblicate, {len(dec['no'])} scartate. "
          + ("Qualcosa è cambiato: aggiorno il sito." if cambiato else "Niente di nuovo."))
    uscita = os.environ.get("GITHUB_OUTPUT")
    if uscita:
        with open(uscita, "a", encoding="utf-8") as f:
            f.write(f"cambiato={'true' if cambiato else 'false'}\n")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["controlla"]:
        sys.exit(controlla())
    print("Uso: python engine/veloce.py controlla")
    sys.exit(1)
