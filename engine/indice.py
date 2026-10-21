"""
ADOLOS – indice di viralità (0-100) e zona di rischio
=====================================================
Serve a ORDINARE la coda di approvazione su Notion: il tuo amico guarda prima le notizie
con più probabilità di funzionare. Non decide da solo cosa pubblicare.

Come si calcola
  1. Parte dai dati (sempre, gratis): quante testate e paesi ne parlano, quanto velocemente
     cresce, quanto è fresca, quanto è confermata, che argomento è.
  2. Se l'AI è attiva e c'è una bozza, aggiunge un voto sul testo: gancio, interesse,
     condivisibilità ("la manderei a un amico?"), chiarezza. Propone anche 3 ganci alternativi.
  3. Dopo la pubblicazione legge i risultati veri da Instagram (copertura, salvataggi,
     condivisioni) e una volta a settimana aggiusta i pesi per argomento (calibra).

Zona
  - "Rossa": nomi in cronaca, persone accusate, notizia non ancora confermata. Controllo attento.
  - "Verde": tutto il resto. Controllo veloce.
  Il punteggio NON compensa il rischio: una notizia rossa da 95 va controllata come una da 10.

File privati (non vanno sul sito): engine/cache/indice.json, pesi_indice.json, risultati.json
"""

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
CACHE = ENGINE / "cache"
F_INDICE = CACHE / "indice.json"
F_PESI = CACHE / "pesi_indice.json"
F_RISULTATI = CACHE / "risultati.json"
F_IG = CACHE / "instagram.json"

# quanto un argomento tende a essere condiviso (punto di partenza, poi lo corregge calibra())
PESI_SEZIONE = {"Curiosità": 1.0, "Sport": 0.9, "Tecnologia": 0.85, "Italia": 0.85, "Società": 0.8,
                "Mondo": 0.75, "Economia": 0.7, "Politica": 0.6}
PESO_BASE = 0.7
MIN_RISULTATI_PER_CALIBRARE = 20
GIORNI_TRA_CALIBRAZIONI = 7
ORE_PRIMA_DI_MISURARE = 48          # Instagram dà i dati con fino a 48 ore di ritardo

SISTEMA = """Sei l'editor social di Adolos, una pagina italiana di notizie verificate.
Valuta una bozza di carosello Instagram. Sii severo e onesto: la media deve stare intorno a 5.

Voti da 0 a 10:
- gancio: la prima slide (titolo) si capisce in un secondo e fa venire voglia di sfogliare?
- interesse: riguarda molte persone in Italia, sorprende, risponde a una domanda che la gente si fa?
- condivisibilita: qualcuno la manderebbe a un amico o la salverebbe?
- chiarezza: è facile da capire senza conoscere già la notizia?

Poi scrivi 3 titoli alternativi per la copertina (massimo 70 caratteri), più forti ma ONESTI:
non devono dire nulla che la sintesi non dice, niente esagerazioni, niente punti esclamativi,
niente "non ci crederai", niente colpe date per certe.

Rispondi SOLO con questo JSON:
{"gancio": 0, "interesse": 0, "condivisibilita": 0, "chiarezza": 0,
 "motivo": "una frase sul punto forte e una sul punto debole",
 "ganci": ["", "", ""]}"""


# ---------------------------------------------------------------- utilità
def _leggi(f, vuoto):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return vuoto


def _scrivi(f, dati):
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")


def _conf():
    return _leggi(ENGINE / "fonti.json", {}).get("indice", {})


def pesi():
    p = dict(PESI_SEZIONE)
    p.update(_leggi(F_PESI, {}).get("sezioni", {}))
    return p


def zona(s, bozza=None):
    motivi = []
    if s.get("controllo"):
        motivi.append("nomi in cronaca o reati")
    if s.get("categoria") == "Cronaca":
        motivi.append("cronaca")
    if s.get("stato") != "confermato":
        motivi.append("non ancora confermata")
    if bozza and bozza.get("persone_accusate"):
        motivi.append("persone accusate")
    return ("Rossa" if motivi else "Verde"), motivi


