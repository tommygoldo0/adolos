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
  - "ne parlano", "testate", ultima scena            -> globo con i paesi delle testate che si accendono
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


def _veli(img, alto=0.72, basso=0.5):
    """Mappe e globo: scurisce solo la fascia in alto (parole) e quella in basso (fonte), il centro resta libero."""
    w, h = img.size
    m = Image.new("L", (1, h))
    for y in range(h):
        a = max(0.0, 1 - y / (h * 0.24)) * alto
        b = min(1.0, max(0.0, (y / h - 0.70) / 0.26)) * basso
        m.putpixel((0, y), int(255 * max(a, b)))
    return Image.composite(Image.new("RGB", img.size, ST.NERO), img, m.resize(img.size))


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
    social._pillola_a(img, d, M, ST.Y_ETICHETTA, etichetta, size=34)


def _didascalia(fr, parole, dt, forti):
    """Le parole della voce, in alto: sottili, la parola chiave in grassetto, i numeri in giallo. Entrano dal basso."""
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
    alt = int(size * 1.9)
    strato = Image.new("RGBA", (W, alt), ST.TRASPARENTE)
    ombra = Image.new("RGBA", (W, alt), ST.TRASPARENTE)
    ds, dd = ImageDraw.Draw(ombra), ImageDraw.Draw(strato)
    x = (W - larga) / 2
    for p in parole:
        f = _f(size, peso(p))
        pulita = p.strip(".,:;!?«»\"'()").lower()
        colore = ST.GIALLO if any(c.isdigit() for c in p) else ST.BIANCO
        ds.text((x, alt / 2 + 4), p, font=f, fill=ST.OMBRA, anchor="lm")
        dd.text((x, alt / 2), p, font=f, fill=colore, anchor="lm")
        x += d0.textlength(p, font=f) + spazio
    ombra = ombra.filter(ImageFilter.GaussianBlur(6))
    strato = Image.alpha_composite(ombra, strato)
    k = _e(dt / 0.14)
    strato.putalpha(strato.getchannel("A").point(lambda v: int(v * k)))
    fr.alpha_composite(strato, dest=(0, int(ST.Y_DIDASCALIA - alt / 2 + (1 - _e(dt / 0.2)) * 18)))


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
    mappa_ok, evento, luogo = False, None, (p.get("globo") or {}).get("luogo")
    try:
        import mappa
        mappa_ok = mappa.disponibile()
        if mappa_ok:
            evento = p.get("paese_evento") or mappa.codice_da_testo(etichetta, nomi) or mappa.codice_da_testo(p["titolo"], nomi)
    except Exception as e:
        print("Reel: mappa non disponibile:", str(e)[:160])
    cache_sfondi = {}

    def sfondo_mappa(codici, alta=False):
        """Mappa notturna con questi paesi illuminati (uno solo: ingrandito; più d'uno: vista d'insieme)."""
        chiave = tuple(codici)
        if (chiave, alta) not in cache_sfondi:
            wc, hc = grande.size
            cy = (700 if alta else 880) + (hc - H) // 2          # alta: sotto c'è un contatore
            v = mappa.vista_paese(chiave[0], wc, hc, cy) if len(chiave) == 1 else mappa.vista_insieme(list(chiave), wc, hc, cy)
            img = mappa.fondo(v, list(chiave))
            if luogo and evento in chiave:                          # la città della notizia (es. Shenzhen) sulla mappa
                dd = ImageDraw.Draw(img)
                x, y = v.xy(luogo["lon"], luogo["lat"])
                dd.ellipse((x - 16, y - 16, x + 16, y + 16), fill=ST.GIALLO, outline=ST.NERO, width=4)
                dd.text((x + 28, y), luogo["nome"].upper(), font=_f(40, ST.PESO_FORTE), fill=ST.BIANCO, anchor="lm",
                        stroke_width=4, stroke_fill=ST.NERO)
            cache_sfondi[(chiave, alta)] = _veli(img)
        return cache_sfondi[(chiave, alta)]

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
        if i == 0:
            piano.append(("apertura", None))
        elif numero and len(numero) <= 14:
            piano.append(("numero", (numero, schermo if r.get("numero") else _etichetta_numero(voce, schermo))))
        elif anno and int(anno.group(1)) < oggi.year:
            piano.append(("anno", (int(anno.group(1)), "")))
        elif not gia_fonti and (i == len(righe) - 1 or FONTI_RE.search(voce)):
            piano.append(("fonti", None))
            gia_fonti = True
        elif con_foto:
            piano.append(("foto", _carta_sorgente(base, i)))
        elif mappa_ok and (codici_scena(r.get("paese")) or evento):
            piano.append(("mappa", None))
        else:
            piano.append(("parola", schermo or voce.split()[social._parola_forte(voce.split())].strip(".,:;!?")))

    # sfondo di ogni scena: la mappa con i paesi di QUELLA scena illuminati, oppure la foto sfocata
    sfondo_scena = []
    for i, (tipo, _) in enumerate(piano):
        if tipo == "apertura":
            sfondo_scena.append(vivo)
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
            alt = social._titolo_a(t_strato, dt, frase, M, 0, W - 2 * M, 430, colore=ST.BIANCO, size=120, min_size=70, prova=True)
            social._titolo_a(t_strato, dt, frase, M, ST.Y_SICURO - alt - 20, W - 2 * M, 430,
                             evidenzia=social._parola_forte(frase.split()), colore=ST.BIANCO, size=120, min_size=70)
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
    try:
        for n in range(round(totale * FPS)):
            t = n / FPS
            i = max(k for k in range(len(inizi)) if inizi[k] <= t + 1e-6)
            tl = t - inizi[i]
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
                if fonti_scena[i]:
                    _riga_fonte(fr, tl, fonti_scena[i])
                while g + 1 < len(gruppi) and gruppi[g + 1][0] <= t:
                    g += 1
                a, b, parole, si = gruppi[g]
                if si == i and i > 0 and a <= t < b + 0.05:        # la prima scena è la copertina: titolo, niente parole
                    _didascalia(fr, parole, t - a, forti[i])
            if tl < ST.STACCO_S and n:                              # stacco rapido tra le scene
                fr = Image.blend(fr, nero, 0.55 * (1 - tl / ST.STACCO_S))
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


def _credito_mappa():
    import mappa
    return mappa.CREDITO
