"""
ADOLOS – reel animato, stile "infografica"
==========================================
Il montaggio del reel disegnato fotogramma per fotogramma (Pillow) e mandato direttamente a ffmpeg, come i video
esplicativi che girano su Instagram: fondo scuro, etichetta gialla con il paese o l'argomento e la data in alto,
un elemento grafico al centro che si muove, sottotitoli a scatti con la parola chiave in giallo.

Per ogni scena del copione si sceglie l'elemento centrale dal contenuto (niente inventato, solo quello che c'è):
  - un numero con unità (48%, 1.170 euro, 3 miliardi)  -> contatore giallo che sale fino al numero
  - un anno passato (dal 2012)                           -> linea del tempo che si riempie fino a oggi
  - "ne parlano", "testate", ultima scena                -> griglia delle testate che compare una alla volta
                                                            (+ punto cieco italiano se il pacchetto lo segnala)
  - altrimenti                                          -> la foto con licenza libera in un riquadro che si muove
La prima scena è la copertina (foto a tutto schermo e titolo), l'ultima è "Segui @adolos.it" con fonti e note.
Restano sempre scritti "Voce generata con AI" e, nella chiusura, il credito della foto.

Usato da engine/reel.py quando in fonti.json > reel_voce > stile_video c'è "infografica".
"""

import datetime
import functools
import math
import re
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import reel
import social

W, H, FPS, M = reel.W, reel.H, reel.FPS, reel.MARGINE
GIALLO, BIANCO = social.GIALLO, (255, 255, 255)
NERO = (9, 9, 12)
GRIGIO = (196, 192, 188)
SCURO_CELLA = (22, 22, 28)
MESI = "GEN FEB MAR APR MAG GIU LUG AGO SET OTT NOV DIC".split()
Y_SOTTO = 1480                       # riga dei sottotitoli (sopra la zona coperta da nome utente e didascalia)
CARTA = (110, 520, 970, 1260)        # riquadro centrale della foto
ANNO = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
FONTI_RE = re.compile(r"\b(ne parla\w*|testat\w+|giornali|riportano|riporta|fonti|media)\b", re.I)


@functools.lru_cache(maxsize=512)
def _f(size, peso=900):
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
def _velo(img):
    w, h = img.size
    m = Image.new("L", (1, h))
    for y in range(h):
        basso = min(1.0, max(0.0, (y / h - 0.28) / 0.40)) ** 1.1 * 0.92
        alto = max(0.0, 1 - y / (h * 0.2)) * 0.65
        m.putpixel((0, y), int(255 * max(basso, alto)))
    return Image.composite(Image.new("RGB", img.size, NERO), img, m.resize(img.size))


def _pan(img, t, durata, verso):
    """Ritaglio W x H che scorre piano dentro un'immagine un po' più grande (niente ridimensionamento: veloce)."""
    k = min(1.0, max(0.0, t / max(durata, 0.1)))
    dx, dy = img.width - W, img.height - H
    x, y = [(dx * k, dy / 2), (dx * (1 - k), dy / 2), (dx / 2, dy * k), (dx / 2, dy * (1 - k))][verso % 4]
    return img.crop((int(x), int(y), int(x) + W, int(y) + H))


def _carta_sorgente(base, i):
    """Ritaglio della foto per il riquadro centrale: ogni scena prende una parte diversa, così sembrano inquadrature."""
    cw, ch = CARTA[2] - CARTA[0], CARTA[3] - CARTA[1]
    sw, sh = int(cw * 1.16), int(ch * 1.16)
    rw = base.width
    rh = int(rw * sh / sw)
    y0 = [0.30, 0.05, 0.50, 0.18][i % 4] * max(0, base.height - rh)
    pezzo = base.crop((0, int(y0), rw, int(y0) + rh)).resize((sw, sh), Image.LANCZOS)
    maschera = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(maschera).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=30, fill=255)
    return pezzo, maschera


