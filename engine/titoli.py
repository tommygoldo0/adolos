"""
ADOLOS – titoli scritti da Adolos (niente titoli delle testate sul sito)
=======================================================================
Scelta della redazione (ottobre 2026): sul sito e nei dati pubblici NON mostriamo i titoli
originali delle testate né le loro traduzioni, finché non sappiamo se ci è permesso
(art. 43-bis L. 633/1941: diritto degli editori, esclusi solo link, singole parole ed
estratti molto brevi). Delle testate mostriamo solo: nome, paese, data e link all'articolo.

Ogni notizia pubblica ha quindi un titolo scritto da Adolos:
  1. il titolo approvato dalla redazione su Notion (se c'è);
  2. altrimenti un titolo neutro scritto dall'AI a partire dai fatti comuni a più testate,
     con controllo anti-copia (niente 5 parole di fila uguali a un titolo delle fonti);
  3. senza titolo Adolos la notizia NON va sul sito (resta solo nell'area staff su Notion).

Le testate in modalità "conta_e_link" (fonti.json > rss_diretti > "uso") non vengono passate
all'AI: servono solo a contare chi ne parla e a mettere il link.

Cache privata: engine/cache/titoli.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import ai
import sintesi

ENGINE = Path(__file__).resolve().parent
CACHE = ENGINE / "cache" / "titoli.json"
GIORNI = 4
PACCO = 15
N_PAROLE_COPIA_TITOLI = 5

SISTEMA = """Sei la redazione di Adolos, sito italiano di notizie. Per ogni notizia ricevi i titoli con cui
la raccontano più testate. Scrivi per ognuna un titolo NUOVO in italiano.

Regole:
- solo fatti presenti in almeno uno dei titoli, niente aggiunte; se un fatto lo dice una sola testata, lascialo fuori;
- parole tue: non copiare e non tradurre parola per parola nessun titolo;
- tono neutro, niente aggettivi d'effetto, niente punti esclamativi, niente virgolette di citazioni;
- reati: "accusato", "indagato", "secondo la polizia"; mai colpe date per certe, mai nomi di minori o vittime;
- massimo 90 caratteri, prima il fatto principale.

Rispondi SOLO con un oggetto JSON {"<id>": "<titolo>", ...} con gli stessi id ricevuti."""


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


def _materiale(gruppo):
    """Titoli (in italiano se tradotti) delle testate che si possono passare all'AI, max 6."""
    viste, out = set(), []
    for x in sorted(gruppo, key=lambda x: x["data"]):
        if x.get("tipo") == "social" or x.get("correlato") or x.get("uso") == "conta_e_link":
            continue
        k = x["fonte"].lower()
        if k in viste:
            continue
        viste.add(k)
        out.append((x.get("titolo_it") or x["titolo"], x["titolo"]))
        if len(out) >= 6:
            break
    return out


def copiato(titolo, fonti_titoli):
    nostre = sintesi._sequenze(sintesi._norm(titolo), N_PAROLE_COPIA_TITOLI)
    loro = set()
    for t in fonti_titoli:
        loro |= sintesi._sequenze(sintesi._norm(t), N_PAROLE_COPIA_TITOLI)
    return sorted(nostre & loro)


def prepara(storie, gruppi, max_al_giro=120, approvati=None):
    """Restituisce {id storia: titolo Adolos}. Usa i titoli approvati, la cache e, se c'è, l'AI."""
    approvati = approvati or {}
    cache = _leggi()
    out = {sid: t for sid, t in approvati.items() if t}
    for s in storie:
        v = cache.get(s["id"])
        if s["id"] not in out and v and v.get("titolo"):
            out[s["id"]] = v["titolo"]
    da_fare = []
    for s in storie:
        v = cache.get(s["id"], {})
        if s["id"] in out or v.get("titolo") or v.get("tentativi", 0) >= 2:
            continue
        mat = _materiale(gruppi.get(s["id"], []))
        if len(mat) >= 1:
            da_fare.append((s, mat))
    da_fare = da_fare[:max_al_giro]
    if da_fare and not ai.attiva():
        print(f"Titoli: AI non configurata, {len(da_fare)} notizie restano fuori dal sito finché non hanno un titolo Adolos")
        return out
    fatti = scartati = 0
    adesso = datetime.now(timezone.utc).timestamp()
    for i in range(0, len(da_fare), PACCO):
        pacco = da_fare[i:i + PACCO]
        richiesta = "\n\n".join(f'id: {s["id"]}\n' + "\n".join(f"- {it}" for it, _ in mat) for s, mat in pacco)
        try:
            risposta = ai.json_da(ai.chiedi(SISTEMA, richiesta, max_token=60 * len(pacco) + 200))
        except ai.TettoRaggiunto:
            print("Titoli: tetto di spesa mensile raggiunto")
            break
        except Exception as e:
            print("Titoli non scritti:", str(e)[:120])
            continue
        if not isinstance(risposta, dict):
            continue
        for s, mat in pacco:
            t = str(risposta.get(s["id"], "")).strip().strip('"«»').strip()[:110]
            # confronto con TUTTI i titoli del gruppo (anche testate solo-conteggio, social e correlati)
            fonti_titoli = [x.get("titolo_it") or "" for x in gruppi.get(s["id"], [])] + \
                           [x["titolo"] for x in gruppi.get(s["id"], [])] + [s.get("titolo", "")]
            if not t or copiato(t, fonti_titoli):
                cache[s["id"]] = {"ts": adesso, "titolo": "", "scartato": "vuoto o copiato",
                                  "tentativi": cache.get(s["id"], {}).get("tentativi", 0) + 1}
                scartati += 1
                continue
            cache[s["id"]] = {"ts": adesso, "titolo": t}
            out[s["id"]] = t
            fatti += 1
    _scrivi(cache)
    if da_fare:
        print(f"Titoli Adolos: {fatti} nuovi, {scartati} scartati (copiati o vuoti)")
    return out


# ---------------------------------------------------------------- dati pubblici
CAMPI_PRIVATI_STORIA = ("titolo_originale", "fonte_titolo", "didascalia", "bot_motivo", "bot", "controllo", "motivi")
CAMPI_PRIVATI_FONTE = ("titolo", "titolo_it", "riassunto")


def versione_pubblica(s, titolo):
    """Copia della notizia per il sito: titolo Adolos, delle testate solo nome, paese, data, link."""
    p = {k: v for k, v in s.items() if k not in CAMPI_PRIVATI_STORIA and not k.startswith("_")}
    p["titolo"] = titolo
    p["fonti"] = []
    for f in s.get("fonti", []):
        g = {k: v for k, v in f.items() if k not in CAMPI_PRIVATI_FONTE}
        if str(g.get("link", "")).startswith("https://news.google"):   # i link di ricerca contengono il titolo
            g["link"] = ""
        p["fonti"].append(g)
    if isinstance(p.get("prima"), dict):
        p["prima"] = {k: v for k, v in p["prima"].items() if k != "link" or not str(v).startswith("https://news.google")}
    return p
