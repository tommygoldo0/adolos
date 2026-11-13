"""
ADOLOS – immagini per i caroselli (solo fonti legali)
=====================================================
Ordine (vedi fonti.json > "immagini" e la skill adolos-controllo-legale):
  1. Foto con licenza libera da Wikimedia Commons (CC0, pubblico dominio, CC BY, CC BY-SA),
     prese dalla pagina Wikipedia della persona, del luogo o dell'azienda principale della notizia.
     Autore e licenza vengono scritti sulla copertina e nella didascalia.
  2. Solo se attivato ("ai": true) e dentro il tetto giornaliero e mensile: una scena GENERICA creata
     con l'AI di Gemini, senza persone riconoscibili, loghi o scritte, con l'etichetta
     "Immagine illustrativa generata con AI". Mai volti di persone vere (art. 612-quater c.p.).
  3. Altrimenti niente foto: fondo rosso Adolos.
Mai foto prese dai giornali o da Google.

Le immagini restano nella cache privata (engine/cache/immagini/); sul sito finiscono solo
dentro il carosello, con i crediti.
"""

import base64
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
CARTELLA = ENGINE / "cache" / "immagini"
REGISTRO = ENGINE / "cache" / "immagini.json"
USO = ENGINE / "cache" / "uso_immagini.json"
UA = {"User-Agent": "AdolosBot/1.0 (https://tommygoldo0.github.io/adolos/; redazioneadolos@gmail.com)"}
ETICHETTA_AI = "Immagine illustrativa generata con AI"
PREDEFINITO = {
    "wikimedia": True,
    "ai": False,
    "ai_modelli": ["gemini-nano-banana-2.1", "gemini-3.1-flash-image"],
    "ai_max_al_giorno": 3,
    "ai_budget_mensile_usd": 3.5,
    "ai_costo_immagine_usd": 0.07,
    "licenze_ammesse": ["CC0", "Public domain", "CC BY", "CC BY-SA"],
}
INIZI = {"la", "il", "lo", "le", "i", "gli", "un", "una", "the", "a", "perché", "perche", "chi", "come", "dove",
         "why", "how", "who", "what", "ecco", "anche", "ora", "oggi"}
GENERICHE = {"presidente", "governo", "ministro", "polizia", "esercito", "stati", "uniti", "unione", "europea",
             "champions", "league", "guerra", "notizie", "casa", "bianca"}


def conf():
    try:
        c = json.loads((ENGINE / "fonti.json").read_text(encoding="utf-8")).get("immagini", {})
    except Exception:
        c = {}
    return {**PREDEFINITO, **{k: v for k, v in c.items() if not k.startswith("_")}}


def _leggi(p, vuoto):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return vuoto


