"""
ADOLOS – traduzione dei titoli in italiano (solo servizi ufficiali)
===================================================================
Si traducono SOLO i titoli (testi brevi, sempre mostrati insieme all'originale e al link).
Mai articoli interi.

Servizi, in ordine:
  1. l'AI configurata in ai.py (secret AI_KEY), se in fonti.json "ai" > "traduci_titoli" è true;
  2. DeepL, se c'è il secret DEEPL_KEY (le chiavi che finiscono con ":fx" sono del piano gratuito);
  3. nessuno: i titoli restano nella lingua originale. È gratis e legale, solo meno comodo.

Il traduttore pubblico di Google e MyMemory NON si usano più: non sono API ufficiali.

Ogni titolo tradotto viene salvato in engine/cache/traduzioni.json, così non si ritraduce
(e non si paga) due volte la stessa cosa.
"""

import hashlib
import json
import os
import time
from pathlib import Path

import ai

ENGINE = Path(__file__).resolve().parent
CACHE = ENGINE / "cache" / "traduzioni.json"
GIORNI_CACHE = 4
MAX_TITOLI_AL_GIRO = 400       # il resto si traduce al giro dopo
PACCO_AI = 50                  # titoli per richiesta

SISTEMA = ("Traduci in italiano dei titoli di notizie. Rispondi SOLO con un array JSON di stringhe, "
           "una per titolo, nello stesso ordine. Traduzione fedele e neutra, senza aggiungere nulla, "
           "senza virgolette in più, nomi propri invariati.")


def _chiave(lingua, testo):
    return hashlib.sha1(f"{lingua}|{testo}".encode("utf-8")).hexdigest()[:16]


def _leggi_cache():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _scrivi_cache(cache):
    limite = time.time() - GIORNI_CACHE * 86400
    pulita = {k: v for k, v in cache.items() if v[1] >= limite}
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(pulita, ensure_ascii=False), encoding="utf-8")


def con_ai(testi):
    elenco = json.dumps(testi, ensure_ascii=False)
    risposta = ai.chiedi(SISTEMA, elenco, max_token=60 * len(testi) + 200)
    out = ai.json_da(risposta)
    if not isinstance(out, list) or len(out) != len(testi):
        raise ValueError("risposta non allineata")
    return [str(x).strip() for x in out]


def con_deepl(testi, lingua):
    import requests
    chiave = os.environ["DEEPL_KEY"].strip()
    url = "https://api-free.deepl.com/v2/translate" if chiave.endswith(":fx") else "https://api.deepl.com/v2/translate"
    dati = {"text": testi, "target_lang": "IT"}
    if lingua not in ("?", None):
        dati["source_lang"] = lingua.upper()
    r = requests.post(url, json=dati, headers={"Authorization": "DeepL-Auth-Key " + chiave}, timeout=30)
    r.raise_for_status()
    return [t["text"] for t in r.json()["translations"]]


def servizio():
    if ai.attiva() and ai.conf().get("traduci_titoli", True):
        return "ai"
    if os.environ.get("DEEPL_KEY", "").strip():
        return "deepl"
    return None


def traduci_items(items):
    """Aggiunge 'titolo_it' agli articoli non in italiano (se c'è un servizio ufficiale configurato)."""
    cache = _leggi_cache()
    adesso = time.time()
    da_fare = {}   # lingua -> {titolo: [items]}
    for it in items:
        if it.get("titolo_it"):
            continue
        lingua = it.get("lingua") or "?"
        if lingua == "it":
            it["titolo_it"] = it["titolo"]
            continue
        k = _chiave(lingua, it["titolo"])
        if k in cache:
            it["titolo_it"] = cache[k][0]
            cache[k][1] = adesso
            continue
        da_fare.setdefault(lingua, {}).setdefault(it["titolo"], []).append(it)

    quale = servizio()
    if not quale:
        _scrivi_cache(cache)
        n = sum(len(v) for v in da_fare.values())
        print(f"Traduzioni: nessun servizio ufficiale configurato, {n} titoli restano in lingua originale")
        return items

    # prima i titoli più recenti
    coda = sorted(((max(x["data"] for x in lst), lingua, t) for lingua, per in da_fare.items() for t, lst in per.items()),
                  reverse=True)[:MAX_TITOLI_AL_GIRO]
    per_lingua = {}
    for _, lingua, t in coda:
        per_lingua.setdefault(lingua, []).append(t)

    tradotti = errori = 0
    for lingua, testi in per_lingua.items():
        for i in range(0, len(testi), PACCO_AI):
            pacco = testi[i:i + PACCO_AI]
            try:
                risultato = con_ai(pacco) if quale == "ai" else con_deepl(pacco, lingua)
            except ai.TettoRaggiunto:
                print("Traduzioni: tetto di spesa mensile raggiunto, si riprende il mese prossimo")
                _scrivi_cache(cache)
                return items
            except Exception as e:
                errori += 1
                print("Traduzione non riuscita:", str(e)[:120])
                if errori >= 3:
                    break
                continue
            for t, tr in zip(pacco, risultato):
                if not tr:
                    continue
                cache[_chiave(lingua, t)] = [tr, adesso]
                for it in da_fare[lingua][t]:
                    it["titolo_it"] = tr
                tradotti += 1
        if errori >= 3:
            break
    _scrivi_cache(cache)
    mancanti = sum(1 for it in items if not it.get("titolo_it"))
    print(f"Traduzioni ({quale}): {tradotti} nuove, {mancanti} rimandate o in lingua originale")
    return items
