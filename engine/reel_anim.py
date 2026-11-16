"""
ADOLOS – reel animato, stile Adolos "adolos-reel-v2"
====================================================
Il montaggio del reel disegnato fotogramma per fotogramma (Pillow) e mandato direttamente a ffmpeg.
Lo stile è UNO: colori, caratteri, posizioni e regole stanno in engine/stile_reel.py (qui non si scrive nessun colore
né nome di carattere: lo controlla `stile_reel.controlla()` prima di ogni video).

Per ogni scena del copione si sceglie l'elemento centrale dal contenuto (niente di inventato, solo quello che c'è):
  - prima scena                                      -> globo 3D (Blender) con i protagonisti e il luogo, o la foto
  - "Numero: ..." nel copione, o un numero con unità -> contatore giallo che sale fino al dato
  - un anno passato (1945)                           -> linea del tempo che si riempie fino a oggi
  - ("ne parlano", "testate": scena spenta, vedi ST.SCENA_TESTATE) -> globo con i paesi delle testate che si accendono
  - altrimenti                                       -> la foto con licenza libera in un riquadro che si muove
Le parole della voce stanno in alto, a pezzi di 2-4 parole, sottili; la parola chiave in grassetto, i numeri in giallo.
Se la scena ha una "Fonte", sotto compare "Secondo <testata>". Chiusura: "Segui @adolos.it", fonti, nota AI, crediti.
Restano sempre scritti "Voce generata con AI" e, nella chiusura, i crediti di foto e mappa.

Usato da engine/reel.py quando in fonti.json > reel_voce > stile_video c'è "infografica".
"""

import datetime
import functools
import math
import os
import re
import subprocess

from PIL import Image, ImageDraw, ImageFilter

import reel
import social
import stile_reel as ST

W, H, FPS, M = ST.LARGHEZZA, ST.ALTEZZA, ST.FPS, ST.MARGINE
ANNO = re.compile(r"\b(1[89]\d\d|20[0-4]\d)\b")
FONTI_RE = re.compile(r"\b(ne parla\w*|testat\w+|giornali|riportano|riporta|fonti|media)\b", re.I)


@functools.lru_cache(maxsize=512)
def _f(size, peso=ST.PESO_TITOLO):
    return social._arch(int(size), peso)


def _e(x):                           # parte veloce e rallenta
    x = min(1.0, max(0.0, x))
    return 1 - (1 - x) ** 3


def _salto(x):                       # arriva, supera un poco e torna (effetto "pop")
    x = min(1.0, max(0.0, x))
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def _nomi_paesi():
    try:
        import adolos
        return adolos.PAESI
    except Exception:
        return {}


# ---------------------------------------------------------------- fondi
def _velo(img, alto=0.65, basso=0.92, da=0.28):
    """Scurisce in alto (marchio e parole) e dalla metà in giù, senza coprire il centro."""
    w, h = img.size
    m = Image.new("L", (1, h))
    for y in range(h):
        b = min(1.0, max(0.0, (y / h - da) / 0.40)) ** 1.1 * basso
        a = max(0.0, 1 - y / (h * 0.2)) * alto
        m.putpixel((0, y), int(255 * max(a, b)))
    return Image.composite(Image.new("RGB", img.size, ST.NERO), img, m.resize(img.size))


@functools.lru_cache(maxsize=16)
def _maschera_veli(w, h, alto, basso):
    m = Image.new("L", (1, h))
    for y in range(h):
        a = max(0.0, 1 - y / (h * 0.24)) * alto
        b = min(1.0, max(0.0, (y / h - 0.70) / 0.26)) * basso
        m.putpixel((0, y), int(255 * max(a, b)))
    return m.resize((w, h))


def _veli(img, alto=0.72, basso=0.5):
    """Mappe e globo: scurisce solo la fascia in alto (parole) e quella in basso (fonte), il centro resta libero."""
    return Image.composite(Image.new("RGB", img.size, ST.NERO), img.convert("RGB"), _maschera_veli(img.width, img.height, alto, basso))


def _pan(img, t, durata, verso):
    """Ritaglio W x H che scorre piano dentro un'immagine un po' più grande (niente ridimensionamento: veloce)."""
    k = min(1.0, max(0.0, t / max(durata, 0.1)))
    dx, dy = img.width - W, img.height - H
    x, y = [(dx * k, dy / 2), (dx * (1 - k), dy / 2), (dx / 2, dy * k), (dx / 2, dy * (1 - k))][verso % 4]
    return img.crop((int(x), int(y), int(x) + W, int(y) + H))


def _carta_sorgente(base, i):
    """Ritaglio della foto per il riquadro centrale: ogni scena prende una parte diversa, così sembrano inquadrature."""
    x0, y0, x1, y1 = ST.RIQUADRO_FOTO
    cw, ch = x1 - x0, y1 - y0
    sw, sh = int(cw * 1.16), int(ch * 1.16)
    rw = base.width
    rh = int(rw * sh / sw)
    ys = [0.30, 0.05, 0.50, 0.18][i % 4] * max(0, base.height - rh)
    pezzo = base.crop((0, int(ys), rw, int(ys) + rh)).resize((sw, sh), Image.LANCZOS)
    maschera = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(maschera).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=30, fill=255)
    return pezzo, maschera


# ---------------------------------------------------------------- pezzi fissi e parole
def _testa(img, etichetta):
    """Marchio, nota sulla voce AI ed etichetta rossa: uguali su tutte le scene."""
    d = ImageDraw.Draw(img)
    social._marchio(d, M, ST.Y_MARCHIO)
    d.text((W - M, ST.Y_MARCHIO + 42), ST.SCRITTA_VOCE, font=_f(24, ST.PESO_MEDIO), fill=ST.GRIGIO, anchor="rm")
    _etichetta_rossa(d, M, ST.Y_ETICHETTA, etichetta)


