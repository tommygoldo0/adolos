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
import stile_reel                  # noqa: E402  (lo stile unico dei reel)

W, H, FPS = 1080, 1920, 30
MARGINE = 72
VOCE, LINGUA, VELOCITA = "im_nicola", "it", 1.08
PAUSA = 0.22                       # secondi di silenzio tra una scena e l'altra
CHIUSURA = 2.8                     # secondi della scheda finale "Segui @adolos.it"
FFMPEG = next((p for p in ("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", shutil.which("ffmpeg") or "") if p and Path(p).exists()), "ffmpeg")
BIANCO = (255, 255, 255)


# ---------------------------------------------------------------- copione
def righe_copione(copione):
    """Una scena per riga del copione: [{"voce", "schermo", "numero", "fonte"}]. Toglie i tempi ("[0-2s]" oppure
    "1 (0-3 s)") e le righe di servizio (fonti, nota AI). Forma completa di una riga:
        1 (0-3 s) Testo: scritta breve · Voce: frase letta · Numero: 11.000 · Fonte: El Mundo · Paese: US, CN · Luogo: Shenzhen · Scena: orbite
    "Testo" diventa la scritta della scena, "Voce" è letta dalla voce, "Numero" (facoltativo) è il dato da scrivere
    grande, "Fonte" (facoltativa) è la testata che compare sotto ("Secondo El Mundo"), "Paese" (facoltativo) sono i paesi
    da illuminare sulla mappa di quella scena (codici come US, CN o nomi come Cina), "Luogo" un posto del pacchetto
    ("luoghi") che pulsa sulla mappa, "Scena" forza il tipo di scena (lancio, orbite, domanda)."""
    scene = []
    for riga in (copione or "").splitlines():
        t = re.sub(r"^\s*\[[^\]]*\]\s*", "", riga).strip()
        t = re.sub(r"^\d+\s*\(\s*\d+\s*[-–]\s*\d+\s*s\s*\)\s*", "", t).strip()
        schermo, extra = "", {}
        if re.search(r"\bVoce\s*:", t):
            prima, t = re.split(r"\bVoce\s*:", t, maxsplit=1)
            schermo = re.sub(r"^\s*Testo\s*:\s*", "", prima).strip(" ·-–\"«»")
            pezzi = re.split(r"\s*·\s*(?=(?:Numero|Fonte|Paese|Luogo|Scena)\s*:)", t.strip())
            t = pezzi[0]
            for seg in pezzi[1:]:
                k, _, v = seg.partition(":")
                extra[k.strip().lower()] = v.strip()
        t = re.sub(r"^Testo\s*:\s*", "", t).strip(" ·")
        if not t or t.lower().startswith(("fonti", "testo preparato", "scritta", "voce generata")):
            continue
        t = re.sub(r"\s*Testo preparato con l'aiuto dell'AI.*$", "", t).strip()
        if t:
            scene.append({"voce": t, "schermo": schermo if len(schermo) <= 48 else "",
                          "numero": extra.get("numero", ""), "fonte": extra.get("fonte", ""), "paese": extra.get("paese", ""),
                          "luogo": extra.get("luogo", ""), "scena": extra.get("scena", "")})
    return scene[:stile_reel.MAX_SCENE]


def scene_dal_copione(copione):
    return [r["voce"] for r in righe_copione(copione)]


def copione_da_punti(titolo, punti):
    """Se il pacchetto non ha un copione: apertura dal titolo (la parte dopo i due punti) e una scena per punto."""
    frase = social._divide_titolo(titolo or "")[-1].strip()
    frase = frase[:1].upper() + frase[1:]
    righe = [frase.rstrip(".") + "."] + [x.strip() for x in (punti or []) if x.strip()]
    return "\n".join(righe[:6])


def _da_leggere(testo):
    """Piccoli aggiustamenti perché la voce legga bene numeri e sigle."""
    t = re.sub(r"(\d)\.(\d{3})\b", r"\1\2", testo)            # 1.170 -> 1170
    t = t.replace("%", " per cento").replace("€", " euro")
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------- voce
ULTIMA_VOCE = ""                   # come è stata fatta la voce dell'ultimo reel (la regia lo scrive su Telegram)
USO_ELEVENLABS = Path.home() / ".adolos" / "elevenlabs.json"


def _imp_voce():
    try:
        return json.loads((ENGINE / "fonti.json").read_text(encoding="utf-8")).get("reel_voce", {})
    except Exception:
        return {}


def _n(x):
    return f"{int(x):,}".replace(",", ".")