# ---------------------------------------------------------------- punteggio dai dati
def punteggio_dati(s, p=None):
    """0-100 solo dai numeri che il motore ha già. Restituisce (punteggio, motivi principali)."""
    p = p or pesi()
    m = s.get("motivi", {})
    n = max(1, s.get("n_fonti", 1))
    parti = {
        "copertura": 25 * min(1.0, math.log(n) / math.log(40)),
        "paesi": 15 * min(1.0, len(s.get("paesi", [])) / 10),
        "velocita": 15 * min(1.0, (m.get("ultime_3_ore") or 0) / 10),
        "freschezza": 10 * max(0.0, 1 - max(0.0, (m.get("ore_dall_ultimo_aggiornamento") or 0) - 2) / 22),
        "argomento": 15 * p.get(s.get("sezione"), PESO_BASE),
        "conferma": 10 * min(1.0, (s.get("attendibilita") or 0) / 100),
    }
    totale = round(sum(parti.values()) * 100 / 90)
    if s.get("punto_cieco") == "italia":       # "il mondo ne parla, l'Italia no": angolo che ha solo Adolos
        totale += 8
    testi = {
        "copertura": f"ne parlano {n} testate",
        "paesi": f"{len(s.get('paesi', []))} paesi",
        "velocita": f"{m.get('ultime_3_ore') or 0} articoli nelle ultime 3 ore",
        "freschezza": "notizia fresca",
        "argomento": f"argomento {s.get('sezione', '')} di solito condiviso",
        "conferma": "ben confermata",
    }
    # i due pezzi che pesano di più rispetto al loro massimo
    massimi = {"copertura": 25, "paesi": 15, "velocita": 15, "freschezza": 10, "argomento": 15, "conferma": 10}
    migliori = sorted(parti, key=lambda k: parti[k] / massimi[k], reverse=True)[:2]
    motivi = [testi[k] for k in migliori]
    if s.get("punto_cieco") == "italia":
        motivi.insert(0, "il mondo ne parla, in Italia quasi nessuno (punto cieco)")
    return max(0, min(100, totale)), motivi


# ---------------------------------------------------------------- voto AI sul testo
def voto_ai(s, bozza):
    import ai
    testo = (f"Sezione: {s.get('sezione')}\nTitolo: {bozza.get('titolo')}\nSintesi: {bozza.get('sintesi')}\n"
             f"Punti del carosello:\n- " + "\n- ".join(bozza.get("punti", [])))
    v = ai.json_da(ai.chiedi(SISTEMA, testo, max_token=400))
    voti = [max(0, min(10, float(v.get(k, 0)))) for k in ("gancio", "interesse", "condivisibilita", "chiarezza")]
    # la condivisibilità conta il doppio: gli invii in DM sono tra i segnali più forti
    media = (voti[0] + voti[1] + 2 * voti[2] + voti[3]) / 5
    ganci = [str(g).strip()[:90] for g in (v.get("ganci") or []) if str(g).strip()][:3]
    return round(media * 10), str(v.get("motivo", "")).strip()[:300], ganci


# ---------------------------------------------------------------- principale
def calcola(storie, bozze=None):
    """Restituisce {id storia: {indice, zona, perche, ganci, dati, ai}} (dati privati per Notion)."""
    bozze = bozze or {}
    cache = _leggi(F_INDICE, {})
    conf = _conf()
    p = pesi()
    usa_ai = conf.get("ai", True)
    max_ai = int(conf.get("max_ai_al_giro", 10))
    try:
        import ai
        ai_on = usa_ai and ai.attiva()
    except Exception:
        ai_on = False
    fatte_ai = 0
    out = {}
    for s in storie:
        b = bozze.get(s["id"]) or {}
        dati, motivi = punteggio_dati(s, p)
        z, motivi_z = zona(s, b)
        voce = cache.get(s["id"], {})
        firma = (b.get("titolo", ""), b.get("sintesi", ""))
        if ai_on and b.get("sintesi") and voce.get("firma") != list(firma) and fatte_ai < max_ai:
            try:
                v, motivo, ganci = voto_ai(s, b)
                voce = {"firma": list(firma), "ai": v, "motivo": motivo, "ganci": ganci,
                        "ts": datetime.now(timezone.utc).timestamp()}
                cache[s["id"]] = voce
                fatte_ai += 1
            except Exception as e:
                print("Indice: voto AI non riuscito:", str(e)[:120])
        v_ai = voce.get("ai") if voce.get("firma") == list(firma) else None
        finale = round(0.6 * dati + 0.4 * v_ai) if v_ai is not None else dati
        perche = "Dati: " + ", ".join(motivi) + "."
        if v_ai is not None and voce.get("motivo"):
            perche += f" Testo ({v_ai}/100): {voce['motivo']}"
        if motivi_z:
            perche += " Zona rossa: " + ", ".join(motivi_z) + "."
        out[s["id"]] = {"indice": finale, "zona": z, "perche": perche, "dati": dati, "ai": v_ai,
                        "ganci": voce.get("ganci", []) if v_ai is not None else []}
    # pulizia: tieni solo le storie degli ultimi giorni
    limite = datetime.now(timezone.utc).timestamp() - 5 * 86400
    _scrivi(F_INDICE, {k: v for k, v in cache.items() if v.get("ts", 0) >= limite})
    if out:
        verdi = sum(1 for v in out.values() if v["zona"] == "Verde")
        print(f"Indice: {len(out)} notizie valutate ({verdi} verdi), {fatte_ai} voti AI nuovi")
    return out