def _scrivi(p, dati):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(dati, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- 1. Wikimedia Commons
def _pulisci_html(t):
    t = re.sub(r"<[^>]+>", "", t or "")
    return re.sub(r"\s+", " ", t).strip()[:80]


def candidati(titolo, titoli_fonti, testo=""):
    """Chi o cosa cercare per la foto, in ordine. Regole per non sbagliare soggetto:
    - una PERSONA si cerca solo con nome e cognome (un cognome da solo può essere un'altra persona o un luogo:
      "Nasser" è anche un ospedale di Gaza). I nomi completi si prendono anche dalla sintesi;
    - un LUOGO è la parola prima della virgola o dei due punti a inizio titolo ("Spagna, ...", "Gaza: ...");
    - prima le persone citate nel titolo, poi il luogo, poi le persone citate solo nella sintesi."""
    titolo = titolo or ""
    conta = {}
    for t in [titolo] * 3 + list(titoli_fonti) + [testo or ""]:
        for m in re.finditer(r"(?:[A-ZÀ-Ý][\w'’\-]+)(?:\s+(?:de|di|da|van|von|bin|al|del|la)?\s*[A-ZÀ-Ý][\w'’\-]+)+", t or ""):
            parole = m.group(0).split()
            while parole and parole[0].lower() in INIZI:
                parole = parole[1:]
            if len(parole) < 2 or all(x.lower() in GENERICHE for x in parole):
                continue
            nome = " ".join(parole)
            conta[nome] = conta.get(nome, 0) + 1
    def nel_titolo(n):
        return any(x.lower() in titolo.lower() for x in n.split() if len(x) > 3)
    persone_titolo = sorted((n for n in conta if nel_titolo(n)), key=lambda n: -conta[n])
    altre = sorted((n for n in conta if not nel_titolo(n)), key=lambda n: -conta[n])
    luogo = re.match(r"\s*([A-ZÀ-Ý][\w'’\-]+(?:\s+[A-ZÀ-Ý][\w'’\-]+)?)\s*[,:]", titolo)
    luoghi = [luogo.group(1)] if luogo and luogo.group(1).lower() not in INIZI else []
    visti, out = set(), []
    for n in persone_titolo[:3] + luoghi + altre[:2]:
        if n.lower() not in visti:
            visti.add(n.lower())
            out.append(n)
    return out[:5]


def _foto_da_wikidata(lingua, nome):
    """Se la pagina Wikipedia non ha una foto adatta (per paesi e regioni di solito c'è la bandiera), chiede a
    Wikidata la foto del soggetto o, per un paese o una regione, quella della sua capitale."""
    import requests
    r = requests.get(f"https://{lingua}.wikipedia.org/w/api.php", headers=UA, timeout=20, params={
        "action": "query", "titles": nome, "prop": "pageprops", "ppprop": "wikibase_item", "redirects": 1, "format": "json"}).json()
    qid = next((p.get("pageprops", {}).get("wikibase_item") for p in r.get("query", {}).get("pages", {}).values()), None)
    def proprieta(q, prop):
        e = requests.get("https://www.wikidata.org/w/api.php", headers=UA, timeout=20, params={
            "action": "wbgetclaims", "entity": q, "property": prop, "format": "json"}).json()
        v = [c.get("mainsnak", {}).get("datavalue", {}).get("value") for c in e.get("claims", {}).get(prop, [])]
        return next((x for x in v if x), None)
    if not qid:
        return None, ""
    foto = proprieta(qid, "P18")
    if isinstance(foto, str) and not foto.lower().endswith((".svg", ".gif")):
        return foto.replace(" ", "_"), ""
    capitale = proprieta(qid, "P36")
    if isinstance(capitale, dict) and capitale.get("id"):
        foto = proprieta(capitale["id"], "P18")
        if isinstance(foto, str) and not foto.lower().endswith((".svg", ".gif")):
            return foto.replace(" ", "_"), " (capitale)"
    return None, ""


def _licenza_ok(nome, ammesse):
    n = (nome or "").lower()
    return any(n.startswith(a.lower()) for a in ammesse) or n in ("pd", "public domain")


def wikimedia(nomi, ammesse):
    """Cerca la foto principale della pagina Wikipedia (it, poi en) e ne controlla la licenza su Commons."""
    import requests
    for nome in nomi:
        for lingua in ("it", "en"):
            try:
                r = requests.get(f"https://{lingua}.wikipedia.org/w/api.php", headers=UA, timeout=20, params={
                    "action": "query", "titles": nome, "prop": "pageimages", "piprop": "name",
                    "redirects": 1, "format": "json"}).json()
                pagine = list(r.get("query", {}).get("pages", {}).values())
                file = next((p.get("pageimage") for p in pagine if p.get("pageimage")), None)
                nota = ""
                if not file or file.lower().endswith((".svg", ".gif")):      # niente bandiere, mappe e loghi in svg
                    file, nota = _foto_da_wikidata(lingua, nome)
                    if not file:
                        continue
                info = requests.get("https://commons.wikimedia.org/w/api.php", headers=UA, timeout=20, params={
                    "action": "query", "titles": f"File:{file}", "prop": "imageinfo",
                    "iiprop": "url|extmetadata|size", "iiurlwidth": 2200, "format": "json"}).json()
                pag = list(info.get("query", {}).get("pages", {}).values())
                ii = (pag[0].get("imageinfo") or [None])[0] if pag else None
                if not ii:
                    continue      # file non su Commons (per esempio immagini "fair use" di en.wikipedia)
                meta = ii.get("extmetadata", {})
                lic = meta.get("LicenseShortName", {}).get("value", "")
                if meta.get("NonFree", {}).get("value") or not _licenza_ok(lic, ammesse):
                    continue
                if min(ii.get("width", 0), ii.get("height", 0)) < 700:
                    continue      # troppo piccola per riempire la copertina
                dati = requests.get(ii.get("thumburl") or ii["url"], headers=UA, timeout=30).content
                autore = _pulisci_html(meta.get("Artist", {}).get("value", "")) or "autore su Wikimedia Commons"
                return {"tipo": "wikimedia", "dati": dati, "soggetto": nome + nota,
                        "credito": f"Foto: {autore} · {lic} · Wikimedia Commons",
                        "pagina": ii.get("descriptionurl", "")}
            except Exception as e:
                print(f"Immagine Wikimedia non trovata per {nome}: {str(e)[:80]}")
    return None


# ---------------------------------------------------------------- 2. scena generica con AI
def _chiave():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k
    try:
        prov = (os.environ.get("AI_PROVIDER") or json.loads((ENGINE / "fonti.json").read_text(encoding="utf-8"))
                .get("ai", {}).get("provider", "")).strip().lower()
    except Exception:
        prov = ""
    return os.environ.get("AI_KEY", "").strip() if prov == "gemini" else ""


def _uso(c):
    oggi = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    u = _leggi(USO, {})
    if u.get("mese") != oggi[:7]:
        u = {"mese": oggi[:7], "costo_usd": 0.0, "giorno": oggi, "oggi": 0}
    if u.get("giorno") != oggi:
        u["giorno"], u["oggi"] = oggi, 0
    return u


def ai_scena(scena, c):
    """Una scena generica, senza persone riconoscibili. Rispetta i tetti di spesa."""
    import requests
    chiave = _chiave()
    if not (c["ai"] and chiave and scena):
        return None
    u = _uso(c)
    if u["oggi"] >= int(c["ai_max_al_giorno"]) or u["costo_usd"] >= float(c["ai_budget_mensile_usd"]):
        print("Immagini AI: tetto del giorno o del mese raggiunto")
        return None
    prompt = (f"Editorial news illustration, photorealistic, natural light: {scena}. "
              "Strict rules: no recognizable real people, faces not visible or blurred in the distance, "
              "no logos, no brand names, no text, no flags of real organizations, no violence or gore. "
              "Vertical composition 4:5, calm and neutral mood.")
    for modello in c["ai_modelli"]:
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{modello}:generateContent",
                headers={"x-goog-api-key": chiave, "Content-Type": "application/json"}, timeout=120,
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "4:5"}}})
            if r.status_code >= 300:
                print(f"Immagine AI ({modello}) non creata: {r.status_code} {r.text[:150]}")
                continue
            parti = [p for cand in r.json().get("candidates", []) for p in cand.get("content", {}).get("parts", [])]
            img = next((p.get("inlineData") or p.get("inline_data") for p in parti
                        if p.get("inlineData") or p.get("inline_data")), None)
            if not img:
                continue
            u["oggi"] += 1
            u["costo_usd"] += float(c["ai_costo_immagine_usd"])
            _scrivi(USO, u)
            return {"tipo": "ai", "dati": base64.b64decode(img["data"]), "soggetto": scena[:80],
                    "credito": ETICHETTA_AI, "modello": modello}
        except Exception as e:
            print(f"Immagine AI ({modello}) non creata: {str(e)[:120]}")
    return None


