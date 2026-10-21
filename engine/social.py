"""
ADOLOS – caroselli e pubblicazione su Instagram (API ufficiale di Meta)
=======================================================================
1. Per ogni notizia APPROVATA dalla redazione (Stato = Approvata su Notion, con una Sintesi)
   il sistema disegna un carosello Adolos: 5 immagini JPEG 1080x1350, solo grafica propria
   (niente foto delle testate). Le immagini finiscono in site/social/<id>/ e quindi sono online.
2. Se sulla scheda Notion è spuntata "Pubblica su Instagram", al giro dopo il carosello viene
   pubblicato con l'API ufficiale (Instagram Graph API, Content Publishing). Poi la scheda passa
   a Stato = Pubblicata con il link al post.

Secret necessari per il punto 2 (vedi LEGGIMI, Parte 5):
  IG_USER_ID      l'ID dell'account Instagram professionale
  IG_TOKEN        il token di accesso con il permesso di pubblicare
  IG_GRAPH_HOST   facoltativo: graph.facebook.com (predefinito) oppure graph.instagram.com
  SITO_URL        l'indirizzo del sito: Instagram scarica le immagini da lì
"""

import colorsys
import hashlib
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
RADICE = ENGINE.parent
CARTELLA = RADICE / "site" / "social"
FONT = ENGINE / "fonts"
STATO_IG = ENGINE / "cache" / "instagram.json"
W, H = 1080, 1350
GIORNI_TENUTA = 21

ROSSO = (211, 32, 43)
SCURO = (31, 7, 9)
BORDEAUX = (58, 11, 14)
CARTA = (247, 242, 235)
INK = (24, 18, 18)
GRIGIO = (110, 100, 100)


# ---------------------------------------------------------------- disegno
def _f(nome, size):
    from PIL import ImageFont
    return ImageFont.truetype(str(FONT / nome), size)


def _a_capo(draw, testo, font, larghezza):
    righe, riga = [], ""
    for parola in testo.split():
        prova = (riga + " " + parola).strip()
        if draw.textlength(prova, font=font) <= larghezza:
            riga = prova
        else:
            if riga:
                righe.append(riga)
            riga = parola
    if riga:
        righe.append(riga)
    return righe


def _blocco(draw, xy, testo, nome_font, size, larghezza, max_altezza, colore, interlinea=1.22, min_size=26):
    """Scrive un testo andando a capo; se non ci sta, rimpicciolisce il carattere."""
    x, y = xy
    while True:
        font = _f(nome_font, size)
        righe = _a_capo(draw, testo, font, larghezza)
        alt = len(righe) * size * interlinea
        if alt <= max_altezza or size <= min_size:
            break
        size -= 2
    for r in righe:
        draw.text((x, y), r, font=font, fill=colore)
        y += size * interlinea
    return y


def _latino(t):
    """True se il nome si può scrivere con i caratteri del carosello (alfabeto latino)."""
    return all(ord(c) < 0x250 or c in "’‘“”–—…" for c in t)


def colore_att(att):
    """Da rosso (voce) a verde (certa), come sul sito."""
    h = (max(0, min(100, att)) / 100) * 0.36
    r, g, b = colorsys.hls_to_rgb(h, 0.45, 0.75)
    return int(r * 255), int(g * 255), int(b * 255)


def _logo(draw, x, y, chiaro=True):
    draw.ellipse((x, y, x + 64, y + 64), fill=(255, 255, 255))
    draw.text((x + 32, y + 30), "α", font=_f("DejaVuSerif-BoldItalic.ttf", 46), fill=ROSSO, anchor="mm")
    draw.text((x + 80, y + 33), "Adolos", font=_f("Lora-Italic.ttf", 40), fill=(255, 255, 255) if chiaro else INK, anchor="lm")


def _piede(draw, n, tot, chiaro=True):
    c = (230, 205, 205) if chiaro else GRIGIO
    draw.text((70, H - 70), "adolos.it", font=_f("InstrumentSans-Bold.ttf", 30), fill=c, anchor="lm")
    draw.text((W - 70, H - 70), f"{n}/{tot}", font=_f("InstrumentSans-Regular.ttf", 30), fill=c, anchor="rm")


def _pillola(draw, x, y, testo, sfondo, colore=(255, 255, 255), size=28):
    f = _f("InstrumentSans-Bold.ttf", size)
    w = draw.textlength(testo, font=f)
    draw.rounded_rectangle((x, y, x + w + 36, y + size + 22), radius=(size + 22) // 2, fill=sfondo)
    draw.text((x + 18, y + (size + 22) / 2), testo, font=f, fill=colore, anchor="lm")
    return x + w + 36


def _sfondo_scuro():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), SCURO)
    d = ImageDraw.Draw(img)
    for i in range(H):   # sfumatura verticale
        t = i / H
        d.line([(0, i), (W, i)], fill=tuple(int(SCURO[k] + (BORDEAUX[k] - SCURO[k]) * t) for k in range(3)))
    return img, d