def _etichetta_rossa(d, x, y, testo, size=32):
    """Etichetta rossa piena col testo maiuscolo (la stessa dei caroselli), nel carattere del reel."""
    testo = testo.upper()
    f = _f(size, ST.PESO_FORTE)
    while d.textlength(testo, font=f) > W - 2 * M - 60 and " " in testo:
        testo = testo.rsplit(" ", 1)[0].rstrip(",;:")
    lw, h = d.textlength(testo, font=f), int(size * 1.7)
    d.rounded_rectangle((x, y, x + lw + 52, y + h), radius=10, fill=ST.ROSSO)
    d.text((x + 26, y + h / 2), testo, font=f, fill=ST.BIANCO, anchor="lm")


def _didascalia(fr, parole, dt, forti, durata_pezzo=0.8):
    """Le parole della voce, in alto: sottili, la parola chiave in grassetto, i numeri in giallo. Ogni parola salta
    fuori al suo turno, con un piccolo "pop"."""
    def peso(p):
        pulita = p.strip(".,:;!?«»\"'()").lower()
        return ST.PESO_FORTE if (any(c.isdigit() for c in p) or pulita in forti) else ST.PESO_SOTTILE
    d0 = ImageDraw.Draw(fr)
    size = ST.DIM_DIDASCALIA
    while True:
        spazio = d0.textlength(" ", font=_f(size, ST.PESO_SOTTILE))
        larga = sum(d0.textlength(p, font=_f(size, peso(p))) for p in parole) + spazio * (len(parole) - 1)
        if larga <= W - 2 * M or size <= 44:
            break
        size -= 4
    alt = int(size * 2.2)
    strato = Image.new("RGBA", (W, alt), ST.TRASPARENTE)
    ombra = Image.new("RGBA", (W, alt), ST.TRASPARENTE)
    ds, dd = ImageDraw.Draw(ombra), ImageDraw.Draw(strato)
    passo = min(0.16, max(0.05, durata_pezzo / (len(parole) + 1)))
    x = (W - larga) / 2
    for j, p in enumerate(parole):
        larg = d0.textlength(p, font=_f(size, peso(p)))
        tj = dt - j * passo
        if tj >= 0:
            s_pop = 0.7 + 0.3 * _salto(tj / 0.2)
            f = _f(max(20, round(size * s_pop / 2) * 2), peso(p))
            colore = ST.GIALLO if any(c.isdigit() for c in p) else ST.BIANCO
            cx = x + larg / 2
            sposta = (1 - _e(tj / 0.18)) * 22
            ds.text((cx, alt / 2 + 5 + sposta), p, font=f, fill=ST.OMBRA, anchor="mm")
            dd.text((cx, alt / 2 + sposta), p, font=f, fill=colore, anchor="mm")
        x += larg + spazio
    ombra = ombra.filter(ImageFilter.GaussianBlur(6))
    strato = Image.alpha_composite(ombra, strato)
    fr.alpha_composite(strato, dest=(0, int(ST.Y_DIDASCALIA - alt / 2)))


def _riga_fonte(fr, t, testo):
    """"Secondo El Mundo" (una testata) o "Fonti: Casa Bianca, Cremlino" (più d'una), sotto la scena."""
    k = _e((t - 0.3) / 0.3)
    if k <= 0 or not testo:
        return
    multipla = ("," in testo) or (" e " in testo)
    s = ("Fonti: " if multipla else "Secondo ") + testo
    strato = Image.new("RGBA", (W, 110), ST.TRASPARENTE)
    d = ImageDraw.Draw(strato)
    f = _f(42, ST.PESO_MEDIO)
    lw = d.textlength(s, font=f)
    d.line((W / 2 - lw / 2, 18, W / 2 + lw / 2, 18), fill=ST.GIALLO, width=4)
    d.text((W / 2, 64), s, font=f, fill=ST.BIANCO, anchor="mm")
    strato.putalpha(strato.getchannel("A").point(lambda v: int(v * k)))
    fr.alpha_composite(strato, dest=(0, ST.Y_FONTE - 30))


# ---------------------------------------------------------------- elementi centrali
def _valore(numero):
    """"1.170 €" -> (1170, 0, "€") · "2,5 MILIARDI" -> (2.5, 1, "MILIARDI") · "11.000" -> (11000, 0, "")."""
    m = re.match(r"([\d.,]+)\s?(.*)", numero)
    cifre, unita = m.group(1), m.group(2).strip()
    if "," in cifre:
        intero, dec = cifre.replace(".", "").split(",", 1)
        return float(intero + "." + dec), len(dec), unita
    return float(cifre.replace(".", "")), 0, unita


def _scrivi_numero(v, nd, unita):
    s = f"{v:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{s}{'' if unita == '%' else ' '}{unita}".strip()


def _etichetta_numero(voce, schermo):
    """Le parole dopo il numero ("in dieci anni"); la scritta della scena è già in alto, non si ripete."""
    m = re.search(r"\d[\d.,]*\s?(?:%|per cento|euro|€|miliardi|milioni|mila|voti|punti)?", voce, re.I)
    dopo = re.sub(r"[^\w\sàèéìòù']", "", voce[m.end():] if m else "").split()[:5]
    testo = " ".join(dopo)
    return "" if testo.lower() == (schermo or "").lower() else testo


