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


GIALLO = (255, 212, 0)
ROSSO_SCURO = (156, 20, 28)
ROSA = (255, 222, 222)
ARCHIVO = RADICE / "site" / "assets" / "fonts" / "archivo.woff2"


def _arch(size, peso=900):
    """Archivo (lo stesso carattere del sito), con il peso scelto. Se manca, Instrument Sans."""
    from PIL import ImageFont
    try:
        f = ImageFont.truetype(str(ARCHIVO), size)
        try:
            f.set_variation_by_axes([peso])
        except Exception:
            pass
        return f
    except Exception:
        return _f("InstrumentSans-Bold.ttf", size)


def _righe_strette(draw, testo, font, larghezza, stretto):
    """Va a capo tenendo conto che ogni riga verrà schiacciata in orizzontale (carattere "stretto")."""
    return _a_capo(draw, testo, font, larghezza / stretto)


def _scrivi_stretto(img, x, y, riga, font, colore, stretto=0.84):
    """Disegna una riga e la stringe in orizzontale: titoli spessi e stretti come nei post @adolos.it."""
    from PIL import Image, ImageDraw
    w = int(ImageDraw.Draw(img).textlength(riga, font=font)) + 8
    h = int(font.size * 1.3)
    strato = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(strato).text((0, 0), riga, font=font, fill=colore + (255,))
    strato = strato.resize((max(1, int(w * stretto)), h), Image.LANCZOS)
    img.paste(strato, (int(x), int(y)), strato)


def _titolo(img, draw, blocchi, x, y, larghezza, altezza, size=118, min_size=56, interlinea=0.98, stretto=0.84,
            colore=(255, 255, 255)):
    """Scrive uno o più blocchi di testo maiuscolo (con una riga vuota tra un blocco e l'altro),
    rimpicciolendo il carattere finché non ci sta. Restituisce la y finale."""
    while True:
        font = _arch(size, 900)
        tutte = []
        for k, b in enumerate(blocchi):
            if k:
                tutte.append("")
            tutte += _righe_strette(draw, b.upper(), font, larghezza, stretto)
        alt = sum(size * (interlinea if r else 0.45) for r in tutte)
        largo = max([draw.textlength(r, font=font) * stretto for r in tutte if r] or [0])
        if (alt <= altezza and largo <= larghezza) or size <= min_size:
            break
        size -= 4
    for r in tutte:
        if r:
            _scrivi_stretto(img, x, y, r, font, colore, stretto)
        y += size * (interlinea if r else 0.45)
    return y


def _sfondo_rosso(variante=0):
    """Rosso Adolos pieno con una leggera sfumatura diagonale (niente foto: nessun problema di diritti)."""
    from PIL import Image, ImageDraw
    a, b = [(ROSSO_SCURO, ROSSO), (BORDEAUX, ROSSO_SCURO), (ROSSO_SCURO, (186, 26, 36))][variante % 3]
    img = Image.new("RGB", (W, H), a)
    d = ImageDraw.Draw(img)
    for i in range(0, W + H, 3):
        t = i / (W + H)
        c = tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))
        d.line([(i, 0), (i - H, H)], fill=c, width=4)
    return img, ImageDraw.Draw(img)


def _alfa(draw, x, y, size=84, colore=(255, 255, 255)):
    draw.text((x, y), "α", font=_f("DejaVuSerif-BoldItalic.ttf", size), fill=colore, anchor="rt")


def _piede_ig(draw, n, tot, ultimo=False, scuro=False):
    c = (80, 60, 60) if scuro else ROSA
    draw.text((70, H - 72), f"{n}/{tot}", font=_arch(30, 600), fill=c, anchor="lm")
    draw.text((W / 2, H - 72), "α", font=_f("DejaVuSerif-BoldItalic.ttf", 40), fill=ROSSO if scuro else c, anchor="mm")
    if ultimo:
        draw.text((W - 70, H - 72), "adolos.it", font=_arch(30, 700), fill=c, anchor="rm")
    else:   # la freccia con DejaVu: Archivo non ha il carattere →
        draw.text((W - 70, H - 72), "→", font=_f("DejaVuSerif-BoldItalic.ttf", 34), fill=c, anchor="rm")
        draw.text((W - 118, H - 72), "Scorri", font=_arch(30, 700), fill=c, anchor="rm")


def _kicker(draw, x, y, testo, colore=GIALLO, size=32):
    draw.text((x, y), testo.upper(), font=_arch(size, 800), fill=colore)


def _divide_titolo(titolo):
    """ "PSG-Barcellona 4-2: Vitinha decide" -> ["PSG-Barcellona 4-2:", "Vitinha decide"] (stile @adolos.it)."""
    if ":" in titolo:
        a, b = titolo.split(":", 1)
        if 3 <= len(a) <= 45 and b.strip():
            return [a.strip() + ":", b.strip()]
    return [titolo]