# ---------------------------------------------------------------- imparare dai risultati
def registra_pubblicazione(sid, media_id, s, info):
    """Chiamata da social.py subito dopo una pubblicazione."""
    r = _leggi(F_RISULTATI, {})
    r[sid] = {"media": media_id, "pubblicato": datetime.now(timezone.utc).timestamp(),
              "sezione": s.get("sezione"), "zona": (info or {}).get("zona"),
              "indice": (info or {}).get("indice"), "misurato": False}
    _scrivi(F_RISULTATI, r)


def raccogli_risultati():
    """Dopo 48 ore legge da Instagram copertura, salvataggi, condivisioni e interazioni."""
    if not (os.environ.get("IG_TOKEN") and os.environ.get("IG_USER_ID")):
        return 0
    import social
    r = _leggi(F_RISULTATI, {})
    adesso = datetime.now(timezone.utc).timestamp()
    fatti = 0
    for sid, v in r.items():
        if v.get("misurato") or not v.get("media") or adesso - v["pubblicato"] < ORE_PRIMA_DI_MISURARE * 3600:
            continue
        try:
            dati = social._ig("GET", f"{v['media']}/insights", metric="reach,saved,shares,likes,comments,total_interactions")
            for m in dati.get("data", []):
                valori = m.get("values") or [{}]
                v[m["name"]] = (m.get("total_value") or {}).get("value", valori[0].get("value", 0)) or 0
            v["misurato"] = True
            fatti += 1
        except Exception as e:
            print("Risultati Instagram non letti:", sid, str(e)[:120])
            break
    _scrivi(F_RISULTATI, r)
    if fatti:
        print(f"Indice: risultati letti per {fatti} post")
    return fatti


def _qualita(v):
    """Quanto un post ha funzionato: (condivisioni*2 + salvataggi) per 100 persone raggiunte."""
    reach = v.get("reach") or 0
    if reach < 50:
        return None
    return (2 * (v.get("shares") or 0) + (v.get("saved") or 0)) * 100 / reach


def calibra(forza=False):
    """Una volta a settimana: gli argomenti che funzionano meglio pesano di più, gli altri meno.
    Cambi piccoli (al massimo ±15% a settimana), così un post fortunato non sballa tutto."""
    stato = _leggi(F_PESI, {})
    adesso = datetime.now(timezone.utc).timestamp()
    if not forza and adesso - stato.get("ultima", 0) < GIORNI_TRA_CALIBRAZIONI * 86400:
        return None
    misurati = [v for v in _leggi(F_RISULTATI, {}).values() if v.get("misurato") and _qualita(v) is not None]
    if len(misurati) < MIN_RISULTATI_PER_CALIBRARE:
        print(f"Indice: {len(misurati)} post misurati, ne servono {MIN_RISULTATI_PER_CALIBRARE} per calibrare")
        return None
    media = sum(_qualita(v) for v in misurati) / len(misurati)
    attuali = pesi()
    nuovi = dict(stato.get("sezioni", {}))
    for sez in {v["sezione"] for v in misurati if v.get("sezione")}:
        q = [_qualita(v) for v in misurati if v.get("sezione") == sez]
        if len(q) < 3 or media <= 0:
            continue
        rapporto = (sum(q) / len(q)) / media
        fattore = max(0.85, min(1.15, rapporto ** 0.5))
        nuovi[sez] = round(max(0.3, min(1.0, attuali.get(sez, PESO_BASE) * fattore)), 3)
    # quanto l'indice previsto ha indovinato (correlazione semplice)
    coppie = [(v["indice"], _qualita(v)) for v in misurati if v.get("indice") is not None]
    corr = _correlazione(coppie)
    stato.update({"sezioni": nuovi, "ultima": adesso, "post_usati": len(misurati),
                  "correlazione_indice_risultati": corr})
    _scrivi(F_PESI, stato)
    print(f"Indice calibrato su {len(misurati)} post. Pesi: {nuovi}. Quanto indovina l'indice: {corr}")
    return stato


def _correlazione(coppie):
    if len(coppie) < 5:
        return None
    xs, ys = zip(*coppie)
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return round(sum((x - mx) * (y - my) for x, y in coppie) / (sx * sy), 2)