def _sfondo_chiaro():
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), CARTA)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 14), fill=ROSSO)
    return img, d


def carosello(s, testi, nomi_paesi, cont_di):
    """Disegna le 5 immagini. Restituisce la lista di oggetti PIL."""
    att = s.get("attendibilita", 50)
    titolo = testi.get("titolo") or s["titolo"]
    punti = testi.get("punti") or [p.strip() + "." for p in testi["sintesi"].split(". ") if len(p.strip()) > 20][:4]
    paesi = s.get("paesi", [])
    tot = 5
    slide = []

    # 1. copertina
    img, d = _sfondo_scuro()
    _logo(d, 70, 70)
    x = _pillola(d, 70, 200, s.get("sezione", "Notizie").upper(), ROSSO)
    _pillola(d, x + 14, 200, s.get("livello", ""), colore_att(att), (20, 20, 20))
    _blocco(d, (70, 330), titolo, "Lora-Bold.ttf", 96, W - 140, 640, (255, 255, 255), 1.12, 48)
    d.text((70, H - 230), f"Ripresa da {s['n_fonti']} {'testata' if s['n_fonti'] == 1 else 'testate'} in {len(paesi)} {'paese' if len(paesi) == 1 else 'paesi'}",
           font=_f("InstrumentSans-Bold.ttf", 36), fill=(255, 255, 255))
    d.text((70, H - 180), "Scorri per i fatti e le fonti  →", font=_f("InstrumentSans-Regular.ttf", 30), fill=(230, 205, 205))
    _piede(d, 1, tot)
    slide.append(img)

    # 2. in breve
    img, d = _sfondo_chiaro()
    d.text((70, 90), "IN BREVE", font=_f("InstrumentSans-Bold.ttf", 34), fill=ROSSO)
    _blocco(d, (70, 170), testi["sintesi"], "Lora-Regular.ttf", 46, W - 140, H - 380, INK, 1.42, 30)
    _piede(d, 2, tot, chiaro=False)
    slide.append(img)

    # 3. i fatti
    img, d = _sfondo_chiaro()
    d.text((70, 90), "I FATTI", font=_f("InstrumentSans-Bold.ttf", 34), fill=ROSSO)
    y = 180
    spazio = (H - 330) // max(1, len(punti))
    for i, p in enumerate(punti, 1):
        d.ellipse((70, y, 136, y + 66), fill=ROSSO)
        d.text((103, y + 34), str(i), font=_f("InstrumentSans-Bold.ttf", 34), fill=(255, 255, 255), anchor="mm")
        _blocco(d, (165, y + 4), p, "InstrumentSans-Bold.ttf", 40, W - 235, spazio - 40, INK, 1.25, 28)
        y += spazio
    _piede(d, 3, tot, chiaro=False)
    slide.append(img)

    # 4. chi ne parla
    img, d = _sfondo_chiaro()
    d.text((70, 90), "CHI NE PARLA", font=_f("InstrumentSans-Bold.ttf", 34), fill=ROSSO)
    d.text((70, 150), f"{s.get('livello', '')}: attendibilità {att} su 100", font=_f("InstrumentSans-Bold.ttf", 38), fill=INK)
    d.rounded_rectangle((70, 215, W - 70, 245), radius=15, fill=(225, 216, 205))
    d.rounded_rectangle((70, 215, 70 + int((W - 140) * att / 100), 245), radius=15, fill=colore_att(att))
    y = 300
    viste = []
    latine = sorted(s["fonti"], key=lambda f: not _latino(f["fonte"]))
    for f in latine:
        if f["fonte"] in viste or f.get("tipo") == "social" or not _latino(f["fonte"]):
            continue
        viste.append(f["fonte"])
        if len(viste) > 8:
            break
        d.text((70, y), f["fonte"][:38], font=_f("InstrumentSans-Bold.ttf", 36), fill=INK)
        d.text((W - 70, y + 4), nomi_paesi.get(f["paese"], f["paese"])[:22], font=_f("InstrumentSans-Regular.ttf", 30),
               fill=GRIGIO, anchor="ra")
        y += 62
    resto = s["n_fonti"] - len(viste[:8])
    if resto > 0:
        d.text((70, y + 6), f"e altre {resto} testate", font=_f("Lora-Italic.ttf", 32), fill=GRIGIO)
    # copertura per continente (alla Ground News)
    conti = {}
    for p in paesi:
        c = cont_di.get(p, "Altro")
        conti[c] = conti.get(c, 0) + 1
    if conti:
        y0 = H - 300
        d.text((70, y0), "Da dove arriva", font=_f("InstrumentSans-Bold.ttf", 30), fill=INK)
        x = 70
        totale = sum(conti.values())
        for i, (c, n) in enumerate(sorted(conti.items(), key=lambda kv: -kv[1])):
            w = int((W - 140) * n / totale)
            tinta = [ROSSO, (120, 30, 36), (190, 120, 60), (90, 110, 90), (100, 100, 140)][i % 5]
            d.rectangle((x, y0 + 50, x + w, y0 + 90), fill=tinta)
            if w > 150:
                d.text((x + 10, y0 + 70), f"{c} {n}", font=_f("InstrumentSans-Bold.ttf", 24), fill=(255, 255, 255), anchor="lm")
            x += w
    _piede(d, 4, tot, chiaro=False)
    slide.append(img)

    # 5. chiusura
    img, d = _sfondo_scuro()
    _logo(d, 70, 70)
    _blocco(d, (70, 420), "Tutte le fonti, con i link agli articoli originali, su adolos.it", "Lora-Bold.ttf", 70,
            W - 140, 400, (255, 255, 255), 1.16)
    nota = ("Sintesi preparata con l'aiuto dell'intelligenza artificiale e verificata dalla redazione."
            if testi.get("con_ai") else "Sintesi scritta dalla redazione di Adolos.")
    _blocco(d, (70, H - 300), nota, "InstrumentSans-Regular.ttf", 30, W - 140, 120, (230, 205, 205), 1.3)
    _piede(d, 5, tot)
    slide.append(img)
    return slide