def _testate_uniche(s):
    viste = []
    for f in sorted(s["fonti"], key=lambda f: not _latino(f["fonte"])):
        if f.get("tipo") == "social" or f["fonte"] in [v["fonte"] for v in viste] or not _latino(f["fonte"]):
            continue
        viste.append(f)
    return viste


def carosello(s, testi, nomi_paesi, cont_di):
    """Disegna il carosello nello stile della pagina @adolos.it. Restituisce la lista di immagini PIL.
    Copertina + una slide per ogni fatto + "Chi ne parla" + fonti. Niente attendibilità: resta su Notion."""
    titolo = testi.get("titolo") or s["titolo"]
    punti = testi.get("punti") or [p.strip() + "." for p in testi["sintesi"].split(". ") if len(p.strip()) > 20][:4]
    punti = [p for p in punti if p][:4]
    paesi = s.get("paesi", [])
    testate = _testate_uniche(s)
    n_test = max(s.get("n_fonti", 0), len(testate))
    tot = 1 + len(punti) + 2
    slide = []

    # 1. copertina
    img, d = _sfondo_rosso(0)
    _kicker(d, 70, 92, s.get("sezione") or "Notizie")
    _alfa(d, W - 64, 56, 96)
    y0 = 200
    if s.get("punto_cieco") == "italia":
        f = _arch(30, 800)
        testo = "IL MONDO NE PARLA, L'ITALIA NO"
        w = d.textlength(testo, font=f)
        d.rectangle((70, y0, 70 + w + 36, y0 + 56), fill=GIALLO)
        d.text((88, y0 + 28), testo, font=f, fill=BORDEAUX, anchor="lm")
        y0 += 96
    _titolo(img, d, _divide_titolo(titolo), 70, y0, W - 140, H - y0 - 260)
    riga = f"{n_test} {'testata' if n_test == 1 else 'testate'} · {len(paesi)} {'paese' if len(paesi) == 1 else 'paesi'}"
    d.text((70, H - 170), riga.upper(), font=_arch(32, 800), fill=(255, 255, 255))
    _piede_ig(d, 1, tot)
    slide.append(img)

    # 2. un fatto per slide, scritto grande
    for i, p in enumerate(punti, 1):
        img, d = _sfondo_rosso(1 if i % 2 else 2)
        _kicker(d, 70, 92, f"I fatti · {i} di {len(punti)}")
        _alfa(d, W - 64, 56, 72, ROSA)
        size = 76
        while True:
            font = _arch(size, 800)
            righe = _a_capo(d, p, font, W - 140)
            if len(righe) * size * 1.18 <= H - 420 or size <= 40:
                break
            size -= 4
        y = (H - len(righe) * size * 1.18) / 2
        for r in righe:
            d.text((70, y), r, font=font, fill=(255, 255, 255))
            y += size * 1.18
        _piede_ig(d, 1 + i, tot)
        slide.append(img)

    # 3. chi ne parla (il tratto che ci distingue, alla Ground News)
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (W, H), CARTA)
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 16), fill=ROSSO)
    _kicker(d, 70, 92, "Chi ne parla", ROSSO)
    _titolo(img, d, [riga], 70, 150, W - 140, 130, size=92, min_size=50, colore=INK)
    y = 300
    mostrate = testate[:9]
    for f in mostrate:
        d.text((70, y), f["fonte"][:34], font=_arch(38, 750), fill=INK)
        d.text((W - 70, y + 4), nomi_paesi.get(f["paese"], f["paese"])[:22], font=_arch(30, 450), fill=GRIGIO, anchor="ra")
        d.line([(70, y + 56), (W - 70, y + 56)], fill=(225, 214, 202), width=2)
        y += 70
    resto = n_test - len(mostrate)
    if resto > 0:
        d.text((70, y + 8), f"e altre {resto} testate", font=_f("Lora-Italic.ttf", 32), fill=GRIGIO)
    conti = {}
    for p in paesi:
        c = cont_di.get(p, "Altro")
        conti[c] = conti.get(c, 0) + 1
    if conti:
        y0 = H - 270
        d.text((70, y0), "DA DOVE ARRIVA", font=_arch(28, 800), fill=INK)
        x = 70
        totale = sum(conti.values())
        for i, (c, n) in enumerate(sorted(conti.items(), key=lambda kv: -kv[1])):
            w = int((W - 140) * n / totale)
            tinta = [ROSSO, BORDEAUX, (190, 120, 60), (90, 110, 90), (100, 100, 140)][i % 5]
            d.rectangle((x, y0 + 48, x + w, y0 + 96), fill=tinta)
            if w > 150:
                d.text((x + 12, y0 + 72), f"{c} {n}", font=_arch(24, 800), fill=(255, 255, 255), anchor="lm")
            x += w
    _piede_ig(d, tot - 1, tot, scuro=True)
    slide.append(img)

    # 4. fonti e chiusura
    img, d = _sfondo_rosso(0)
    _kicker(d, 70, 92, "Fonti")
    _alfa(d, W - 64, 56, 96)
    nomi = [f["fonte"] for f in testate[:6]]
    if n_test > len(nomi):
        nomi.append(f"e altre {n_test - len(nomi)}")
    y = _titolo(img, d, [", ".join(nomi)], 70, 190, W - 140, 560, size=84, min_size=44)
    _titolo(img, d, ["Tutti i link agli articoli su adolos.it"], 70, max(y + 50, 820), W - 140, 200, size=64,
            min_size=40, colore=GIALLO)
    nota = "Testo preparato con l'aiuto dell'AI e verificato dalla redazione."   # regola 9: sempre dichiarato
    d.text((70, H - 160), nota, font=_arch(28, 500), fill=ROSA)
    _piede_ig(d, tot, tot, ultimo=True)
    slide.append(img)
    return slide