# ---------------------------------------------------------------- pezzi fissi
def _testa(img, etichetta, data, titolo=""):
    d = ImageDraw.Draw(img)
    social._marchio(d, M, 104)
    d.text((W - M, 146), "Voce generata con AI", font=_f(24, 600), fill=GRIGIO, anchor="rm")
    y = 236
    etichetta = etichetta.upper()
    while d.textlength(etichetta, font=_f(30)) > W - 2 * M - 330 and " " in etichetta:
        etichetta = etichetta.rsplit(" ", 1)[0].rstrip(",;:")
    lw = d.textlength(etichetta, font=_f(30))
    d.rounded_rectangle((M, y, M + lw + 34, y + 52), radius=6, fill=GIALLO)
    d.text((M + 17, y + 27), etichetta, font=_f(30), fill=NERO, anchor="lm")
    d.text((W - M, y + 27), data, font=_f(28, 800), fill=GRIGIO, anchor="rm")
    if titolo:
        social._titolo_a(img, d, titolo, M, 324, W - 2 * M, 170, colore=BIANCO, size=80, min_size=50)


def _sottotitolo(fr, d, parole, dt, forti):
    """2-3 parole, grandi, con un piccolo "pop" quando entrano; la parola chiave in giallo."""
    parole = [p.upper() for p in parole]
    size = 84
    while True:
        f = _f(size)
        larga = sum(d.textlength(p, font=f) for p in parole) + d.textlength(" ", font=f) * (len(parole) - 1)
        if larga <= W - 2 * M or size <= 48:
            break
        size -= 4
    f = _f(round(size * (0.84 + 0.16 * _salto(dt / 0.16))))
    spazio = d.textlength(" ", font=f)
    larga = sum(d.textlength(p, font=f) for p in parole) + spazio * (len(parole) - 1)
    x = (W - larga) / 2
    for p in parole:
        pulita = p.strip(".,:;!?«»\"'()").lower()
        colore = GIALLO if (any(c.isdigit() for c in p) or pulita in forti) else BIANCO
        d.text((x, Y_SOTTO), p, font=f, fill=colore, anchor="lm", stroke_width=7, stroke_fill=NERO)
        x += d.textlength(p, font=f) + spazio


# ---------------------------------------------------------------- elementi centrali
def _valore(numero):
    """"1.170 €" -> (1170, 0, "€") · "2,5 MILIARDI" -> (2.5, 1, "MILIARDI") · "48%" -> (48, 0, "%")."""
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


def _contatore(fr, d, t, numero, etichetta):
    v, nd, unita = _valore(numero)
    k = _e((t - 0.15) / 1.2)
    testo = _scrivi_numero(v * k if k < 1 else v, nd, unita)
    finale = _scrivi_numero(v, nd, unita)
    size = 250
    while d.textlength(finale, font=_f(size)) > W - 2 * M and size > 90:
        size -= 10
    size = round(size * (0.8 + 0.2 * _salto(t / 0.35)))
    d.text((W / 2, 830), testo, font=_f(size), fill=GIALLO, anchor="mm", stroke_width=4, stroke_fill=NERO)
    if etichetta and t > 0.3:
        d.text((W / 2, 830 + size * 0.62 + 30), etichetta.upper()[:44], font=_f(40, 800), fill=BIANCO, anchor="mm")


def _linea_tempo(fr, d, t, anno, oggi, etichetta):
    y, x0, x1 = 900, M + 40, W - M - 40
    k = _e((t - 0.2) / 1.4)
    d.text((x0, y - 90), str(anno), font=_f(110), fill=BIANCO, anchor="lm")
    d.text((x1, y - 90), str(oggi), font=_f(110), fill=BIANCO, anchor="rm")
    d.line((x0, y, x1, y), fill=(80, 80, 88), width=8)
    xk = x0 + (x1 - x0) * k
    d.line((x0, y, xk, y), fill=GIALLO, width=12)
    d.ellipse((x0 - 14, y - 14, x0 + 14, y + 14), fill=GIALLO)
    d.ellipse((xk - 20, y - 20, xk + 20, y + 20), fill=GIALLO, outline=NERO, width=4)
    anni = oggi - anno
    n = round(anni * k)
    d.text((W / 2, y + 190), f"{n} {'ANNO' if n == 1 else 'ANNI'}", font=_f(170), fill=GIALLO, anchor="mm",
           stroke_width=4, stroke_fill=NERO)
    if etichetta and t > 0.4:
        d.text((W / 2, y + 330), etichetta.upper()[:44], font=_f(40, 800), fill=BIANCO, anchor="mm")