def _impronta(s, testi):
    base = json.dumps([testi.get("titolo"), testi.get("sintesi"), testi.get("punti"), s.get("livello"), s["n_fonti"]],
                      ensure_ascii=False)
    return hashlib.sha1(base.encode()).hexdigest()[:12]


def genera_caroselli(storie):
    """Disegna i caroselli delle notizie approvate (solo se mancano o se il testo è cambiato)."""
    from sito import CONT_DI
    from adolos import PAESI
    CARTELLA.mkdir(parents=True, exist_ok=True)
    fatti = []
    for s in storie:
        t = s.get("sintesi")
        if not t or not t.get("sintesi"):
            continue
        cartella = CARTELLA / s["id"]
        meta = cartella / "info.json"
        imp = _impronta(s, t)
        try:
            if json.loads(meta.read_text())["impronta"] == imp:
                s["carosello"] = [f"social/{s['id']}/{i}.jpg" for i in range(1, 6)]
                continue
        except Exception:
            pass
        cartella.mkdir(parents=True, exist_ok=True)
        for i, img in enumerate(carosello(s, t, PAESI, CONT_DI), 1):
            img.save(cartella / f"{i}.jpg", "JPEG", quality=88, optimize=True, progressive=False)
        meta.write_text(json.dumps({"impronta": imp, "creato": datetime.now(timezone.utc).isoformat()}))
        s["carosello"] = [f"social/{s['id']}/{i}.jpg" for i in range(1, 6)]
        fatti.append(s["id"])
    # pulizia dei caroselli vecchi
    limite = time.time() - GIORNI_TENUTA * 86400
    for c in CARTELLA.iterdir():
        if c.is_dir() and (c / "info.json").exists() and (c / "info.json").stat().st_mtime < limite:
            shutil.rmtree(c, ignore_errors=True)
    print(f"Caroselli: {len(fatti)} nuovi")
    return fatti


# ---------------------------------------------------------------- Instagram (API ufficiale)
def didascalia(s, t):
    if t.get("didascalia") and t["didascalia"] != s.get("didascalia"):
        return t["didascalia"]          # scritta o corretta dalla redazione su Notion
    nomi = list(dict.fromkeys(f["fonte"] for f in sorted(s["fonti"], key=lambda f: (f["paese"] != "IT", not _latino(f["fonte"])))
                              if f.get("tipo") != "social"))[:4]
    altre = s["n_fonti"] - len(nomi)
    fonti = ", ".join(nomi) + (f" e altre {altre} testate" if altre > 0 else "")
    nota = ("Sintesi preparata con l'aiuto dell'AI e verificata dalla redazione."
            if t.get("con_ai") else "Sintesi della redazione di Adolos.")
    tag = {"Italia": "#italia", "Politica": "#politica", "Mondo": "#esteri", "Economia": "#economia",
           "Società": "#società", "Tecnologia": "#tecnologia", "Sport": "#sport", "Curiosità": "#curiosità"}
    return (f"{t.get('titolo') or s['titolo']}\n\n{t['sintesi']}\n\nFonti: {fonti}. Link agli articoli originali su adolos.it\n\n"
            f"{nota}\n\n#adolos #oltreifatti {tag.get(s.get('sezione'), '#notizie')}")[:2150]