# ---------------------------------------------------------------- principale
def per_storia(s, titolo, gruppo, scena="", testo=""):
    """Restituisce {"file": percorso, "credito": ..., "tipo": ...} oppure None. Una sola ricerca per notizia.
    'testo' = la sintesi: serve a trovare nome e cognome delle persone citate nel titolo solo per cognome."""
    c = conf()
    reg = _leggi(REGISTRO, {})
    gia = reg.get(s["id"])
    if gia is not None:
        if gia and Path(gia.get("file", "")).exists():
            return gia
        if gia == {} and not (scena and c["ai"]):
            return None      # già cercata, niente di adatto
    trovata = None
    if c["wikimedia"]:
        titoli = [x.get("titolo_it") or x.get("titolo", "") for x in gruppo if x.get("tipo") != "social"]
        trovata = wikimedia(candidati(titolo, titoli, testo), c["licenze_ammesse"])
    if not trovata:
        trovata = ai_scena(scena, c)
    if not trovata:
        reg[s["id"]] = {}
        _scrivi(REGISTRO, reg)
        return None
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(trovata["dati"])).convert("RGB")
        CARTELLA.mkdir(parents=True, exist_ok=True)
        file = CARTELLA / f"{s['id']}.jpg"
        img.save(file, "JPEG", quality=90)
    except Exception as e:
        print("Immagine non salvata:", str(e)[:100])
        return None
    voce = {k: v for k, v in trovata.items() if k != "dati"}
    voce["file"] = str(file)
    reg[s["id"]] = voce
    _scrivi(REGISTRO, reg)
    print(f"Immagine per {s['id']}: {voce['tipo']} ({voce['credito'][:70]})")
    return voce