def _griglia(fr, d, t, p, nomi):
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
                            fill=SCURO_CELLA, outline=GIALLO, width=4)
        if k > 0.75:
            paese = c.get("paese") or ""
            nome_p = nomi.get(paese, paese).upper() if paese not in ("+", "WEB") else ("WEB" if paese == "WEB" else "")
            if nome_p:
                fp = _f(34)
                while d.textlength(nome_p, font=fp) > cw - 28 and fp.size > 20:
                    fp = _f(fp.size - 2)
                d.text((cx, cy - 26), nome_p, font=fp, fill=GIALLO, anchor="mm")
            nome = c["fonte"]
            fn = _f(28, 700)
            if d.textlength(nome, font=fn) > cw - 28:
                while d.textlength(nome + "…", font=fn) > cw - 28 and len(nome) > 3:
                    nome = nome[:-1]
                nome = nome.rstrip() + "…"
            if paese == "+":
                d.text((cx, cy), nome, font=_f(64), fill=GIALLO, anchor="mm")
            else:
                d.text((cx, cy + (24 if nome_p else 0)), nome, font=fn, fill=BIANCO, anchor="mm")
    y = y0 + righe * (ch + gap) + 70
    k = _e((t - 0.1) / (passo * len(celle) + 0.3))
    d.text((W / 2, y), f"{round(n_test * k)} {'TESTATA' if n_test == 1 else 'TESTATE'}", font=_f(120), fill=GIALLO,
           anchor="mm", stroke_width=4, stroke_fill=NERO)
    d.text((W / 2, y + 100), f"DA {n_paesi} {'PAESE' if n_paesi == 1 else 'PAESI'}", font=_f(54, 800), fill=BIANCO,
           anchor="mm")
    if p.get("punto_cieco") == "italia" and t > 0.9:
        testo = "PUNTO CIECO: NESSUNA TESTATA ITALIANA"
        f = _f(34)
        lw = d.textlength(testo, font=f)
        d.rounded_rectangle((W / 2 - lw / 2 - 20, y + 160, W / 2 + lw / 2 + 20, y + 216), radius=6, fill=GIALLO)
        d.text((W / 2, y + 189), testo, font=f, fill=NERO, anchor="mm")


def _carta(fr, d, t, durata, sorgente, verso):
    pezzo, maschera = sorgente
    k = _e(t / 0.4)
    dy = int((1 - k) * 90)
    cw, ch = maschera.size
    q = min(1.0, max(0.0, t / max(durata, 0.1)))
    mx, my = pezzo.width - cw, pezzo.height - ch
    x, y = (mx * q, my / 2) if verso % 2 == 0 else (mx * (1 - q), my * q)
    fr.paste(pezzo.crop((int(x), int(y), int(x) + cw, int(y) + ch)), (CARTA[0], CARTA[1] + dy), maschera)
    d.rounded_rectangle((CARTA[0], CARTA[1] + dy, CARTA[2], CARTA[3] + dy), radius=30, outline=GIALLO, width=6)


def _parola(fr, d, t, testo):
    testo = testo.upper()
    size = 130
    while d.textlength(testo, font=_f(size)) > W - 2 * M - 60 and size > 56:
        size -= 6
    f = _f(size)
    lw = d.textlength(testo, font=f)
    k = _e(t / 0.45)
    x0 = W / 2 - lw / 2 - 30
    d.rectangle((x0, 820 - size * 0.75, x0 + (lw + 60) * k, 820 + size * 0.75), fill=GIALLO)
    if k > 0.6:
        d.text((W / 2, 820), testo, font=f, fill=NERO, anchor="mm")