def _contatore(d, t, numero, etichetta):
    v, nd, unita = _valore(numero)
    k = _e((t - 0.15) / 1.2)
    if v <= 99 and unita:                       # numero piccolo con unità: un anello che si riempie mentre il numero sale
        cx, cy, r = W / 2, 1060, 215
        d.ellipse((cx - r - 24, cy - r - 24, cx + r + 24, cy + r + 24), fill=ST.NERO + (200,))
        d.arc((cx - r, cy - r, cx + r, cy + r), 0, 360, fill=ST.LINEA, width=16)
        if k > 0:
            d.arc((cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * k, fill=ST.GIALLO, width=16)
        pop = 0.85 + 0.15 * _salto(t / 0.35)
        d.text((cx, cy - 25), _scrivi_numero(v * k, nd, ""), font=_f(round(250 * pop)), fill=ST.GIALLO, anchor="mm")
        d.text((cx, cy + 100), unita.upper(), font=_f(54, ST.PESO_FORTE), fill=ST.BIANCO, anchor="mm")
        if k >= 1:                                # all'arrivo: un'onda che si allarga
            q = min(1.0, (t - 1.35) / 0.6)
            if 0 <= q < 1:
                rr = r + 30 + 130 * q
                d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=ST.GIALLO + (int(255 * (1 - q)),), width=6)
        if etichetta and t > 0.3:
            d.text((W / 2, cy + r + 70), etichetta.upper()[:44], font=_f(40, ST.PESO_FORTE), fill=ST.BIANCO, anchor="mm",
                   stroke_width=4, stroke_fill=ST.NERO)
        return
    testo = _scrivi_numero(v * k if k < 1 else v, nd, unita)
    finale = _scrivi_numero(v, nd, unita)
    size = 250
    while d.textlength(finale, font=_f(size)) > W - 2 * M and size > 90:
        size -= 10
    size = round(size * (0.8 + 0.2 * _salto(t / 0.35)))
    d.text((W / 2, ST.Y_NUMERO), testo, font=_f(size), fill=ST.GIALLO, anchor="mm", stroke_width=5, stroke_fill=ST.NERO)
    if etichetta and t > 0.3:
        d.text((W / 2, ST.Y_NUMERO + size * 0.62 + 30), etichetta.upper()[:44], font=_f(40, ST.PESO_FORTE),
               fill=ST.BIANCO, anchor="mm", stroke_width=4, stroke_fill=ST.NERO)


def _linea_tempo(d, t, anno, oggi, etichetta):
    y, x0, x1 = ST.Y_NUMERO - 40, M + 40, W - M - 40
    k = _e((t - 0.2) / 1.4)
    d.text((x0, y - 90), str(anno), font=_f(110), fill=ST.BIANCO, anchor="lm", stroke_width=4, stroke_fill=ST.NERO)
    d.text((x1, y - 90), str(oggi), font=_f(110), fill=ST.BIANCO, anchor="rm", stroke_width=4, stroke_fill=ST.NERO)
    d.line((x0, y, x1, y), fill=ST.LINEA, width=8)
    xk = x0 + (x1 - x0) * k
    d.line((x0, y, xk, y), fill=ST.GIALLO, width=12)
    d.ellipse((x0 - 14, y - 14, x0 + 14, y + 14), fill=ST.GIALLO)
    d.ellipse((xk - 20, y - 20, xk + 20, y + 20), fill=ST.GIALLO, outline=ST.NERO, width=4)
    n = round((oggi - anno) * k)
    d.text((W / 2, y + 190), f"{n} {'ANNO' if n == 1 else 'ANNI'}", font=_f(170), fill=ST.GIALLO, anchor="mm",
           stroke_width=4, stroke_fill=ST.NERO)
    if etichetta and t > 0.4:
        d.text((W / 2, y + 330), etichetta.upper()[:44], font=_f(40, ST.PESO_FORTE), fill=ST.BIANCO, anchor="mm",
               stroke_width=4, stroke_fill=ST.NERO)


def _conteggio(d, t, p, n_paesi, k, y=1150):
    """"24 TESTATE · DA 15 PAESI" e, se serve, l'etichetta del punto cieco italiano."""
    n_test = int(p.get("n_fonti") or len(p.get("fonti") or []))
    d.text((W / 2, y), f"{round(n_test * k)} {'TESTATA' if n_test == 1 else 'TESTATE'}", font=_f(130), fill=ST.GIALLO,
           anchor="mm", stroke_width=5, stroke_fill=ST.NERO)
    d.text((W / 2, y + 100), f"DA {n_paesi} {'PAESE' if n_paesi == 1 else 'PAESI'}", font=_f(56, ST.PESO_FORTE),
           fill=ST.BIANCO, anchor="mm", stroke_width=4, stroke_fill=ST.NERO)
    if p.get("punto_cieco") == "italia" and t > 0.9:
        testo = "PUNTO CIECO: NESSUNA TESTATA ITALIANA"
        f = _f(34)
        lw = d.textlength(testo, font=f)
        d.rounded_rectangle((W / 2 - lw / 2 - 20, y + 160, W / 2 + lw / 2 + 20, y + 216), radius=6, fill=ST.GIALLO)
        d.text((W / 2, y + 189), testo, font=f, fill=ST.NERO, anchor="mm")


def _griglia(d, t, p, nomi):
    """Senza mappa né globo: le testate come riquadri che compaiono uno alla volta."""
    fonti = p.get("fonti") or []
    n_test = int(p.get("n_fonti") or len(fonti))
    n_paesi = len(p.get("paesi") or []) or len({f.get("paese") for f in fonti})
    celle = fonti[:8]
    if n_test > len(celle):
        celle = celle + [{"fonte": f"+{n_test - len(celle)}", "paese": "+"}]
    cols, cw, ch, gap = 3, 280, 170, 22
    righe = math.ceil(len(celle) / cols)
    x0, y0 = (W - (cols * cw + (cols - 1) * gap)) / 2, 470
    passo = min(0.16, 1.1 / max(1, len(celle)))
    for j, c in enumerate(celle):
        k = _salto((t - 0.1 - j * passo) / 0.3)
        if k <= 0:
            continue
        r, col = divmod(j, cols)
        cx, cy = x0 + col * (cw + gap) + cw / 2, y0 + r * (ch + gap) + ch / 2
        s = 0.55 + 0.45 * k
        d.rounded_rectangle((cx - cw * s / 2, cy - ch * s / 2, cx + cw * s / 2, cy + ch * s / 2), radius=16,
                            fill=ST.CELLA, outline=ST.GIALLO, width=4)
        if k > 0.75:
            paese = c.get("paese") or ""
            nome_p = nomi.get(paese, paese).upper() if paese not in ("+", "WEB") else ("WEB" if paese == "WEB" else "")
            if nome_p:
                fp = _f(34)
                while d.textlength(nome_p, font=fp) > cw - 28 and fp.size > 20:
                    fp = _f(fp.size - 2)
                d.text((cx, cy - 26), nome_p, font=fp, fill=ST.GIALLO, anchor="mm")
            nome = c["fonte"]
            fn = _f(28, 700)
            if d.textlength(nome, font=fn) > cw - 28:
                while d.textlength(nome + "…", font=fn) > cw - 28 and len(nome) > 3:
                    nome = nome[:-1]
                nome = nome.rstrip() + "…"
            if paese == "+":
                d.text((cx, cy), nome, font=_f(64), fill=ST.GIALLO, anchor="mm")
            else:
                d.text((cx, cy + (24 if nome_p else 0)), nome, font=fn, fill=ST.BIANCO, anchor="mm")
    k = _e((t - 0.1) / (passo * len(celle) + 0.3))
    _conteggio(d, t, p, n_paesi, k, y=y0 + righe * (ch + gap) + 70)


