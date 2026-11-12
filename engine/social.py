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


def _sfondo_foto(percorso):
    """Foto a tutto schermo con il velo rosso Adolos sopra (come nei post @adolos.it)."""
    from PIL import Image, ImageDraw
    foto = Image.open(percorso).convert("RGB")
    sc = max(W / foto.width, H / foto.height)
    foto = foto.resize((int(foto.width * sc) + 1, int(foto.height * sc) + 1), Image.LANCZOS)
    x0, y0 = (foto.width - W) // 2, max(0, (foto.height - H) // 3)
    foto = foto.crop((x0, y0, x0 + W, y0 + H))
    velo = Image.new("RGB", (W, H), ROSSO_SCURO)
    img = Image.blend(foto, velo, 0.62)
    # più scuro in basso, dove c'è il testo
    scuro = Image.new("L", (W, H), 0)
    ds = ImageDraw.Draw(scuro)
    for i in range(H):
        ds.line([(0, i), (W, i)], fill=int(150 * max(0, (i - H * 0.35) / (H * 0.65))))
    img = Image.composite(Image.new("RGB", (W, H), BORDEAUX), img, scuro)
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


# ---------------------------------------------------------------- stile A "Prima pagina" (novembre 2026)
# Carta chiara, nero, una parola evidenziata in giallo, α rossa. In basso sempre la barra "Chi ne parla":
# un quadratino per testata. Regole complete nella skill adolos-stile.
INK_A = (17, 17, 17)
ROSSO_TESTO = (179, 21, 31)        # rosso più scuro: si legge bene sul fondo carta
ROSSO_CHIARO = (255, 74, 85)       # α sul fondo nero
GRIGIO_A = (95, 90, 84)
CARTA_SCURA = (216, 210, 200)
MARGINE = 72
NEWSREADER = RADICE / "site" / "assets" / "fonts" / "newsreader.woff2"
NEWSREADER_CORSIVO = RADICE / "site" / "assets" / "fonts" / "newsreader-italic.woff2"
STRETTO_A = 0.70                   # i titoli sono Archivo 900 stretto al 70%


def _news(size, peso=400, corsivo=False):
    """Newsreader (il carattere di testo del sito). Se manca, Lora."""
    from PIL import ImageFont
    try:
        f = ImageFont.truetype(str(NEWSREADER_CORSIVO if corsivo else NEWSREADER), size)
        try:
            f.set_variation_by_axes([peso])
        except Exception:
            pass
        return f
    except Exception:
        return _f("Lora-Italic.ttf" if corsivo else ("Lora-Bold.ttf" if peso >= 600 else "Lora-Regular.ttf"), size)


def _spaziato(d, x, y, testo, font, colore, spazio=3):
    """Scrive con un po' d'aria tra le lettere (etichette in maiuscolo). Restituisce la x finale."""
    for c in testo:
        d.text((x, y), c, font=font, fill=colore)
        x += d.textlength(c, font=font) + spazio
    return x


def _largo_spaziato(d, testo, font, spazio=3):
    return sum(d.textlength(c, font=font) + spazio for c in testo)


def _parola_forte(parole):
    """Quale parola del titolo evidenziare: l'ultima con un numero, altrimenti l'ultima parola lunga."""
    for i in range(len(parole) - 1, -1, -1):
        if any(c.isdigit() for c in parole[i]):
            return i
    for i in range(len(parole) - 1, -1, -1):
        if len(parole[i].strip(".,:;!?«»\"'")) >= 4:
            return i
    return len(parole) - 1