# ---------------------------------------------------------------- suoni
def _con_effetti(wav, inizi, uscita):
    """Un "whoosh" leggero a ogni cambio di scena (rumore filtrato, fatto qui: niente file di altri)."""
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
def rendi(p, scene, schermi, durate, tempi, foto, wav, uscita, lavoro):
    oggi = datetime.date.today()
    data = f"{oggi.day} {MESI[oggi.month - 1]} {oggi.year}"
    nomi = _nomi_paesi()
    parti = social._divide_titolo(p["titolo"])
    etichetta = parti[0].rstrip(":") if len(parti) == 2 else (p.get("sezione") or "Notizie")
    n_test = int(p.get("n_fonti") or len(p.get("fonti", [])))
    if n_test == 1 and p.get("fonti"):       # una sola testata: si dichiara da chi arriva la notizia
        etichetta = "Secondo " + p["fonti"][0]["fonte"]
    con_foto = bool((foto or {}).get("file"))
    base = reel._fondo916((foto or {}).get("file"))
    grande = base.resize((int(W * 1.10), int(H * 1.10)), Image.LANCZOS)
    vivo = _velo(grande) if con_foto else grande
    scuro = Image.blend(grande.filter(ImageFilter.GaussianBlur(24)), Image.new("RGB", grande.size, NERO), 0.76)

    # che cosa va al centro di ogni scena
    piano, gia_griglia = [], False
    for i, (voce, schermo) in enumerate(zip(scene, schermi)):
        numero = social._numero_forte(voce.replace("%", " per cento"))
        anno = ANNO.search(voce)
        if i == 0:
            piano.append(("apertura", None))
        elif numero and len(numero) <= 14:
            piano.append(("numero", (numero, _etichetta_numero(voce, schermo))))
        elif anno and int(anno.group(1)) < oggi.year:
            piano.append(("anno", (int(anno.group(1)), "")))
        elif not gia_griglia and (i == len(scene) - 1 or FONTI_RE.search(voce)):
            piano.append(("fonti", None))
            gia_griglia = True
        elif con_foto:
            piano.append(("foto", _carta_sorgente(base, i)))
        else:
            piano.append(("parola", schermo or voce.split()[social._parola_forte(voce.split())].strip(".,:;!?")))

    # strati fissi (disegnati una volta per scena)
    strati, titoli = [], []
    for i, ((tipo, _), schermo) in enumerate(zip(piano, schermi)):
        s = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _testa(s, etichetta, data, "" if tipo in ("apertura", "parola") else schermo)
        strati.append(s)
        t_strato = None
        if tipo == "apertura":
            t_strato = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            dt = ImageDraw.Draw(t_strato)
            frase = parti[-1]
            alt = social._titolo_a(t_strato, dt, frase, M, 0, W - 2 * M, 470, colore=BIANCO, size=140, min_size=76, prova=True)
            social._titolo_a(t_strato, dt, frase, M, 1320 - alt - 40, W - 2 * M, 470,
                             evidenzia=social._parola_forte(frase.split()), colore=BIANCO, size=140, min_size=76)
        titoli.append(t_strato)
    forti = []
    for voce in scene:
        parole = voce.split()
        forti.append({parole[social._parola_forte(parole)].strip(".,:;!?«»\"'()").lower()} if parole else set())

    # chiusura
    fine = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    df = ImageDraw.Draw(fine)
    social._marchio(df, M, 104)
    df.text((M, 640), "SEGUI", font=_f(150), fill=BIANCO, anchor="ls")
    nomi_f = [f["fonte"] for f in p.get("fonti", [])][:6]
    if n_test > len(nomi_f):
        nomi_f.append(f"e altre {n_test - len(nomi_f)}")
    y = social._testo_a(df, "Per sapere chi ne parla nel mondo.", M, 920, W - 2 * M, social._news(52), BIANCO, 1.2, max_righe=2)
    y = social._testo_a(df, "Fonti: " + ", ".join(nomi_f) + ".", M, y + 50, W - 2 * M, social._news(42), GRIGIO, 1.25, max_righe=4)
    y = social._testo_a(df, "Testo preparato con l'aiuto dell'AI e verificato dalla redazione. Voce generata con AI.",
                        M, y + 26, W - 2 * M, social._news(30, corsivo=True), GRIGIO, 1.25, max_righe=3)
    if (foto or {}).get("credito"):
        social._testo_a(df, foto["credito"], M, y + 14, W - 2 * M, social._news(26, corsivo=True), GRIGIO, 1.25, max_righe=2)

    gruppi = reel.gruppi_parole(scene, durate, tempi, quante=3)
    inizi = [sum(durate[:i]) for i in range(len(durate) + 1)]       # l'ultimo è l'inizio della chiusura
    totale = sum(durate) + reel.CHIUSURA
    wav_fx = _con_effetti(wav, inizi[1:], lavoro / "voce_effetti.wav")
    comando = [reel.FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(wav_fx), "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
               str(uscita)]
    proc = subprocess.Popen(comando, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    nero = Image.new("RGBA", (W, H), NERO + (255,))
    g = 0
    try:
        for n in range(round(totale * FPS)):
            t = n / FPS
            i = max(k for k in range(len(inizi)) if inizi[k] <= t + 1e-6)
            tl = t - inizi[i]
            if i >= len(scene):                                   # chiusura
                fr = _pan(scuro, tl, reel.CHIUSURA, 0).convert("RGBA")
                fr.alpha_composite(fine)
                d = ImageDraw.Draw(fr)
                k = _salto(tl / 0.4)
                testo = "@ADOLOS.IT"
                f = _f(round(130 * (0.7 + 0.3 * k)))
                lw = d.textlength(testo, font=f)
                d.rounded_rectangle((M, 680, M + lw + 50, 680 + f.size * 1.3), radius=12, fill=GIALLO)
                d.text((M + 25, 680 + f.size * 0.65), testo, font=f, fill=NERO, anchor="lm")
            else:
                tipo, dati = piano[i]
                durata = durate[i]
                fr = _pan(vivo if tipo == "apertura" else scuro, tl, durata, i).convert("RGBA")
                fr.alpha_composite(strati[i])
                if titoli[i] is not None:
                    fr.alpha_composite(titoli[i], dest=(0, int((1 - _e(tl / 0.45)) * 70)))
                d = ImageDraw.Draw(fr)
                if tipo == "numero":
                    _contatore(fr, d, tl, *dati)
                elif tipo == "anno":
                    _linea_tempo(fr, d, tl, dati[0], oggi.year, dati[1])
                elif tipo == "fonti":
                    _griglia(fr, d, tl, p, nomi)
                elif tipo == "foto":
                    _carta(fr, d, tl, durata, dati, i)
                elif tipo == "parola":
                    _parola(fr, d, tl, dati)
                while g + 1 < len(gruppi) and gruppi[g + 1][0] <= t:
                    g += 1
                a, b, parole, si = gruppi[g]
                if si == i and a <= t < b + 0.05:
                    _sottotitolo(fr, d, parole, t - a, forti[i])
            if tl < 0.12 and n:                                    # stacco rapido tra le scene
                fr = Image.blend(fr, nero, 0.55 * (1 - tl / 0.12))
            proc.stdin.write(fr.convert("RGB").tobytes())
        proc.stdin.close()
    except BrokenPipeError:
        pass
    errore = proc.stderr.read().decode(errors="replace")
    if proc.wait():
        raise RuntimeError("ffmpeg (reel animato): " + errore.strip()[-400:])
    return uscita