def _ig(metodo, percorso, **dati):
    import requests
    host = os.environ.get("IG_GRAPH_HOST", "").strip() or "graph.facebook.com"
    ver = _conf().get("versione_api", "v23.0")
    dati["access_token"] = os.environ["IG_TOKEN"].strip()
    url = f"https://{host}/{ver}/{percorso}"
    r = requests.request(metodo, url, params=dati if metodo == "GET" else None,
                         data=dati if metodo != "GET" else None, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"Instagram {r.status_code}: {r.text[:200]}")
    return r.json()


def _conf():
    try:
        return json.loads((ENGINE / "fonti.json").read_text(encoding="utf-8")).get("instagram", {})
    except Exception:
        return {}


def _online(url):
    import requests
    try:
        return requests.head(url, timeout=15, allow_redirects=True).status_code == 200
    except Exception:
        return False


def pubblica(s, sito):
    utente = os.environ["IG_USER_ID"].strip()
    urls = [f"{sito}/{p}" for p in s["carosello"]]
    if not all(_online(u) for u in urls):
        raise RuntimeError("immagini non ancora online (il sito si aggiorna dopo questo giro): riprovo al prossimo")
    figli = [_ig("POST", f"{utente}/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
    contenitore = _ig("POST", f"{utente}/media", media_type="CAROUSEL", children=",".join(figli),
                      caption=didascalia(s, s["sintesi"]))["id"]
    for _ in range(20):                       # Instagram prepara il carosello
        stato = _ig("GET", contenitore, fields="status_code").get("status_code")
        if stato == "FINISHED":
            break
        if stato == "ERROR":
            raise RuntimeError("Instagram ha rifiutato il carosello")
        time.sleep(5)
    media = _ig("POST", f"{utente}/media_publish", creation_id=contenitore)["id"]
    return media, _ig("GET", media, fields="permalink").get("permalink") or ""


def esegui(storie, richieste_ig, campione=False, indici=None):
    """Dopo l'aggiornamento: link del carosello su Notion e pubblicazione su Instagram (i caroselli
    sono già stati disegnati da genera_caroselli, prima di costruire il sito)."""
    if campione:
        return
    import redazione
    sito = (os.environ.get("SITO_URL") or "").strip().rstrip("/")
    st = redazione._leggi_inviati()
    # link al carosello sulla scheda Notion
    for s in storie:
        if s.get("carosello") and sito and s["id"] in st["notion"] and s["id"] not in st["caroselli"]:
            try:
                redazione.aggiorna_scheda(st["notion"][s["id"]], {"Carosello": f"{sito}/{s['carosello'][0]}"})
                st["caroselli"].append(s["id"])
            except Exception as e:
                print("Link carosello non scritto su Notion:", str(e)[:120])
    redazione._scrivi_inviati(st)

    if not richieste_ig:
        return
    if not (os.environ.get("IG_USER_ID") and os.environ.get("IG_TOKEN") and sito):
        print("Instagram: ci sono notizie da pubblicare ma mancano IG_USER_ID, IG_TOKEN o SITO_URL")
        return
    try:
        stato = json.loads(STATO_IG.read_text(encoding="utf-8"))
    except Exception:
        stato = {}
    oggi = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if stato.get("giorno") != oggi:
        stato = {"giorno": oggi, "n": 0, "fatte": stato.get("fatte", {})}
    massimo = int(_conf().get("max_al_giorno", 6))
    per_id = {s["id"]: s for s in storie}
    for sid, page_id in richieste_ig.items():
        if stato["n"] >= massimo:
            print(f"Instagram: raggiunto il massimo di {massimo} post al giorno")
            break
        s = per_id.get(sid)
        if sid in stato["fatte"] or not s or not s.get("carosello") or not s.get("sintesi"):
            continue
        try:
            media, link = pubblica(s, sito)
            stato["fatte"][sid] = link
            try:
                import indice
                indice.registra_pubblicazione(sid, media, s, (indici or {}).get(sid))
            except Exception as e:
                print("Indice: pubblicazione non registrata:", str(e)[:120])
            stato["n"] += 1
            redazione.aggiorna_scheda(page_id, {"Link Instagram": link or "https://www.instagram.com/adolos.it/",
                                                "Stato": "Pubblicata"})
            print("Instagram: pubblicato", sid, link)
        except Exception as e:
            print("Instagram: non pubblicato", sid, str(e)[:160])
    STATO_IG.parent.mkdir(parents=True, exist_ok=True)
    STATO_IG.write_text(json.dumps(stato), encoding="utf-8")