def _uso_mese():
    """Crediti ElevenLabs usati questo mese dai reel di Adolos (conteggio nostro, sul Mac)."""
    import datetime
    mese = datetime.date.today().strftime("%Y-%m")
    try:
        d = json.loads(USO_ELEVENLABS.read_text(encoding="utf-8"))
    except Exception:
        d = {}
    return d if d.get("mese") == mese else {"mese": mese, "crediti": 0, "reel": 0}


def _segna_uso(crediti, reel=1):
    d = _uso_mese()
    d["crediti"] += int(crediti)
    d["reel"] += reel
    USO_ELEVENLABS.parent.mkdir(parents=True, exist_ok=True)
    USO_ELEVENLABS.write_text(json.dumps(d), encoding="utf-8")
    return d


def voce(scene, cartella):
    """Legge ogni scena. Restituisce (file wav unico, [durata di ogni scena], [tempi delle parole o None]).
    Prima prova ElevenLabs (se c'è la chiave ELEVENLABS_API_KEY e non si supera il tetto del mese), altrimenti Kokoro."""
    global ULTIMA_VOCE
    import os
    imp = _imp_voce()
    chiave = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if os.environ.get("ADOLOS_VOCE") == "locale":         # per le prove: non consuma crediti
        chiave = ""
    if imp.get("motore") == "elevenlabs" and imp.get("elevenlabs_consentito") is True and chiave:
        servono = sum(len(_da_leggere(t)) for t in scene)
        uso = _uso_mese()
        tetto = int(imp.get("tetto_crediti_mese", 9000))
        if uso["crediti"] + servono > tetto:
            ULTIMA_VOCE = f"voce locale gratuita (tetto ElevenLabs del mese raggiunto: {_n(uso['crediti'])} su {_n(tetto)} crediti)"
        else:
            try:
                return _voce_elevenlabs(scene, cartella, imp, chiave, tetto)
            except Exception as e:      # mai il testo della chiave: solo il tipo di errore
                print("Reel: ElevenLabs non ha risposto, uso la voce locale:", str(e)[:160])
                ULTIMA_VOCE = "voce locale gratuita (ElevenLabs non ha risposto)"
    else:
        ULTIMA_VOCE = "voce locale gratuita (Kokoro)"
        if imp.get("motore") == "elevenlabs" and not imp.get("elevenlabs_consentito"):
            print("Reel: ElevenLabs è spento in fonti.json (elevenlabs_consentito = false): voce locale")
    wav, durate = _voce_kokoro(scene, cartella)
    return wav, durate, None