def _titolo_a(img, d, testo, x, y, larghezza, altezza, evidenzia=None, colore=INK_A, size=212, min_size=84,
              interlinea=0.9, maiuscolo=True, peso=900, stretto=STRETTO_A, colore_evid=GIALLO):
    """Titolo spesso e stretto che si rimpicciolisce finché ci sta. 'evidenzia' = indice della parola con il
    fondo giallo (None = nessuna). Restituisce la y sotto l'ultima riga."""
    parole = (testo.upper() if maiuscolo else testo).split()
    while True:
        font = _arch(size, peso)
        spazio = d.textlength(" ", font=font) * stretto
        righe, riga, largo = [], [], 0
        for i, p in enumerate(parole):
            w = d.textlength(p, font=font) * stretto
            if riga and largo + spazio + w > larghezza:
                righe.append(riga)
                riga, largo = [], 0
            largo += (spazio if riga else 0) + w
            riga.append((i, p, w))
        if riga:
            righe.append(riga)
        piu_larga = max((w for r in righe for _, _, w in r), default=0)
        if (len(righe) * size * interlinea <= altezza and piu_larga <= larghezza) or size <= min_size:
            break
        size -= 6
    _, alto, _, basso = font.getbbox("H")
    for r in righe:
        cx = x
        for i, p, w in r:
            if evidenzia is not None and i == evidenzia:
                d.rectangle((cx - 12, y + alto - size * 0.07, cx + w + 12, y + basso + size * 0.07), fill=colore_evid)
                _scrivi_stretto(img, cx, y, p, font, INK_A, stretto)
            else:
                _scrivi_stretto(img, cx, y, p, font, colore, stretto)
            cx += w + spazio
        y += size * interlinea
    return y + size * 0.12


def _testo_a(d, testo, x, y, larghezza, font, colore, interlinea=1.22, max_righe=None):
    righe = _a_capo(d, testo, font, larghezza)
    if max_righe and len(righe) > max_righe:
        righe = righe[:max_righe]
        righe[-1] = righe[-1].rstrip(" ,;:") + "…"
    for r in righe:
        d.text((x, y), r, font=font, fill=colore)
        y += font.size * interlinea
    return y


def _testa_a(d, kicker, scuro=False):
    """Riga in alto: etichetta a sinistra, α a destra, filetto spesso sotto."""
    f, k = _arch(30, 800), kicker.upper()
    while _largo_spaziato(d, k, f) > W - 2 * MARGINE - 130 and " " in k:      # non deve toccare la α
        k = k.rsplit(" ", 1)[0].rstrip(",;:")
    _spaziato(d, MARGINE, 84, k, f, GIALLO if scuro else ROSSO_TESTO)
    d.text((W - MARGINE, 30), "α", font=_f("DejaVuSerif-BoldItalic.ttf", 104), fill=ROSSO_CHIARO if scuro else ROSSO, anchor="rt")
    d.rectangle((MARGINE, 164, W - MARGINE, 170), fill=CARTA if scuro else INK_A)


def _scorri(d, colore):
    # la freccia con DejaVu: Archivo non ha il carattere →
    d.text((W - MARGINE, H - 84), "→", font=_f("DejaVuSerif-BoldItalic.ttf", 30), fill=colore, anchor="rm")
    d.text((W - MARGINE - 42, H - 84), "Scorri", font=_arch(26, 800), fill=colore, anchor="rm")


def _piede_a(d, sinistra, destra=None, scuro=False):
    c = CARTA if scuro else INK_A
    d.rectangle((MARGINE, H - 132, W - MARGINE, H - 130), fill=c)
    d.text((MARGINE, H - 84), sinistra, font=_arch(26, 600), fill=c, anchor="lm")
    if destra:
        d.text((W - MARGINE, H - 84), destra, font=_arch(26, 800), fill=c, anchor="rm")
    else:
        _scorri(d, c)


def _barra_chi_ne_parla(d, n_test, n_paesi):
    """Il segno fisso di Adolos sulla copertina: un quadratino per testata (al massimo 14 disegnati)."""
    d.rectangle((MARGINE, H - 132, W - MARGINE, H - 130), fill=INK_A)
    x = _spaziato(d, MARGINE, H - 100, "CHI NE PARLA", _arch(26, 800), INK_A, 2) + 16
    for _ in range(min(n_test, 14)):
        d.rectangle((x, H - 99, x + 28, H - 71), fill=INK_A)
        x += 34
    riga = f"{n_test} {'testata' if n_test == 1 else 'testate'} · {n_paesi} {'paese' if n_paesi == 1 else 'paesi'}"
    if x + 14 + d.textlength(riga, font=_arch(26, 600)) < W - MARGINE - 150:
        d.text((x + 14, H - 84), riga, font=_arch(26, 600), fill=INK_A, anchor="lm")
    _scorri(d, INK_A)
    return riga


