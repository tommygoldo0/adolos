"""
ADOLOS – sintesi multi-fonte (bozza per la redazione)
=====================================================
Regole (vedi LEGGIMI, "Le regole legali"):
- si parte SOLO da titoli e brevi descrizioni dei feed RSS ufficiali, mai dagli articoli interi;
- servono almeno 2 testate diverse sullo stesso fatto;
- l'AI estrae i fatti (chi, cosa, dove, quando, perché) e scrive un testo nuovo in italiano;
- un controllo automatico scarta i testi che ripetono frasi delle fonti (anti-copia);
- il risultato è una BOZZA: va su Notion e sul sito compare solo dopo che una persona l'ha
  controllata e messo lo Stato su "Approvata" (così vale anche per l'AI Act: revisione umana).

Le bozze restano in engine/cache/sintesi.json, che NON è pubblico (non va nel sito).
"""

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import ai

ENGINE = Path(__file__).resolve().parent
CACHE = ENGINE / "cache" / "sintesi.json"
N_PAROLE_COPIA = 6          # 6 parole di fila uguali a una fonte = frase copiata
GIORNI = 5

SISTEMA = """Sei la redazione di Adolos, un sito italiano di notizie. Ricevi i titoli e le brevi descrizioni
con cui più testate diverse raccontano lo stesso fatto. Devi scrivere una sintesi NUOVA in italiano.

Regole obbligatorie:
1. Usa solo fatti presenti nelle fonti. Non aggiungere nulla che non c'è, niente supposizioni.
2. Non copiare e non tradurre parola per parola frasi delle fonti: estrai i fatti e riscrivili con parole tue.
3. Se un'informazione la dà una sola fonte, attribuiscila: "secondo <testata>".
4. Se le fonti non concordano, dillo in modo neutro.
5. Tono neutro, frasi brevi, niente aggettivi d'effetto, niente opinioni, niente punti esclamativi.
6. Persone accusate di reati: usa "accusato", "indagato", "secondo la polizia". Mai dare per certa la colpa.
   Non scrivere nomi di minorenni né di vittime di violenza.
7. Numeri e date esattamente come nelle fonti.

Rispondi SOLO con questo JSON:
{"titolo": "titolo nuovo, massimo 90 caratteri",
 "sintesi": "60-110 parole",
 "fatti": {"chi": "", "cosa": "", "dove": "", "quando": "", "perche": ""},
 "punti": ["3 o 4 frasi brevi per un carosello Instagram, massimo 120 caratteri ciascuna"],
 "versioni_diverse": "una frase se le fonti non concordano, altrimenti stringa vuota",
 "persone_accusate": true o false}"""


