"""
ADOLOS – stile dei reel: UNO SOLO, predefinito ("adolos-reel-v2")
=================================================================
Tutto quello che decide l'aspetto di un reel sta qui: colori, caratteri, posizioni, durate, regole.
Colori e caratteri vengono da engine/social.py, gli stessi dei caroselli, così reel, caroselli e sito sembrano
della stessa testata. engine/reel_anim.py e engine/reel_globo.py devono usare SOLO questi valori:
`controlla()` legge i loro file e ferma la creazione del video se trova colori o caratteri scritti a mano.

Come è fatto un reel Adolos
  - Fondo nero caldo con la Terra di notte (foto NASA) e luci dorate. Niente fondi chiari, niente sfondi colorati.
  - In alto a sinistra il marchio (cerchio rosso con la α e ADOLOS); a destra la nota "Voce generata con AI".
  - Sotto il marchio un'etichetta ROSSA piena (argomento o "Secondo <testata>"), come sulle copertine dei caroselli.
  - Parole della voce a pezzi di 2-4 parole, in alto, in carattere sottile; la parola chiave in grassetto,
    i numeri in giallo. Mai in basso: lì Instagram mette nome utente e didascalia.
  - Al centro una sola cosa che si muove: globo 3D, mappa con il paese illuminato, contatore, linea del tempo,
    foto con licenza libera. Una scena nuova a ogni frase.
  - Numeri e dati di una sola testata: sotto c'è sempre "Secondo <testata>" (riga della fonte).
  - Chiusura: "Segui @adolos.it" in un riquadro giallo, fonti, nota sull'AI, crediti di foto e mappa.
  - Niente scena sulle testate ("24 testate da 15 paesi"): per scelta. Le fonti si citano comunque (regola legale).
  - Mai: volti di persone create con AI, foto di giornali, bandiere finte, scritte fuori dalla zona sicura.
Copiamo il formato (scene brevi, testo in alto, mappe luminose), mai i personaggi o i testi di altri account.
"""

import re
from pathlib import Path

import social

NOME = "adolos-reel-v2"

# ---------------------------------------------------------------- colori (gli stessi di social.py)
NERO = social.NERO_CALDO
ROSSO = social.ROSSO
GIALLO = social.GIALLO
GRIGIO = social.GRIGIO_CHIARO
BIANCO = (255, 255, 255)
CELLA = (26, 16, 17)               # riquadri scuri (testate, etichette sulla mappa)
LINEA = (88, 78, 78)               # linee deboli (linea del tempo)
TRASPARENTE = (0, 0, 0, 0)
OMBRA = (0, 0, 0, 175)             # ombra sotto le scritte sottili

# ---------------------------------------------------------------- caratteri (Archivo, come il sito; pesi da 100 a 900)
PESO_SOTTILE, PESO_MEDIO, PESO_FORTE, PESO_TITOLO = 300, 600, 800, 900

# ---------------------------------------------------------------- misure (video 1080 x 1920)
LARGHEZZA, ALTEZZA, FPS = 1080, 1920, 30
MARGINE = 72
Y_MARCHIO = 104
Y_ETICHETTA = 236
Y_DIDASCALIA = 340                 # le parole della voce, in alto
DIM_DIDASCALIA = 80
Y_CENTRO = 1000                    # centro della scena (il globo è qui)
Y_NUMERO = 1130                    # contatori e linea del tempo
Y_FONTE = 1440                     # riga "Secondo <testata>"
Y_SICURO = 1500                    # sotto questa riga niente: coperta dall'interfaccia di Instagram e TikTok
RIQUADRO_FOTO = (110, 520, 970, 1260)

# ---------------------------------------------------------------- tempi
CHIUSURA_S = 2.8
PAUSA_S = 0.22
STACCO_S = 0.12
PAROLE_PER_PEZZO = 3
MAX_SCENE = 12                     # circa un minuto di voce
SCENA_TESTATE = False              # niente scena "chi ne parla" nei reel (scelta di Tommaso, 16 novembre 2026); le fonti restano in chiusura e sotto i dati
GLOBO_FPS = 30
GLOBO_CAMPIONI = 8                 # qualità di Blender: 8 basta per un video che scorre

# ---------------------------------------------------------------- regole (si leggono anche nella skill adolos-stile)
NOTA_AI = "Testo preparato con l'aiuto dell'AI e verificato dalla redazione. Voce generata con AI."
SCRITTA_VOCE = "Voce generata con AI"
CODA = "@ADOLOS.IT"

FILE_DA_CONTROLLARE = ("reel_anim.py", "reel_globo.py")
_RE_COLORE = re.compile(r"\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*(?:,\s*\d{1,3}\s*)?\)")
_RE_FONT = re.compile(r"\.(?:ttf|otf|woff2?)\b|\b(?:Archivo|Instrument|Newsreader|Lora|DejaVu)\b", re.I)
_AMMESSI = (re.compile(r"^\s*#"),)               # i commenti non contano


def controlla():
    """Ferma tutto se un file del reel ha colori scritti a mano (tuple tipo (255, 212, 0)) o nomi di caratteri."""
    qui = Path(__file__).resolve().parent
    problemi = []
    for nome in FILE_DA_CONTROLLARE:
        f = qui / nome
        if not f.exists():
            continue
        for n, riga in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if any(a.search(riga) for a in _AMMESSI):
                continue
            if _RE_COLORE.search(riga) or _RE_FONT.search(riga):
                problemi.append(f"{nome}:{n}: {riga.strip()[:90]}")
    if problemi:
        raise SystemExit("STILE ADOLOS: colori o caratteri fuori da engine/stile_reel.py:\n  " + "\n  ".join(problemi[:12]))
    return True


if __name__ == "__main__":
    controlla()
    print(f"Stile {NOME}: controllo superato")