def _carta(fr, d, t, durata, sorgente, verso):
    pezzo, maschera = sorgente
    k = _e(t / 0.4)
    dy = int((1 - k) * 90)
    x0, y0, x1, y1 = ST.RIQUADRO_FOTO
    cw, ch = maschera.size
    q = min(1.0, max(0.0, t / max(durata, 0.1)))
    mx, my = pezzo.width - cw, pezzo.height - ch
    x, y = (mx * q, my / 2) if verso % 2 == 0 else (mx * (1 - q), my * q)
    fr.paste(pezzo.crop((int(x), int(y), int(x) + cw, int(y) + ch)), (x0, y0 + dy), maschera)
    d.rounded_rectangle((x0, y0 + dy, x1, y1 + dy), radius=30, outline=ST.GIALLO, width=6)


def _parola(d, t, testo):
    testo = testo.upper()
    size = 130
    while d.textlength(testo, font=_f(size)) > W - 2 * M - 60 and size > 56:
        size -= 6
    f = _f(size)
    lw = d.textlength(testo, font=f)
    k = _e(t / 0.45)
    x0 = W / 2 - lw / 2 - 30
    d.rectangle((x0, 820 - size * 0.75, x0 + (lw + 60) * k, 820 + size * 0.75), fill=ST.GIALLO)
    if k > 0.6:
        d.text((W / 2, 820), testo, font=f, fill=ST.NERO, anchor="mm")


# ---------------------------------------------------------------- mappa piatta (se manca Blender) · engine/mappa.py
class _MappaFonti:
    """Mappa del mondo con i paesi delle testate che si accendono uno alla volta, con un punto e il nome."""

    def __init__(self, p, nomi, tela):
        import mappa
        fonti = p.get("fonti") or []
        codici = [c for c in dict.fromkeys(list(p.get("paesi") or []) + [f.get("paese") for f in fonti])
                  if c and mappa.esiste(c)]
        self.codici = codici[:12]
        self.quante = {c: sum(1 for f in fonti if f.get("paese") == c) for c in self.codici}
        self.nomi = {c: (nomi.get(c) or mappa._paesi()[c]["nome"]).upper() for c in self.codici}
        wc, hc = tela
        self.ox, self.oy = (wc - W) // 2, (hc - H) // 2
        v = mappa.vista_insieme(self.codici, wc, hc, 700 + self.oy)
        self.punti = [tuple(a - b for a, b in zip(v.xy(*mappa.punto_paese(c)), (self.ox, self.oy))) for c in self.codici]
        base = mappa.fondo(v).convert("RGBA")
        self.passi = []
        for j in range(len(self.codici) + 1):
            img = base if not j else Image.alpha_composite(base, mappa.strato_paesi(v, self.codici[:j], forte=False))
            self.passi.append(_veli(img.convert("RGB"), 0.75, 0.62).crop((self.ox, self.oy, self.ox + W, self.oy + H)))
        self.passo = min(0.22, 1.2 / max(1, len(self.codici)))

    def fondo(self, t):
        return self.passi[sum(1 for j in range(len(self.codici)) if t >= 0.15 + j * self.passo)]

    def disegna(self, d, t, p):
        occupati = []
        for j, (c, (x, y)) in enumerate(zip(self.codici, self.punti)):
            dt = t - 0.15 - j * self.passo
            if dt < 0:
                continue
            r = 9 + 4 * _salto(dt / 0.25)
            d.ellipse((x - r, y - r, x + r, y + r), fill=ST.GIALLO, outline=ST.NERO, width=3)
            if dt < 0.6:                                         # onda che si allarga quando il paese si accende
                q = dt / 0.6
                rr = 14 + 46 * q
                d.ellipse((x - rr, y - rr, x + rr, y + rr), outline=ST.GIALLO + (int(255 * (1 - q)),), width=3)
            testo = self.nomi[c] + (f" · {self.quante[c]}" if self.quante.get(c, 0) > 1 else "")
            f = _f(26, ST.PESO_FORTE)
            lw = d.textlength(testo, font=f) + 20
            lx = min(max(M - 30, x - lw / 2), W - M + 30 - lw)
            ly = y + 22
            while any(abs(ly - oy) < 40 and lx < ox + ow and ox < lx + lw for ox, oy, ow in occupati):
                ly += 42
            occupati.append((lx, ly, lw))
            d.rounded_rectangle((lx, ly, lx + lw, ly + 36), radius=6, fill=ST.CELLA + (230,))
            d.text((lx + lw / 2, ly + 18), testo, font=f, fill=ST.BIANCO, anchor="mm")
        n_paesi = len(p.get("paesi") or []) or len(self.codici)
        _conteggio(d, t, p, n_paesi, _e((t - 0.15) / (self.passo * max(1, len(self.codici)) + 0.2)))