_RE_NUMERO = None


def _numero_forte(frase):
    """Se la frase contiene un dato con unità (1.170 euro, 48%, 3 miliardi) lo restituisce per scriverlo grande."""
    global _RE_NUMERO
    import re
    if _RE_NUMERO is None:
        _RE_NUMERO = re.compile(r"(\d[\d.,]*)\s?(€|euro|%|per cento|miliardi|milioni|mila)\b", re.I)
    m = _RE_NUMERO.search(frase.replace("%", "% "))
    if not m:
        return None
    unita = {"euro": "€", "per cento": "%"}.get(m.group(2).lower(), m.group(2).lower())
    return f"{m.group(1)}{'' if unita == '%' else ' '}{unita}".upper()


def _foto_riquadro(img, percorso, x, y, w, h):
    """Foto ritagliata nel riquadro, a colori e senza filtri (licenza libera, con il credito scritto sotto)."""
    from PIL import Image
    foto = Image.open(percorso).convert("RGB")
    sc = max(w / foto.width, h / foto.height)
    foto = foto.resize((int(foto.width * sc) + 1, int(foto.height * sc) + 1), Image.LANCZOS)
    x0, y0 = (foto.width - w) // 2, max(0, (foto.height - h) // 3)
    img.paste(foto.crop((x0, y0, x0 + w, y0 + h)), (x, y))