VERSIONE_GRAFICA = 2      # cambiarla ridisegna tutti i caroselli


def _impronta(s, testi):
    base = json.dumps([VERSIONE_GRAFICA, testi.get("titolo"), testi.get("sintesi"), testi.get("punti"), s["n_fonti"],
                       s.get("punto_cieco")], ensure_ascii=False)
    return hashlib.sha1(base.encode()).hexdigest()[:12]


def _pagina_carosello(cartella, s, t):
    """Pagina semplice con tutte le slide da scaricare e la didascalia da copiare (link messo su Notion)."""
    import html as _h
    n = len(s["carosello"])
    slide = "".join(f'<figure><img src="{i}.jpg" alt="Slide {i}" loading="lazy"><a href="{i}.jpg" download>Scarica slide {i}</a></figure>'
                    for i in range(1, n + 1))
    didas = _h.escape(t.get("didascalia") or "")
    (cartella / "index.html").write_text(f"""<!doctype html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Carosello Adolos</title><style>
body{{margin:0;font-family:system-ui,sans-serif;background:#1f0709;color:#fff;padding:20px}}
h1{{font-size:20px;margin:0 0 6px}}p{{color:#f3cfcf;margin:0 0 18px}}
.g{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}}
figure{{margin:0}}img{{width:100%;border-radius:8px;display:block}}
a{{display:block;margin-top:6px;color:#ffd400;font-weight:700;text-decoration:none}}
textarea{{width:100%;min-height:180px;margin-top:18px;border-radius:8px;padding:10px;font:15px system-ui;box-sizing:border-box}}
button{{margin-top:8px;padding:10px 16px;border:0;border-radius:8px;background:#d3202b;color:#fff;font-weight:700}}
</style></head><body><h1>{_h.escape(t.get('titolo') or s['titolo'])}</h1>
<p>{n} slide, formato 1080×1350. Sul telefono: tieni premuto su un'immagine e scegli "Salva".</p>
<div class="g">{slide}</div>
{f'<textarea id="d" readonly>{didas}</textarea><button onclick="navigator.clipboard.writeText(document.getElementById(&quot;d&quot;).value);this.textContent=&quot;Copiata&quot;">Copia la didascalia</button>' if didas else ''}
</body></html>""", encoding="utf-8")


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
            info = json.loads(meta.read_text())
            if info["impronta"] == imp:
                s["carosello"] = [f"social/{s['id']}/{i}.jpg" for i in range(1, int(info.get("slide", 5)) + 1)]
                continue
        except Exception:
            pass
        cartella.mkdir(parents=True, exist_ok=True)
        for vecchia in cartella.glob("*.jpg"):
            vecchia.unlink()
        immagini = carosello(s, t, PAESI, CONT_DI)
        for i, img in enumerate(immagini, 1):
            img.save(cartella / f"{i}.jpg", "JPEG", quality=90, optimize=True, progressive=False)
        meta.write_text(json.dumps({"impronta": imp, "slide": len(immagini),
                                    "creato": datetime.now(timezone.utc).isoformat()}))
        s["carosello"] = [f"social/{s['id']}/{i}.jpg" for i in range(1, len(immagini) + 1)]
        _pagina_carosello(cartella, s, t)
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
        if s.get("carosello") and sito and s["id"] in st["notion"] and s["id"] not in st.setdefault("caroselli_v2", []):
            try:
                redazione.aggiorna_scheda(st["notion"][s["id"]], {"Carosello": f"{sito}/social/{s['id']}/"})
                st["caroselli_v2"].append(s["id"])
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