# ---------------------------------------------------------------- mappa con telecamera che si muove, marcatori, scene speciali
class _SfondoMappa:
    """Mappa notturna disegnata più grande dello schermo. `inquadra` fa zoomare e spostare la telecamera piano piano
    (verso il luogo della scena, se c'è) e dice dove cade ogni punto (lon, lat) sullo schermo."""

    def __init__(self, img, vista):
        self.img, self.v = img, vista

    def inquadra(self, t, durata, punto=None):
        k = _e(min(1.0, t / max(durata, 0.1)))
        z = ST.ZOOM_DA + (ST.ZOOM_A - ST.ZOOM_DA) * k
        wc, hc = self.img.size
        w, h = W / z, H / z
        cx, cy = wc / 2, hc / 2
        if punto:
            px, py = self.v.xy(*punto)
            cx, cy = cx + (px - cx) * 0.6 * k, cy + (py - cy) * 0.6 * k
        else:
            cx += 40 * (k - 0.5)
        x0 = min(max(cx - w / 2, 0), wc - w)
        y0 = min(max(cy - h / 2, 0), hc - h)
        fr = self.img.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((W, H), Image.BILINEAR)

        def dove(lon, lat):
            px, py = self.v.xy(lon, lat)
            return (px - x0) * W / w, (py - y0) * H / h
        return fr, dove


def _marcatore(d, x, y, t, nome):
    """Il luogo della scena: un punto giallo che pulsa con onde che si allargano, e il nome."""
    pop = _salto(t / 0.3)
    for j in range(3):
        fase = (t * 0.8 + j / 3) % 1
        rr = 20 + 90 * fase
        d.ellipse((x - rr, y - rr, x + rr, y + rr), outline=ST.GIALLO + (int(230 * (1 - fase)),), width=4)
    r = 17 * pop
    d.ellipse((x - r, y - r, x + r, y + r), fill=ST.GIALLO, outline=ST.NERO, width=4)
    if pop > 0.6:
        d.text((x + 34, y), nome.upper(), font=_f(40, ST.PESO_FORTE), fill=ST.BIANCO, anchor="lm", stroke_width=5, stroke_fill=ST.NERO)


def _orbite(d, t):
    """Due costellazioni di satelliti in orbita attorno alla Terra: schema illustrativo, senza numeri."""
    cx, cy = W / 2, 930
    d.ellipse((cx - 150, cy - 150, cx + 150, cy + 150), fill=ST.CELLA, outline=ST.GIALLO, width=5)
    d.text((cx, cy), "TERRA", font=_f(30, ST.PESO_FORTE), fill=ST.GRIGIO, anchor="mm")
    anelli = [(330, 150, -20, ST.GIALLO, 11, 0.9, "AMAZON LEO"), (440, 215, 24, ST.BIANCO, 16, -0.6, "STARLINK")]
    for a, b, inclina, colore, n, vel, nome in anelli:
        fi = math.radians(inclina)
        pt = []
        for q in range(0, 360 + 1, 6):
            th = math.radians(q)
            pt.append((cx + a * math.cos(th) * math.cos(fi) - b * math.sin(th) * math.sin(fi),
                       cy + a * math.cos(th) * math.sin(fi) + b * math.sin(th) * math.cos(fi)))
        d.line(pt, fill=ST.LINEA, width=3)
        for j in range(n):
            th = math.radians(360 * j / n) + t * vel
            x = cx + a * math.cos(th) * math.cos(fi) - b * math.sin(th) * math.sin(fi)
            y = cy + a * math.cos(th) * math.sin(fi) + b * math.sin(th) * math.cos(fi)
            d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=colore, outline=ST.NERO, width=3)
    k = _e((t - 0.3) / 0.4)
    if k > 0:
        d.text((M, 1180), "AMAZON LEO", font=_f(44, ST.PESO_FORTE), fill=ST.GIALLO, anchor="lm", stroke_width=5, stroke_fill=ST.NERO)
        d.text((W - M, 1180), "STARLINK", font=_f(44, ST.PESO_FORTE), fill=ST.BIANCO, anchor="rm", stroke_width=5, stroke_fill=ST.NERO)
    d.text((W / 2, 1330), "schema illustrativo", font=_f(30, ST.PESO_MEDIO), fill=ST.GRIGIO, anchor="mm")


def _domanda(d, t):
    """La scena della domanda: un punto interrogativo che pulsa e fumetti che salgono (invito a commentare)."""
    pulsa = 1 + 0.06 * math.sin(t * 5)
    pop = 0.6 + 0.4 * _salto(t / 0.4)
    d.text((W / 2, 900), "?", font=_f(round(760 * pulsa * pop)), fill=ST.GIALLO, anchor="mm", stroke_width=6, stroke_fill=ST.NERO)
    for j, (x0, ritardo) in enumerate(((0.22, 0.0), (0.5, 0.35), (0.78, 0.7))):
        q = ((t * 0.55 + ritardo) % 1)
        x, y = W * x0, 1220 - 480 * q
        alfa = int(255 * min(1.0, q * 4) * (1 - q))
        d.rounded_rectangle((x - 70, y - 40, x + 70, y + 40), radius=26, outline=ST.BIANCO + (alfa,), width=5)
        for k2 in range(3):
            d.ellipse((x - 34 + 34 * k2 - 7, y - 7, x - 34 + 34 * k2 + 7, y + 7), fill=ST.BIANCO + (alfa,))
    d.text((W / 2, 1300), "SCRIVILO NEI COMMENTI", font=_f(48, ST.PESO_FORTE), fill=ST.BIANCO, anchor="mm", stroke_width=5, stroke_fill=ST.NERO)


