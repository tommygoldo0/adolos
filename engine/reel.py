"""
ADOLOS – reel di una notizia, fatto con il codice (gratis, sul computer)
========================================================================
Da un pacchetto pronto (titolo, sintesi, punti, copione) crea un video verticale 1080x1920 di circa 30 secondi:
foto con licenza libera che si muove lentamente, voce che legge il copione, sottotitoli grandi a tempo,
numeri in evidenza, barra "Chi ne parla" e chiusura "Segui @adolos.it".

    ~/.venvs/faceless/bin/python engine/reel.py pacchetto.json [cartella di uscita]

Il pacchetto è un file JSON:
  {"id", "titolo", "sintesi", "punti": [...], "copione": "[0-2s] frase...\\n[2-8s] ...", "sezione",
   "paesi": ["ES", ...], "n_fonti": 7, "fonti": [{"fonte": "Al Jazeera", "paese": "QA"}, ...]}

Cosa serve sul computer: ffmpeg con i sottotitoli (brew install ffmpeg-full), Pillow, e la voce locale Kokoro
(kokoro-onnx + i due file in ~/.cache/kokoro, licenza Apache 2.0). Niente chiavi, niente costi.

Regole: la voce è sintetica, quindi nel video resta scritto "Voce generata con AI" per tutta la durata.
La foto è solo con licenza libera (stessa ricerca dei caroselli) e il credito compare nella chiusura.
Il video NON viene pubblicato da nessuna parte: resta nella cartella di uscita finché una persona non lo approva.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE))
import social                      # noqa: E402  (stessi caratteri, colori e marchio dei caroselli)

W, H, FPS = 1080, 1920, 30
MARGINE = 72
VOCE, LINGUA, VELOCITA = "im_nicola", "it", 1.08
PAUSA = 0.22                       # secondi di silenzio tra una scena e l'altra
CHIUSURA = 2.8                     # secondi della scheda finale "Segui @adolos.it"
FFMPEG = next((p for p in ("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", shutil.which("ffmpeg") or "") if p and Path(p).exists()), "ffmpeg")
BIANCO = (255, 255, 255)


# ---------------------------------------------------------------- copione
def scene_dal_copione(copione):
    """Una scena per riga del copione. Toglie i tempi tra parentesi quadre e le righe di servizio (fonti, nota AI)."""
    scene = []
    for riga in (copione or "").splitlines():
        t = re.sub(r"^\s*\[[^\]]*\]\s*", "", riga).strip()
        if not t or t.lower().startswith(("fonti", "testo preparato", "scritta", "voce generata")):
            continue
        t = re.sub(r"\s*Testo preparato con l'aiuto dell'AI.*$", "", t).strip()
        if t:
            scene.append(t)
    return scene[:8]


def _da_leggere(testo):
    """Piccoli aggiustamenti perché la voce legga bene numeri e sigle."""
    t = re.sub(r"(\d)\.(\d{3})\b", r"\1\2", testo)            # 1.170 -> 1170
    t = t.replace("%", " per cento").replace("€", " euro")
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------- voce (Kokoro, locale)
def voce(scene, cartella):
    """Legge ogni scena. Restituisce (file wav unico, [durata di ogni scena in secondi])."""
    import numpy as np
    import soundfile as sf
    from kokoro_onnx import Kokoro
    casa = Path.home() / ".cache" / "kokoro"
    tts = Kokoro(str(casa / "kokoro-v1.0.onnx"), str(casa / "voices-v1.0.bin"))
    pezzi, durate, sr = [], [], 24000
    for t in scene:
        audio = []
        for frase in [f for f in re.split(r"(?<=[.!?])\s+", _da_leggere(t)) if f.strip()]:
            a, sr = tts.create(frase, voice=VOCE, speed=VELOCITA, lang=LINGUA)
            audio.append(a)
            audio.append(np.zeros(int(sr * 0.10), dtype=a.dtype))
        a = np.concatenate(audio + [np.zeros(int(sr * PAUSA), dtype=audio[0].dtype)])
        pezzi.append(a)
        durate.append(len(a) / sr)
    pezzi.append(np.zeros(int(sr * CHIUSURA), dtype=pezzi[0].dtype))
    file = cartella / "voce.wav"
    sf.write(str(file), np.concatenate(pezzi), sr)
    return file, durate


# ---------------------------------------------------------------- immagini delle scene
def _fondo916(file_foto):
    """Foto ritagliata in verticale 9:16; senza foto, fondo Adolos con la grande α."""
    from PIL import Image, ImageDraw
    if file_foto:
        foto = Image.open(file_foto).convert("RGB")
        sc = max(W / foto.width, H / foto.height)
        foto = foto.resize((int(foto.width * sc) + 1, int(foto.height * sc) + 1), Image.LANCZOS)
        x0, y0 = (foto.width - W) // 2, max(0, (foto.height - H) // 4)
        return foto.crop((x0, y0, x0 + W, y0 + H))
    img = Image.new("RGB", (W, H), (24, 10, 12))
    ImageDraw.Draw(img).text((W + 80, -200), "α", font=social._f("DejaVuSerif-BoldItalic.ttf", 1800), fill=(74, 16, 21), anchor="rt")
    return img


def _scuro(img, quanto=0.72, sfoca=30):
    from PIL import Image, ImageFilter
    return Image.blend(img.filter(ImageFilter.GaussianBlur(sfoca)), Image.new("RGB", img.size, social.NERO_CALDO), quanto)


def _velo916(img):
    """Scurisce in alto (marchio) e dalla metà in giù (titolo e sottotitoli)."""
    from PIL import Image
    m = Image.new("L", (1, H))
    for y in range(H):
        basso = min(1.0, max(0.0, (y / H - 0.30) / 0.36)) ** 1.2 * 0.93
        alto = max(0.0, 1 - y / 320) * 0.6
        m.putpixel((0, y), int(255 * max(basso, alto)))
    return Image.composite(Image.new("RGB", (W, H), social.NERO_CALDO), img, m.resize((W, H)))


def _strato():
    from PIL import Image
    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _fisso(d, n_test, n_paesi):
    """Quello che resta su ogni scena: marchio, scritta sulla voce AI, barra "Chi ne parla" (dentro la zona sicura)."""
    social._marchio(d, MARGINE, 150)
    d.text((W - MARGINE, 192), "Voce generata con AI", font=social._arch(24, 600), fill=(225, 220, 214), anchor="rm")
    y = 1500
    x = social._spaziato(d, MARGINE, y - 15, "CHI NE PARLA", social._arch(26, 800), BIANCO, 2) + 16
    for _ in range(min(n_test, 12)):
        d.rectangle((x, y - 14, x + 26, y + 12), fill=BIANCO)
        x += 32
    riga = f"{n_test} {'testata' if n_test == 1 else 'testate'} · {n_paesi} {'paese' if n_paesi == 1 else 'paesi'}"
    if x + 14 + d.textlength(riga, font=social._arch(26, 700)) < W - MARGINE:
        d.text((x + 14, y), riga, font=social._arch(26, 700), fill=BIANCO, anchor="lm")


def immagini_scene(p, scene, foto, cartella):
    """Per ogni scena: un fondo (jpg) e uno strato trasparente (png) con le scritte fisse. Più la chiusura."""
    from PIL import ImageDraw
    base = _fondo916((foto or {}).get("file"))
    from PIL import Image
    chiaro = _velo916(base) if foto else base
    # scene interne: la foto resta visibile (un po' più scura), così il video non diventa uno schermo nero
    medio = _velo916(Image.blend(base, Image.new("RGB", base.size, social.NERO_CALDO), 0.30)) if foto else base
    scuro = _scuro(base)
    larg = W - 2 * MARGINE
    n_test, n_paesi = int(p.get("n_fonti") or len(p.get("fonti", []))), len(p.get("paesi", []))
    parti = social._divide_titolo(p["titolo"])
    kicker = parti[0].rstrip(":") if len(parti) == 2 else (p.get("sezione") or "Notizie")
    file = []
    for i, testo in enumerate(scene):
        con_numero = bool(i and social._numero_forte(testo) and len(social._numero_forte(testo)) <= 14)
        fondo, strato = (chiaro if i == 0 else scuro if con_numero else medio), _strato()
        d = ImageDraw.Draw(strato)
        _fisso(d, n_test, n_paesi)
        if i == 0:                                   # apertura: etichetta e titolo, come la copertina del carosello
            frase = parti[-1]
            alt = social._titolo_a(strato, d, frase, MARGINE, 0, larg, 520, colore=BIANCO, size=150, min_size=80, prova=True)
            y = 1180 - alt - 100
            social._pillola_a(strato, d, MARGINE, y, kicker)
            social._titolo_a(strato, d, frase, MARGINE, y + 100, larg, 520, evidenzia=social._parola_forte(frase.split()),
                             colore=BIANCO, size=150, min_size=80)
        else:
            social._pillola_a(strato, d, MARGINE, 300, kicker, size=34)
            numero = social._numero_forte(testo)
            if numero and len(numero) <= 14:
                social._titolo_a(strato, d, numero, MARGINE, 480, larg, 380, colore=social.GIALLO, size=380, min_size=150, interlinea=0.86)
        f_fondo, f_strato = cartella / f"fondo_{i:02d}.jpg", cartella / f"strato_{i:02d}.png"
        fondo.save(f_fondo, "JPEG", quality=92)
        strato.save(f_strato)
        file.append((f_fondo, f_strato))
    # chiusura: segui la pagina, fonti, nota sull'AI, credito della foto
    strato = _strato()
    d = ImageDraw.Draw(strato)
    social._marchio(d, MARGINE, 150)
    y = social._titolo_a(strato, d, "Segui @adolos.it", MARGINE, 560, larg, 420, evidenzia=1, colore=BIANCO, size=190, min_size=110)
    nomi = [f["fonte"] for f in p.get("fonti", [])][:6]
    if n_test > len(nomi):
        nomi.append(f"e altre {n_test - len(nomi)}")
    y = social._testo_a(d, "Fonti: " + ", ".join(nomi) + ".", MARGINE, y + 30, larg, social._news(44), BIANCO, 1.25, max_righe=5)
    note = "Testo preparato con l'aiuto dell'AI e verificato dalla redazione. Voce generata con AI."
    y = social._testo_a(d, note, MARGINE, y + 34, larg, social._news(30, corsivo=True), social.GRIGIO_CHIARO, 1.25, max_righe=3)
    if (foto or {}).get("credito"):
        social._testo_a(d, foto["credito"], MARGINE, y + 16, larg, social._news(26, corsivo=True), social.GRIGIO_CHIARO, 1.25, max_righe=2)
    f_fondo, f_strato = cartella / "fondo_fine.jpg", cartella / "strato_fine.png"
    scuro.save(f_fondo, "JPEG", quality=92)
    strato.save(f_strato)
    file.append((f_fondo, f_strato))
    return file


# ---------------------------------------------------------------- sottotitoli (ASS, a tempo sulle parole)
def _tempo(t):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def sottotitoli(scene, durate, cartella):
    """Tre parole alla volta, grandi e al centro. I tempi sono stimati dalla lunghezza delle parole dentro ogni scena."""
    righe = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
             "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             "Style: A,Instrument Sans,86,&H00FFFFFF,&H00FFFFFF,&H00090810,&H96000000,-1,0,0,0,100,100,0,0,1,7,2,5,60,60,0,1", "",
             "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    t0 = 0.0
    for i, (testo, durata) in enumerate(zip(scene, durate)):
        parole = testo.split()
        gruppi = [parole[k:k + 3] for k in range(0, len(parole), 3)]
        peso = [sum(len(x) for x in g) + len(g) for g in gruppi]
        utile, t = durata - PAUSA, t0
        y = 1050 if (i and social._numero_forte(testo)) else 1330
        for g, w in zip(gruppi, peso):
            dt = utile * w / sum(peso)
            frase = " ".join(g).upper().replace("{", "(").replace("}", ")")
            righe.append(f"Dialogue: 0,{_tempo(t)},{_tempo(t + dt)},A,,0,0,0,,{{\\an5\\pos({W // 2},{y})}}{frase}")
            t += dt
        t0 += durata
    file = cartella / "sottotitoli.ass"
    file.write_text("\n".join(righe) + "\n", encoding="utf-8")
    return file


# ---------------------------------------------------------------- montaggio
def _ffmpeg(*args):
    r = subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *args], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError("ffmpeg: " + r.stderr.strip()[-400:])


def monta(file_scene, durate, wav, ass, uscita, cartella):
    """Ogni scena: fondo che si muove piano (zoom avanti e indietro alternati) + strato fisso. Poi voce e sottotitoli."""
    pezzi = []
    for i, ((fondo, strato), durata) in enumerate(zip(file_scene, list(durate) + [CHIUSURA])):
        n = max(2, round(durata * FPS))
        passo = 0.10 / n
        zoom = f"1+{passo:.6f}*on" if i % 2 == 0 else f"1.10-{passo:.6f}*on"
        pezzo = cartella / f"scena_{i:02d}.mp4"
        _ffmpeg("-i", str(fondo), "-loop", "1", "-i", str(strato), "-filter_complex",
                f"[0:v]scale={W * 2}:{H * 2},zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS}[bg];"
                f"[bg][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
                "-map", "[v]", "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(pezzo))
        pezzi.append(pezzo)
    lista = cartella / "lista.txt"
    lista.write_text("".join(f"file '{p}'\n" for p in pezzi), encoding="utf-8")
    muto = cartella / "muto.mp4"
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(muto))
    def esc(x):
        return str(x).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    _ffmpeg("-i", str(muto), "-i", str(wav), "-vf", f"subtitles='{esc(ass)}':fontsdir='{esc(social.FONT)}'",
            "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart", str(uscita))


def genera(file_pacchetto, cartella_uscita=None):
    import time
    inizio = time.time()
    p = json.loads(Path(file_pacchetto).read_text(encoding="utf-8"))
    scene = scene_dal_copione(p.get("copione"))
    if len(scene) < 2:
        raise SystemExit("ERRORE reel: il copione ha meno di 2 righe utili (campo 'Copione TikTok' del pacchetto)")
    uscita_dir = Path(cartella_uscita or Path.home() / "Desktop" / "Adolos" / "video").expanduser()
    lavoro = ENGINE / "cache" / "reel" / p["id"]
    lavoro.mkdir(parents=True, exist_ok=True)
    uscita_dir.mkdir(parents=True, exist_ok=True)
    foto = None
    try:
        import immagini
        s = {"id": p["id"], "titolo": p["titolo"]}
        foto = immagini.per_storia(s, p["titolo"], [], "", (p.get("sintesi") or "") + " " + " ".join(p.get("punti") or []))
    except Exception as e:
        print("Reel: foto non cercata:", str(e)[:120])
    wav, durate = voce(scene, lavoro)
    file_scene = immagini_scene(p, scene, foto, lavoro)
    ass = sottotitoli(scene, durate, lavoro)
    uscita = uscita_dir / f"adolos-{p['id']}.mp4"
    monta(file_scene, durate, wav, ass, uscita, lavoro)
    print(f"Reel pronto in {time.time() - inizio:.0f} secondi: {uscita} ({sum(durate) + CHIUSURA:.0f} s, "
          f"{uscita.stat().st_size // 1024} KB, {'con foto' if foto else 'senza foto'})")
    return uscita


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python engine/reel.py pacchetto.json [cartella di uscita]")
        sys.exit(1)
    genera(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