# ---------------------------------------------------------------- utilità
def _norm(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", t)


def _sequenze(parole, n=N_PAROLE_COPIA):
    return {" ".join(parole[i:i + n]) for i in range(max(0, len(parole) - n + 1))}


def frasi_copiate(testo, fonti_testi):
    """Restituisce le sequenze di N parole che il testo ha in comune con le fonti."""
    nostre = _sequenze(_norm(testo))
    loro = set()
    for t in fonti_testi:
        loro |= _sequenze(_norm(t))
    return sorted(nostre & loro)


def _leggi():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _scrivi(dati):
    limite = datetime.now(timezone.utc).timestamp() - GIORNI * 86400
    dati = {k: v for k, v in dati.items() if v.get("ts", 0) >= limite}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")


def bozze():
    return _leggi()


def _materiale(s, gruppo):
    """Titoli e descrizioni RSS delle testate (non social), una riga per testata, massimo 6."""
    righe, testi, viste = [], [], set()
    for x in sorted(gruppo, key=lambda x: x["data"]):
        if x.get("tipo") == "social" or x.get("correlato") or x.get("uso") == "conta_e_link":
            continue
        k = x["fonte"].lower()
        if k in viste:
            continue
        viste.add(k)
        desc = (x.get("riassunto") or "")[:400]
        righe.append(f"- {x['fonte']} ({x['paese']}), {x['data'][:16].replace('T', ' ')} UTC\n"
                     f"  Titolo: {x['titolo']}" + (f"\n  Titolo in italiano: {x['titolo_it']}" if x.get("titolo_it")
                                                     and x["titolo_it"] != x["titolo"] else "")
                     + (f"\n  Descrizione: {desc}" if desc else ""))
        testi += [x["titolo"], x.get("titolo_it") or "", desc]
        if len(righe) >= 6:
            break
    return righe, testi


def candidata(s):
    """Si scrive la bozza solo per notizie confermate da almeno 2 testate e proposte per Instagram
    (o approvate a mano dalla redazione)."""
    testate = sum(1 for f in s["fonti"] if f.get("tipo") != "social")
    return testate >= 2 and (s.get("bot") in ("post", "storia") or s.get("approvata_a_mano"))


def firma(s):
    return hashlib.sha1("|".join(sorted(f["fonte"] for f in s["fonti"][:6])).encode()).hexdigest()[:10]


# ---------------------------------------------------------------- principale
def prepara(storie, gruppi, max_al_giro=8):
    """Scrive le bozze che mancano. 'gruppi' = {id storia: articoli del gruppo}."""
    dati = _leggi()
    if not ai.attiva():
        print("Sintesi: AI non configurata, la redazione può scriverle a mano su Notion")
        return dati
    fatte = 0
    for s in storie:
        if fatte >= max_al_giro:
            break
        if not candidata(s) or s["id"] in dati:
            continue
        righe, testi_fonti = _materiale(s, gruppi.get(s["id"], []))
        if len(righe) < 2:
            continue
        richiesta = "Fonti sullo stesso fatto:\n" + "\n".join(righe)
        bozza, avviso = None, ""
        for tentativo in range(2):
            try:
                risposta = ai.chiedi(SISTEMA, richiesta + avviso, max_token=900)
                b = ai.json_da(risposta)
            except ai.TettoRaggiunto:
                print("Sintesi: tetto di spesa mensile raggiunto")
                _scrivi(dati)
                return dati
            except Exception as e:
                print("Sintesi non riuscita:", str(e)[:120])
                break
            tutto = " ".join([b.get("titolo", ""), b.get("sintesi", "")] + list(b.get("punti", [])))
            copiate = frasi_copiate(tutto, testi_fonti)
            if not copiate:
                bozza = b
                break
            avviso = ("\n\nATTENZIONE: la versione precedente ripeteva queste frasi delle fonti, riscrivile con parole "
                      "diverse: " + "; ".join(copiate[:6]))
        fatte += 1
        if not bozza:
            dati[s["id"]] = {"ts": datetime.now(timezone.utc).timestamp(), "scartata": "frasi copiate dalle fonti"}
            continue
        punti = [str(p).strip() for p in bozza.get("punti", []) if str(p).strip()][:4]
        dati[s["id"]] = {
            "ts": datetime.now(timezone.utc).timestamp(),
            "firma": firma(s),
            "titolo": str(bozza.get("titolo", "")).strip()[:120],
            "sintesi": str(bozza.get("sintesi", "")).strip(),
            "fatti": {k: str(v).strip() for k, v in (bozza.get("fatti") or {}).items()},
            "punti": punti,
            "versioni_diverse": str(bozza.get("versioni_diverse", "")).strip(),
            "persone_accusate": bool(bozza.get("persone_accusate")),
            "fonti_usate": [r.split("(")[0].strip("- ").strip() for r in righe],
        }
    _scrivi(dati)
    spesa = ai.spesa_mese()
    print(f"Sintesi: {fatte} bozze nuove. Spesa AI del mese: {spesa['costo_usd']:.2f} $ ({spesa['chiamate']} richieste)")
    return dati