# ---------------------------------------------------------------- clip del globo (Blender) letti fotogramma per fotogramma
class _Clip:
    def __init__(self, mp4):
        self.proc = subprocess.Popen([reel.FFMPEG, "-v", "error", "-i", str(mp4), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                     stdout=subprocess.PIPE)
        self.ultimo = Image.new("RGB", (W, H), ST.NERO)

    def fotogramma(self):
        b = self.proc.stdout.read(W * H * 3)
        if len(b) == W * H * 3:
            self.ultimo = Image.frombytes("RGB", (W, H), b)
        return self.ultimo

    def chiudi(self):
        try:
            self.proc.kill()
        except Exception:
            pass


# ---------------------------------------------------------------- suoni
def _con_effetti(wav, inizi, uscita):
    """Un "whoosh" leggero a ogni cambio di scena (rumore filtrato, fatto qui: niente file di altri)."""
    import numpy as np
    import soundfile as sf
    a, sr = sf.read(str(wav), dtype="float32")
    if a.ndim > 1:
        a = a.mean(axis=1)
    n = int(sr * 0.38)
    rumore = np.random.default_rng(7).standard_normal(n + 64).astype("float32")
    rumore = np.convolve(rumore, np.ones(48) / 48, mode="same")[:n]
    w = rumore * np.sin(np.linspace(0, np.pi, n)) ** 2
    w = w / (np.abs(w).max() + 1e-9) * 0.13
    for s in inizi:
        i0 = int(max(0.0, s - 0.16) * sr)
        pezzo = a[i0:i0 + n]
        pezzo += w[:len(pezzo)]
    sf.write(str(uscita), np.clip(a, -1, 1), sr)
    return uscita


# ---------------------------------------------------------------- montaggio
def rendi(p, righe, durate, tempi, foto, wav, uscita, lavoro):
    oggi = datetime.date.today()
    nomi = _nomi_paesi()
    scene = [r["voce"] for r in righe]
    schermi = [r["schermo"] for r in righe]
    fonti_scena = [r.get("fonte", "") for r in righe]
    parti = social._divide_titolo(p["titolo"])
    etichetta = p.get("etichetta") or (parti[0].rstrip(":") if len(parti) == 2 else (p.get("sezione") or "Notizie"))
    n_test = int(p.get("n_fonti") or len(p.get("fonti", [])))
    if n_test == 1 and p.get("fonti"):       # una sola testata: si dichiara da chi arriva la notizia
        etichetta = "Secondo " + p["fonti"][0]["fonte"]
    con_foto = bool((foto or {}).get("file"))
    base = reel._fondo916((foto or {}).get("file"))
    grande = base.resize((int(W * 1.10), int(H * 1.10)), Image.LANCZOS)
    vivo = _velo(grande) if con_foto else grande
    scuro = Image.blend(grande.filter(ImageFilter.GaussianBlur(24)), Image.new("RGB", grande.size, ST.NERO), 0.76)

    # globo 3D (Blender) e mappa notturna: se mancano, il reel usa foto e mappa piatta senza errori
    import reel_globo
    globo_ok = reel_globo.disponibile() and not os.environ.get("ADOLOS_SENZA_GLOBO")   # per le prove veloci
    usata_mappa = False
    mappa_fonti = None
    mappa_ok, evento = False, None
    try:
        import mappa
        mappa_ok = mappa.disponibile()
        if mappa_ok:
            evento = p.get("paese_evento") or mappa.codice_da_testo(etichetta, nomi) or mappa.codice_da_testo(p["titolo"], nomi)
    except Exception as e:
        print("Reel: mappa non disponibile:", str(e)[:160])
    cache_sfondi = {}

    def sfondo_mappa(codici, alta=False):
        """Mappa notturna con questi paesi illuminati (uno solo: ingrandito; più d'uno: vista d'insieme). La tela è più
        grande dello schermo (ST.CANVAS_K) per lasciare spazio alla telecamera."""
        chiave = tuple(codici)
        if (chiave, alta) not in cache_sfondi:
            wc, hc = int(W * ST.CANVAS_K), int(H * ST.CANVAS_K)
            cy = (700 if alta else 880) + (hc - H) // 2          # alta: sotto c'è un contatore
            v = mappa.vista_paese(chiave[0], wc, hc, cy) if len(chiave) == 1 else mappa.vista_insieme(list(chiave), wc, hc, cy)
            cache_sfondi[(chiave, alta)] = _SfondoMappa(mappa.fondo(v, list(chiave)), v)
        return cache_sfondi[(chiave, alta)]

    def luogo_di(nome):
        """Il posto con questo nome (dal pacchetto: "luoghi", oppure il luogo del globo) -> {"nome", "lon", "lat"} o None."""
        if not nome:
            return None
        for k, val in dict(p.get("luoghi") or {}, **({(p.get("globo") or {}).get("luogo", {}).get("nome", ""): (p.get("globo") or {}).get("luogo")}
                                                    if (p.get("globo") or {}).get("luogo") else {})).items():
            if k and k.lower() == nome.strip().lower() and val:
                return dict(val, nome=k)
        return None

    def codici_scena(testo):
        """"US, CN" o "Stati Uniti, Cina" -> ["US", "CN"] (solo paesi che si trovano sulla mappa)."""
        out = []
        for x in [y.strip() for y in (testo or "").split(",") if y.strip()]:
            c = x.upper() if (len(x) == 2 and mappa.esiste(x.upper())) else mappa.codice_da_testo(x, nomi)
            if c and mappa.esiste(c) and c not in out:
                out.append(c)
        return out

    # che cosa va al centro di ogni scena
    piano, gia_fonti = [], False
    for i, r in enumerate(righe):
        voce, schermo = r["voce"], r["schermo"]
        numero = r.get("numero") or social._numero_forte(voce.replace("%", " per cento"))
        anno = ANNO.search(voce)
        forzata = (r.get("scena") or "").strip().lower()
        if i == 0:
            piano.append(("apertura", None))
        elif forzata in ("orbite", "domanda"):
            piano.append((forzata, None))
        elif numero and len(numero) <= 14:
            piano.append(("numero", (numero, schermo if r.get("numero") else _etichetta_numero(voce, schermo))))
        elif anno and int(anno.group(1)) < oggi.year:
            piano.append(("anno", (int(anno.group(1)), "")))
        elif ST.SCENA_TESTATE and not gia_fonti and (i == len(righe) - 1 or FONTI_RE.search(voce)):
            piano.append(("fonti", None))
            gia_fonti = True
        elif mappa_ok and (r.get("paese") or r.get("luogo")) and (codici_scena(r.get("paese")) or evento):
            piano.append(("mappa", None))             # se la scena dice quali paesi o luoghi, vince la mappa sulla foto
        elif con_foto:
            piano.append(("foto", _carta_sorgente(base, i)))
        elif mappa_ok and (codici_scena(r.get("paese")) or evento):
            piano.append(("mappa", None))
        else:
            piano.append(("parola", schermo or voce.split()[social._parola_forte(voce.split())].strip(".,:;!?")))

    # sfondo di ogni scena: la mappa con i paesi di QUELLA scena illuminati, oppure la foto sfocata
    fondo_nero = Image.new("RGB", grande.size, ST.NERO)
    luogo_scena = [luogo_di(r.get("luogo")) for r in righe]
    sfondo_scena = []
    for i, (tipo, _) in enumerate(piano):
        if tipo == "apertura":
            sfondo_scena.append(vivo)
        elif tipo == "orbite":
            sfondo_scena.append(fondo_nero)
        elif tipo == "domanda":
            sfondo_scena.append(scuro)
        elif mappa_ok and tipo != "foto" and (codici_scena(righe[i].get("paese")) or evento):
            sfondo_scena.append(sfondo_mappa(codici_scena(righe[i].get("paese")) or [evento], alta=tipo in ("numero", "anno")))
            usata_mappa = True
        else:
            sfondo_scena.append(scuro)

    # clip 3D: si disegnano ora, perché servono le durate esatte della voce
    clip_file = {}
    if globo_ok:
        for i, (tipo, _) in enumerate(piano):
            try:
                if tipo == "apertura" and p.get("globo"):
                    print(f"Reel: globo 3D, scena {i + 1} ({durate[i]:.0f} s)…", flush=True)
                    if (p["globo"].get("tipo") or "") == "lancio":
                        clip_file[i] = reel_globo.clip_lancio(p, durate[i], lavoro)
                    else:
                        clip_file[i] = reel_globo.clip_convergenza(p, durate[i], lavoro)
                elif tipo == "fonti":
                    print(f"Reel: globo 3D delle testate, scena {i + 1} ({durate[i]:.0f} s)…", flush=True)
                    clip_file[i], _ = reel_globo.clip_testate(p, durate[i], lavoro)
                usata_mappa = usata_mappa or i in clip_file
            except Exception as e:
                print("Reel: globo 3D non riuscito, uso la mappa piatta:", str(e)[:200])
    if "fonti" in [t for t, _ in piano]:
        i_f = [t for t, _ in piano].index("fonti")
        if i_f not in clip_file:
            try:
                import mappa
                mappa_fonti = _MappaFonti(p, nomi, grande.size) if mappa.disponibile() else None
                mappa_fonti = mappa_fonti if mappa_fonti and mappa_fonti.codici else None
                usata_mappa = usata_mappa or bool(mappa_fonti)
            except Exception as e:
                print("Reel: mappa delle testate non disegnata:", str(e)[:160])

    # strati fissi (disegnati una volta per scena)
    strati, titoli = [], []
    for i, (tipo, _) in enumerate(piano):
        s = Image.new("RGBA", (W, H), ST.TRASPARENTE)
        _testa(s, etichetta)
        strati.append(s)
        t_strato = None
        if tipo == "apertura":                     # la copertina: titolo grande in basso, come sui caroselli
            t_strato = Image.new("RGBA", (W, H), ST.TRASPARENTE)
            dt = ImageDraw.Draw(t_strato)
            frase = parti[-1]
            alt = social._titolo_a(t_strato, dt, frase, M, 0, W - 2 * M, 430, colore=ST.BIANCO, size=120, min_size=64, stretto=ST.STRETTO_TITOLO, peso=ST.PESO_TITOLO, prova=True)
            social._titolo_a(t_strato, dt, frase, M, ST.Y_SICURO - alt - 20, W - 2 * M, 430,
                             evidenzia=social._parola_forte(frase.split()), colore=ST.BIANCO, size=120, min_size=64,
                             stretto=ST.STRETTO_TITOLO, peso=ST.PESO_TITOLO)
        titoli.append(t_strato)
    forti = []
    for voce in scene:
        parole = voce.split()
        forti.append({parole[social._parola_forte(parole)].strip(".,:;!?«»\"'()").lower()} if parole else set())

    # chiusura
    fine = Image.new("RGBA", (W, H), ST.TRASPARENTE)
    df = ImageDraw.Draw(fine)
    social._marchio(df, M, ST.Y_MARCHIO)
    df.text((M, 640), "SEGUI", font=_f(150), fill=ST.BIANCO, anchor="ls")
    nomi_f = [f["fonte"] for f in p.get("fonti", [])][:6]
    if n_test > len(nomi_f):
        nomi_f.append(f"e altre {n_test - len(nomi_f)}")
    y = social._testo_a(df, "Per sapere chi ne parla nel mondo.", M, 920, W - 2 * M, social._news(52), ST.BIANCO, 1.2, max_righe=2)
    y = social._testo_a(df, "Fonti: " + ", ".join(nomi_f) + ".", M, y + 50, W - 2 * M, social._news(42), ST.GRIGIO, 1.25, max_righe=4)
    y = social._testo_a(df, ST.NOTA_AI, M, y + 26, W - 2 * M, social._news(30, corsivo=True), ST.GRIGIO, 1.25, max_righe=3)
    crediti = " ".join(x for x in ((foto or {}).get("credito", ""), _credito_mappa() if usata_mappa else "") if x)
    if crediti:
        social._testo_a(df, crediti, M, y + 14, W - 2 * M, social._news(26, corsivo=True), ST.GRIGIO, 1.25, max_righe=3)

    gruppi = reel.gruppi_parole(scene, durate, tempi, quante=ST.PAROLE_PER_PEZZO)
    inizi = [sum(durate[:i]) for i in range(len(durate) + 1)]       # l'ultimo è l'inizio della chiusura
    totale = sum(durate) + reel.CHIUSURA
    wav_fx = _con_effetti(wav, inizi[1:], lavoro / "voce_effetti.wav")
    comando = [reel.FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(wav_fx), "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
               str(uscita)]
    proc = subprocess.Popen(comando, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    nero = Image.new("RGBA", (W, H), ST.NERO + (255,))
    clips = {i: _Clip(f) for i, f in clip_file.items()}
    g = 0
    ultimo_fr, prec, i_cor = None, None, -1
    try:
        for n in range(round(totale * FPS)):
            t = n / FPS
            i = max(k for k in range(len(inizi)) if inizi[k] <= t + 1e-6)
            tl = t - inizi[i]
            if i != i_cor:                                        # nuova scena: si tiene l'ultimo fotogramma di quella prima
                prec, i_cor = ultimo_fr, i
            if i >= len(scene):                                   # chiusura
                fr = _pan(scuro, tl, reel.CHIUSURA, 0).convert("RGBA")
                fr.alpha_composite(fine)
                d = ImageDraw.Draw(fr, "RGBA")
                k = _salto(tl / 0.4)
                f = _f(round(130 * (0.7 + 0.3 * k)))
                lw = d.textlength(ST.CODA, font=f)
                d.rounded_rectangle((M, 680, M + lw + 50, 680 + f.size * 1.3), radius=12, fill=ST.GIALLO)
                d.text((M + 25, 680 + f.size * 0.65), ST.CODA, font=f, fill=ST.NERO, anchor="lm")
            else:
                tipo, dati = piano[i]
                durata = durate[i]
                if i in clips:
                    fr = _veli(clips[i].fotogramma(), 0.55, 0.78 if tipo == "apertura" else 0.45).convert("RGBA")
                elif tipo == "fonti" and mappa_fonti:
                    fr = mappa_fonti.fondo(tl).convert("RGBA")
                elif isinstance(sfondo_scena[i], _SfondoMappa):
                    fr0, dove = sfondo_scena[i].inquadra(tl, durata, (luogo_scena[i]["lon"], luogo_scena[i]["lat"]) if luogo_scena[i] else None)
                    fr = _veli(fr0, 0.6, 0.45).convert("RGBA")
                else:
                    fr = _pan(sfondo_scena[i], tl, durata, i).convert("RGBA")
                fr.alpha_composite(strati[i])
                if titoli[i] is not None:
                    fr.alpha_composite(titoli[i], dest=(0, int((1 - _e(tl / 0.45)) * 70)))
                d = ImageDraw.Draw(fr, "RGBA")
                if tipo == "numero":
                    _contatore(d, tl, *dati)
                elif tipo == "anno":
                    _linea_tempo(d, tl, dati[0], oggi.year, dati[1])
                elif tipo == "fonti" and i in clips:
                    codici = reel_globo.codici_testate(p)
                    _conteggio(d, tl, p, len(p.get("paesi") or []) or len(codici), _e((tl - 0.2) / max(1.0, durata * 0.6)), y=1290)
                elif tipo == "fonti" and mappa_fonti:
                    mappa_fonti.disegna(d, tl, p)
                elif tipo == "fonti":
                    _griglia(d, tl, p, nomi)
                elif tipo == "foto":
                    _carta(fr, d, tl, durata, dati, i)
                elif tipo == "parola":
                    _parola(d, tl, dati)
                elif tipo == "orbite":
                    _orbite(d, tl)
                elif tipo == "domanda":
                    _domanda(d, tl)
                if luogo_scena[i] and isinstance(sfondo_scena[i], _SfondoMappa):
                    mx, my = dove(luogo_scena[i]["lon"], luogo_scena[i]["lat"])
                    _marcatore(d, mx, my, tl, luogo_scena[i]["nome"])
                if fonti_scena[i]:
                    _riga_fonte(fr, tl, fonti_scena[i])
                while g + 1 < len(gruppi) and gruppi[g + 1][0] <= t:
                    g += 1
                a, b, parole, si = gruppi[g]
                if si == i and i > 0 and a <= t < b + 0.05:        # la prima scena è la copertina: titolo, niente parole
                    _didascalia(fr, parole, t - a, forti[i], b - a)
            if tl < ST.TRANSIZIONE_S and prec is not None:          # la scena nuova spinge via la vecchia
                fr = _spinta(prec, fr, tl / ST.TRANSIZIONE_S, i)
            ultimo_fr = fr
            proc.stdin.write(fr.convert("RGB").tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        pass
    finally:
        for c in clips.values():
            c.chiudi()
    errore = proc.stderr.read().decode(errors="replace")
    if proc.wait():
        raise RuntimeError("ffmpeg (reel animato): " + errore.strip()[-400:])
    return uscita


def _spinta(prec, nuovo, q, i):
    """Cambio di scena in movimento: la nuova arriva da destra, dal basso o con uno zoom, a turno."""
    k = _e(q)
    vecchio, nuovo = prec.convert("RGB"), nuovo.convert("RGB")
    verso = i % 3
    if verso == 2:                                   # zoom: la scena nuova arriva grande e si assesta
        s = 1.22 - 0.22 * k
        w, h = int(W * s), int(H * s)
        gr = nuovo.resize((w, h), Image.BILINEAR).crop(((w - W) // 2, (h - H) // 2, (w - W) // 2 + W, (h - H) // 2 + H))
        return Image.blend(vecchio, gr, k)
    tela = Image.new("RGB", (W, H), ST.NERO)
    if verso == 0:
        tela.paste(vecchio, (-int(k * W * 0.6), 0))
        tela.paste(nuovo, (int((1 - k) * W), 0))
    else:
        tela.paste(vecchio, (0, -int(k * H * 0.6)))
        tela.paste(nuovo, (0, int((1 - k) * H)))
    return tela


def _credito_mappa():
    import mappa
    return mappa.CREDITO