def _voce_elevenlabs(scene, cartella, imp, chiave, tetto):
    """Una richiesta per scena, con i tempi di ogni lettera (servono ai sottotitoli a tempo esatto).
    Ogni richiesta riceve anche la frase prima e dopo, così l'intonazione resta continua."""
    global ULTIMA_VOCE
    import base64
    import urllib.request
    import numpy as np
    import soundfile as sf
    sr, pezzi, durate, tempi, costo = 44100, [], [], [], 0
    testi = [_da_leggere(t) for t in scene]
    for i, testo in enumerate(testi):
        corpo = {"text": testo, "model_id": imp.get("modello", "eleven_multilingual_v2"), "language_code": "it",
                 "voice_settings": imp.get("impostazioni", {"stability": 0.45, "similarity_boost": 0.8, "style": 0.2,
                                                            "use_speaker_boost": True})}
        if i:
            corpo["previous_text"] = testi[i - 1]
        if i + 1 < len(testi):
            corpo["next_text"] = testi[i + 1]
        # stessa frase, stessa voce, stesse impostazioni: si riusa l'audio già fatto (niente crediti spesi due volte)
        import hashlib
        impronta = hashlib.sha1(json.dumps([corpo, imp.get("voce_id")], sort_keys=True).encode()).hexdigest()
        f_cache = cartella / f"el_{i:02d}.json"
        dati = None
        try:
            c = json.loads(f_cache.read_text(encoding="utf-8"))
            if c.get("impronta") == impronta:
                dati = c["dati"]
        except Exception:
            pass
        if dati is None:
            req = urllib.request.Request(
                f"https://api.elevenlabs.io/v1/text-to-speech/{imp.get('voce_id', 'onwK4e9ZLuTAKqWW03F9')}/with-timestamps"
                "?output_format=mp3_44100_128", data=json.dumps(corpo).encode(),
                headers={"xi-api-key": chiave, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                spesi = int(r.headers.get("character-cost") or len(testo))
                dati = json.load(r)
            costo += spesi
            _segna_uso(spesi, reel=0)               # i crediti si contano subito, anche se un'altra scena poi fallisce
            f_cache.write_text(json.dumps({"impronta": impronta, "dati": dati}), encoding="utf-8")
        mp3, wav = cartella / f"el_{i:02d}.mp3", cartella / f"el_{i:02d}.wav"
        mp3.write_bytes(base64.b64decode(dati["audio_base64"]))
        _ffmpeg("-i", str(mp3), "-ar", str(sr), "-ac", "1", str(wav))
        a, _ = sf.read(str(wav), dtype="float32")
        al = dati.get("alignment") or {}
        fine = al.get("character_end_times_seconds") or []
        n = max(1, len(al.get("characters") or []))
        # (frazione del testo letto, secondo) -> per mettere i sottotitoli esattamente sulle parole
        tempi.append([(k / n, t) for k, t in enumerate([0.0] + list(fine))] if fine else None)
        a = np.concatenate([a, np.zeros(int(sr * PAUSA), dtype=a.dtype)])
        pezzi.append(a)
        durate.append(len(a) / sr)
    pezzi.append(np.zeros(int(sr * CHIUSURA), dtype=pezzi[0].dtype))
    file = cartella / "voce.wav"
    sf.write(str(file), np.concatenate(pezzi), sr)
    uso = _segna_uso(0, reel=1)
    ULTIMA_VOCE = (f"ElevenLabs, voce {imp.get('nome_voce', '')}: {_n(costo)} crediti spesi per questo reel, "
                   f"questo mese {_n(uso['crediti'])} su {_n(tetto)}")
    return file, durate, tempi


def _voce_kokoro(scene, cartella):
    """Voce locale gratuita. Restituisce (file wav unico, [durata di ogni scena in secondi])."""
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
    if n_test == 1 and p.get("fonti"):     # una sola testata: si dichiara subito da chi arriva la notizia
        kicker = "Secondo " + p["fonti"][0]["fonte"]
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


def _quando(tempi, frazione):
    """Secondo in cui la voce arriva a quella frazione del testo (dai tempi di ElevenLabs)."""
    for (f0, t0), (f1, t1) in zip(tempi, tempi[1:]):
        if frazione <= f1:
            return t0 + (t1 - t0) * ((frazione - f0) / (f1 - f0) if f1 > f0 else 0)
    return tempi[-1][1]


def sottotitoli(scene, durate, cartella, tempi=None):
    """Tre parole alla volta, grandi e al centro. Con ElevenLabs i tempi sono quelli veri della voce; con la voce locale
    sono stimati dalla lunghezza delle parole dentro ogni scena."""
    return _ass(scene, gruppi_parole(scene, durate, tempi), cartella)


def gruppi_parole(scene, durate, tempi=None, quante=3):
    """[(inizio, fine, [parole], indice della scena)]: poche parole alla volta, a tempo con la voce.
    Con ElevenLabs i tempi sono quelli veri; con la voce locale sono stimati dalla lunghezza delle parole."""
    out, t0 = [], 0.0
    for i, (testo, durata) in enumerate(zip(scene, durate)):
        parole = testo.split()
        gruppi = [parole[k:k + quante] for k in range(0, len(parole), quante)]
        peso = [sum(len(x) for x in g) + len(g) for g in gruppi]
        tot, utile = sum(peso), durata - PAUSA
        tm = (tempi or [None] * len(scene))[i]
        fatti, t = 0, t0
        for k, (g, w) in enumerate(zip(gruppi, peso)):
            if tm:
                a = t0 + _quando(tm, fatti / tot)
                b = t0 + (_quando(tm, (fatti + w) / tot) if k + 1 < len(gruppi) else utile)
            else:
                a, b = t, t + utile * w / tot
            out.append((a, max(a + 0.12, b), g, i))
            t, fatti = b, fatti + w
        t0 += durata
    return out


def _ass(scene, gruppi, cartella):
    righe = ["[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "",
             "[V4+ Styles]",
             "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
             "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
             "Style: A,Instrument Sans,86,&H00FFFFFF,&H00FFFFFF,&H00090810,&H96000000,-1,0,0,0,100,100,0,0,1,7,2,5,60,60,0,1", "",
             "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    for a, b, g, i in gruppi:
        y = 1050 if (i and social._numero_forte(scene[i])) else 1330
        frase = " ".join(g).upper().replace("{", "(").replace("}", ")")
        righe.append(f"Dialogue: 0,{_tempo(a)},{_tempo(b)},A,,0,0,0,,{{\\an5\\pos({W // 2},{y})}}{frase}")
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


def didascalia_reel(p, righe, foto=None):
    """La didascalia da incollare sotto il reel (Instagram e TikTok), sempre della stessa forma seria: testo, domanda ai
    lettori, fonti, "Segui @adolos.it", nota sull'AI, crediti e, dopo tre punti, pochi hashtag sempre uguali."""
    testo = p.get("testo_post") or " ".join(r["voce"] for r in righe[:2])
    nomi = [f["fonte"] for f in p.get("fonti", [])][:5]
    n = int(p.get("n_fonti") or len(p.get("fonti", [])))
    fonti = "Fonti: " + ", ".join(nomi) + (f" e altre {n - len(nomi)}." if n > len(nomi) else ".")
    crediti = []
    if (foto or {}).get("credito"):
        crediti.append(foto["credito"] + ".")
    try:
        import mappa
        if mappa.disponibile():
            crediti.append(mappa.CREDITO)
    except Exception:
        pass
    parti = [testo, p.get("didascalia_domanda", ""), fonti, social.SEGUI, social.NOTA_AI + " Voce generata con AI."] + crediti
    tag = list(dict.fromkeys(list(social.HASHTAG_FISSI) + [social.HASHTAG_SEZIONE.get(p.get("sezione"), "")]))
    coda = "\n.\n.\n.\n" + " ".join(x for x in tag if x)
    corpo = "\n\n".join(x for x in parti if x)
    return corpo[:2190 - len(coda)].rstrip() + coda + "\n"


def genera(file_pacchetto, cartella_uscita=None):
    import time
    inizio = time.time()
    p = json.loads(Path(file_pacchetto).read_text(encoding="utf-8"))
    stile_reel.controlla()                       # un solo stile Adolos: se i file del reel escono dallo stile, si ferma
    righe = righe_copione(p.get("copione"))
    if len(righe) < 2:
        righe = righe_copione(copione_da_punti(p.get("titolo"), p.get("punti")))
    scene = [r["voce"] for r in righe]
    if len(scene) < 2:
        raise SystemExit("ERRORE reel: il copione ha meno di 2 righe utili (campo 'Copione TikTok' del pacchetto)")
    uscita_dir = Path(cartella_uscita or Path.home() / "Desktop" / "Adolos" / "video").expanduser()
    lavoro = Path.home() / ".adolos" / "lavoro" / "reel" / p["id"]        # fuori dalla Scrivania: iCloud non deve sincronizzare i fotogrammi
    lavoro.mkdir(parents=True, exist_ok=True)
    uscita_dir.mkdir(parents=True, exist_ok=True)
    foto = None
    try:
        if p.get("senza_foto"):                  # es. non si sa se la foto trovata mostra proprio quel razzo/luogo/persona
            raise RuntimeError("foto non cercata (senza_foto)")
        import immagini
        s = {"id": p["id"], "titolo": p["titolo"]}
        foto = immagini.per_storia(s, p["titolo"], [], "", (p.get("sintesi") or "") + " " + " ".join(p.get("punti") or []))
    except Exception as e:
        print("Reel: foto non cercata:", str(e)[:120])
    wav, durate, tempi = voce(scene, lavoro)
    uscita = uscita_dir / f"adolos-{p['id']}.mp4"
    if _imp_voce().get("stile_video", "infografica") == "infografica":
        import reel_anim
        with stile_reel.carattere_reel():
            reel_anim.rendi(p, righe, durate, tempi, foto, wav, uscita, lavoro)
    else:                                        # stile di prima: foto che si muove + sottotitoli ASS
        file_scene = immagini_scene(p, scene, foto, lavoro)
        ass = sottotitoli(scene, durate, lavoro, tempi)
        monta(file_scene, durate, wav, ass, uscita, lavoro)
    try:
        (uscita_dir / f"adolos-{p['id']}-didascalia.txt").write_text(didascalia_reel(p, righe, foto), encoding="utf-8")
    except Exception as e:
        print("Reel: didascalia non scritta:", str(e)[:120])
    print(f"Reel pronto in {time.time() - inizio:.0f} secondi: {uscita} ({sum(durate) + CHIUSURA:.0f} s, "
          f"{uscita.stat().st_size // 1024} KB, {'con foto' if foto else 'senza foto'}) · {ULTIMA_VOCE}")
    return uscita


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python engine/reel.py pacchetto.json [cartella di uscita]")
        sys.exit(1)
    genera(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