def carosello(s, testi, nomi_paesi, cont_di):
    """Disegna il carosello nello stile A "Prima pagina". Restituisce la lista di immagini PIL.
    Copertina + una slide per ogni fatto + "Chi ne parla" + fonti. Niente attendibilità: resta su Notion."""
    from PIL import Image, ImageDraw
    titolo = testi.get("titolo") or s["titolo"]
    punti = testi.get("punti") or [p.strip() + "." for p in testi["sintesi"].split(". ") if len(p.strip()) > 20][:4]
    punti = [p for p in punti if p][:4]
    paesi = s.get("paesi", [])
    testate = _testate_uniche(s)
    n_test = max(s.get("n_fonti", 0), len(testate))
    tot = 1 + len(punti) + 2
    larg = W - 2 * MARGINE
    slide = []

    # 1. copertina: etichetta, titolo con la parola forte in giallo, una frase, barra "Chi ne parla"
    img = Image.new("RGB", (W, H), CARTA)
    d = ImageDraw.Draw(img)
    parti = _divide_titolo(titolo)
    kicker = parti[0].rstrip(":") if len(parti) == 2 else (s.get("sezione") or "Notizie")
    frase = parti[-1]
    _testa_a(d, kicker)
    y = 214
    if s.get("punto_cieco") == "italia":
        f = _arch(30, 800)
        testo = "IL MONDO NE PARLA, L'ITALIA NO"
        d.rectangle((MARGINE, y, MARGINE + d.textlength(testo, font=f) + 36, y + 56), fill=GIALLO)
        d.text((MARGINE + 18, y + 28), testo, font=f, fill=INK_A, anchor="lm")
        y += 92
    foto = testi.get("_immagine") or {}
    if foto.get("file"):
        try:
            _foto_riquadro(img, foto["file"], MARGINE, y, larg, 390)
            if foto.get("credito"):
                d.text((MARGINE, y + 400), foto["credito"][:110], font=_arch(19, 500), fill=GRIGIO_A)
            y += 446
        except Exception:
            foto = {}
    sotto = (testi.get("sintesi") or "").split(". ")[0].strip().rstrip(".") + "."
    sotto = sotto if 25 <= len(sotto) <= 170 else ""
    fondo = H - 170
    riserva = 250 if sotto else 0
    parole = frase.split()
    y_fine = _titolo_a(img, d, frase, MARGINE, y, larg, fondo - y - riserva, evidenzia=_parola_forte(parole),
                       size=150 if foto.get("file") else 212)
    if sotto and y_fine + 150 <= fondo:
        _testo_a(d, sotto, MARGINE, y_fine + 26, larg, _news(48), INK_A, 1.2, max_righe=max(1, int((fondo - y_fine - 30) // 58)))
    riga = _barra_chi_ne_parla(d, n_test, len(paesi))
    slide.append(img)

    # 2. un fatto per slide: se c'è un dato con unità, il numero va grande e rosso
    for i, p in enumerate(punti, 1):
        img = Image.new("RGB", (W, H), CARTA)
        d = ImageDraw.Draw(img)
        _testa_a(d, f"I fatti · {i} di {len(punti)}")
        numero = _numero_forte(p)
        if numero and len(numero) <= 14:
            y = _titolo_a(img, d, numero, MARGINE, 236, larg, 360, colore=ROSSO, size=380, min_size=150, interlinea=0.86)
            _testo_a(d, p, MARGINE, y + 30, larg, _news(58), INK_A, 1.18, max_righe=9)
        else:
            _titolo_a(img, d, p, MARGINE, 250, larg, H - 250 - 190, size=124, min_size=54, interlinea=1.04,
                      maiuscolo=False, peso=800, stretto=0.86)
        _piede_a(d, f"{1 + i}/{tot}")
        slide.append(img)

    # 3. chi ne parla (il tratto che ci distingue), su fondo nero
    img = Image.new("RGB", (W, H), INK_A)
    d = ImageDraw.Draw(img)
    _testa_a(d, "Chi ne parla", scuro=True)
    y = _titolo_a(img, d, riga.replace(" · ", ", "), MARGINE, 222, larg, 380, colore=CARTA, size=190, min_size=100)
    conti = {}
    for p in paesi:
        c = cont_di.get(p, "Altro")
        conti[c] = conti.get(c, 0) + 1
    y += 30
    fondo = H - (330 if conti else 170)
    mostrate = testate[:max(1, int((fondo - y - 50) // 70))]
    for f in mostrate:
        d.line([(MARGINE, y), (W - MARGINE, y)], fill=(90, 86, 80), width=2)
        d.text((MARGINE, y + 14), f["fonte"][:34], font=_arch(36, 700), fill=CARTA)
        d.text((W - MARGINE, y + 17), nomi_paesi.get(f["paese"], f["paese"])[:22], font=_arch(32, 400), fill=CARTA_SCURA, anchor="ra")
        y += 70
    d.line([(MARGINE, y), (W - MARGINE, y)], fill=(90, 86, 80), width=2)
    resto = n_test - len(mostrate)
    if resto > 0:
        d.text((MARGINE, y + 12), f"e {'un' + chr(39) + 'altra testata' if resto == 1 else f'altre {resto} testate'}",
               font=_news(32, corsivo=True), fill=CARTA_SCURA)
    if conti:
        y0 = H - 290
        _spaziato(d, MARGINE, y0, "DA DOVE ARRIVA", _arch(26, 800), GIALLO, 2)
        x, totale = MARGINE, sum(conti.values())
        tinte = [(GIALLO, INK_A), (CARTA, INK_A), (ROSSO_CHIARO, INK_A), (150, 146, 140), (90, 86, 80)]
        for k, (c, n) in enumerate(sorted(conti.items(), key=lambda kv: -kv[1])):
            w = int(larg * n / totale)
            tinta = tinte[k % 5]
            fondo_t, testo_t = tinta if isinstance(tinta[0], tuple) else (tinta, INK_A if k < 4 else CARTA)
            d.rectangle((x, y0 + 46, x + w - 4, y0 + 100), fill=fondo_t)
            if w > 170:
                d.text((x + 14, y0 + 73), f"{c} {n}"[:int(w / 15)], font=_arch(24, 800), fill=testo_t, anchor="lm")
            x += w
    _piede_a(d, f"{tot - 1}/{tot}", scuro=True)
    slide.append(img)

    # 4. fonti e chiusura
    img = Image.new("RGB", (W, H), CARTA)
    d = ImageDraw.Draw(img)
    _testa_a(d, "Fonti")
    chiusa = "Tutti i link agli articoli su adolos.it"
    y = _titolo_a(img, d, chiusa, MARGINE, 222, larg, 520, evidenzia=len(chiusa.split()) - 1, size=170, min_size=90)
    nomi = [f["fonte"] for f in testate[:8]]
    if n_test > len(nomi):
        nomi.append(f"e altre {n_test - len(nomi)}")
    y = _testo_a(d, "Ne parlano: " + ", ".join(nomi) + ".", MARGINE, y + 34, larg, _news(40), INK_A, 1.25, max_righe=6)
    nota = "Testo preparato con l'aiuto dell'AI e verificato dalla redazione."   # regola 9: sempre dichiarato
    y_nota = H - 250
    if foto.get("credito"):
        _testo_a(d, "Foto di copertina: " + foto["credito"], MARGINE, y_nota - 74, larg, _news(26, corsivo=True), GRIGIO_A, 1.25, max_righe=2)
    _testo_a(d, nota, MARGINE, y_nota, larg, _news(30, corsivo=True), GRIGIO_A, 1.25, max_righe=2)
    _piede_a(d, f"{tot}/{tot}", "adolos.it")
    slide.append(img)
    return slide


VERSIONE_GRAFICA = 4      # cambiarla ridisegna tutti i caroselli (4 = stile A "Prima pagina")


def _impronta(s, testi):
    base = json.dumps([VERSIONE_GRAFICA, testi.get("titolo"), testi.get("sintesi"), testi.get("punti"), s["n_fonti"],
                       s.get("punto_cieco"), (testi.get("_immagine") or {}).get("credito")], ensure_ascii=False)
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


def genera_caroselli(storie, gruppi=None):
    """Disegna i caroselli delle notizie approvate (solo se mancano o se il testo è cambiato)."""
    from sito import CONT_DI
    from adolos import PAESI
    CARTELLA.mkdir(parents=True, exist_ok=True)
    fatti = []
    try:
        import sintesi
        bozze_ai = sintesi.bozze()
    except Exception:
        bozze_ai = {}
    for s in storie:
        t = s.get("sintesi")
        if not t or not t.get("sintesi"):
            continue
        cartella = CARTELLA / s["id"]
        meta = cartella / "info.json"
        try:
            import immagini
            scena = (bozze_ai.get(s["id"]) or {}).get("scena_immagine", "")
            foto = immagini.per_storia(s, t.get("titolo") or s["titolo"], (gruppi or {}).get(s["id"], []), scena)
        except Exception as e:
            print("Immagine non cercata:", str(e)[:120])
            foto = None
        if foto:
            t = {**t, "_immagine": foto}
            s["immagine"] = {"credito": foto["credito"], "tipo": foto["tipo"]}
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
    """Didascalia Instagram con i crediti della foto (obbligatori per le licenze CC BY e per le immagini AI)."""
    testo = _didascalia_base(s, t)
    cred = (s.get("immagine") or {}).get("credito")
    if cred and cred not in testo:
        testo = testo.rstrip() + "\n\n" + cred + "."
    return testo[:2190]


def _didascalia_base(s, t):
    if t.get("didascalia") and t["didascalia"] != s.get("didascalia"):
        return t["didascalia"]          # scritta o corretta dalla redazione su Notion
    nomi = list(dict.fromkeys(f["fonte"] for f in sorted(s["fonti"], key=lambda f: (f["paese"] != "IT", not _latino(f["fonte"])))
                              if f.get("tipo") != "social"))[:4]
    altre = s["n_fonti"] - len(nomi)
    fonti = ", ".join(nomi) + (f" e altre {altre} testate" if altre > 0 else "")
    nota = "Testo preparato con l'aiuto dell'AI e verificato dalla redazione."
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
                extra = {"Immagine": "Copertina: " + s["immagine"]["credito"] + ". Controllare che la foto sia quella giusta "
                         "prima di spuntare Pubblica su Instagram."} if s.get("immagine") else {}
                redazione.aggiorna_scheda(st["notion"][s["id"]], {"Carosello": f"{sito}/social/{s['id']}/", **extra})
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
