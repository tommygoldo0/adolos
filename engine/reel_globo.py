"""
ADOLOS – clip del globo 3D per i reel (Blender, gratis, sul Mac)
================================================================
Fa due tipi di clip, poi li passa a engine/reel_anim.py che ci scrive sopra le parole:
  - convergenza: i protagonisti della notizia (città) si accendono sul globo e le linee dorate arrivano al luogo;
  - testate: i paesi delle testate che ne parlano si accendono uno alla volta, con le linee verso il luogo.

Serve Blender (brew install --cask blender) e la Terra di notte NASA in ~/.adolos/mappe (python engine/mappa.py scarica).
Se manca una delle due cose, `disponibile()` è falso e il reel usa la mappa piatta, senza errori.
Colori e tempi vengono da engine/stile_reel.py. Un fotogramma costa circa 0,35 secondi: 10 secondi di globo = 2 minuti.
"""

import json
import shutil
import subprocess
from pathlib import Path

import mappa
import stile_reel as ST

ENGINE = Path(__file__).resolve().parent
BLENDER = next((p for p in (shutil.which("blender") or "", "/Applications/Blender.app/Contents/MacOS/Blender")
                if p and Path(p).exists()), None)
TEXTURE = Path.home() / ".adolos" / "mappe" / "notte_8k.jpg"
FFMPEG = next((p for p in ("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", shutil.which("ffmpeg") or "") if p and Path(p).exists()), "ffmpeg")


def _texture():
    """La foto NASA a 8192 x 4096 (la originale è troppo pesante per Blender)."""
    if TEXTURE.exists():
        return TEXTURE
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    img = Image.open(mappa.NOTTE).convert("RGB").resize((8192, 4096), Image.LANCZOS)
    img.save(TEXTURE, quality=92)
    return TEXTURE


def disponibile():
    return bool(BLENDER) and mappa.NOTTE.exists()


def _media_lon(lons):
    import math
    x = sum(math.cos(math.radians(v)) for v in lons)
    y = sum(math.sin(math.radians(v)) for v in lons)
    return math.degrees(math.atan2(y, x))


def _render(scena, durata, lavoro, nome):
    """Blender disegna i fotogrammi (JPEG), ffmpeg li unisce in un mp4 con un po' di bagliore. Restituisce il file mp4."""
    fotogrammi = max(2, round(durata * ST.GLOBO_FPS))
    cartella = lavoro / f"globo_{nome}"
    shutil.rmtree(cartella, ignore_errors=True)
    cartella.mkdir(parents=True)
    scena = dict(scena, fotogrammi=fotogrammi, fps=ST.GLOBO_FPS, larghezza=ST.LARGHEZZA, altezza=ST.ALTEZZA,
                 uscita=str(cartella), texture=str(_texture()), campioni=ST.GLOBO_CAMPIONI,
                 oro=[c / 255 for c in ST.GIALLO])
    f_json = lavoro / f"globo_{nome}.json"
    f_json.write_text(json.dumps(scena), encoding="utf-8")
    r = subprocess.run([BLENDER, "-b", "-P", str(ENGINE / "blender_globo.py"), "--", str(f_json)], capture_output=True, text=True)
    n = len(list(cartella.glob("f_*.jpg")))
    if r.returncode or n < fotogrammi:
        raise RuntimeError(f"Blender: {n}/{fotogrammi} fotogrammi. " + (r.stderr or r.stdout)[-300:])
    mp4 = lavoro / f"globo_{nome}.mp4"
    # il bagliore si calcola in RGB: in YUV colora di viola tutto lo sfondo
    filtro = "format=gbrp,split[a][b];[b]gblur=sigma=16[g];[a][g]blend=all_mode=screen:all_opacity=0.55,format=yuv420p"
    e = subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-framerate", str(ST.GLOBO_FPS), "-i",
                        str(cartella / "f_%04d.jpg"), "-vf", filtro, "-c:v", "libx264", "-crf", "17", "-preset", "veryfast",
                        str(mp4)], capture_output=True, text=True)
    if e.returncode:
        raise RuntimeError("ffmpeg (globo): " + e.stderr[-300:])
    shutil.rmtree(cartella, ignore_errors=True)         # i fotogrammi occupano spazio: si tiene solo l'mp4
    return mp4


def clip_convergenza(p, durata, lavoro):
    """p["globo"] = {"luogo": {"nome", "lon", "lat"}, "attori": [{"nome", "lon", "lat"}, ...]}"""
    g = p["globo"]
    luogo, attori = g["luogo"], g.get("attori", [])
    punti = [dict(a, da=0.4 + 0.5 * i) for i, a in enumerate(attori)] + [dict(luogo, da=durata * 0.40)]
    iluogo = len(punti) - 1
    archi = [{"a": i, "b": iluogo, "da": durata * (0.30 + 0.12 * i), "durata": durata * 0.40} for i in range(len(attori))]
    lons = [a["lon"] for a in attori] or [luogo["lon"]]
    cam = {"da": {"lon": _media_lon(lons), "lat": 36, "distanza": 3.9},
           "a": {"lon": luogo["lon"], "lat": luogo["lat"] + 6, "distanza": 3.3}, "spostamento_y": -0.2}
    return _render({"punti": punti, "archi": archi, "camera": cam}, durata, lavoro, "convergenza")


def codici_testate(p, massimo=12):
    """I paesi delle testate che ne parlano, quelli con più testate per primi (senza doppioni)."""
    conta = {}
    for f in p.get("fonti") or []:
        c = f.get("paese")
        if c and mappa.punto_paese(c):
            conta[c] = conta.get(c, 0) + 1
    for c in p.get("paesi") or []:
        if c and mappa.punto_paese(c):
            conta.setdefault(c, 1)
    return [c for c, _ in sorted(conta.items(), key=lambda kv: -kv[1])][:massimo]


def clip_testate(p, durata, lavoro):
    """Tutti i paesi delle testate si accendono; se c'è un luogo della notizia, le linee vanno verso di lui."""
    codici = codici_testate(p)
    luogo = (p.get("globo") or {}).get("luogo")
    pos = [mappa.punto_paese(c) for c in codici]
    passo = min(0.5, (durata * 0.62) / max(1, len(codici)))
    punti = [{"lon": lon, "lat": lat, "da": 0.25 + passo * i} for i, (lon, lat) in enumerate(pos)]
    archi = []
    if luogo:
        punti.append(dict(luogo, da=0.1))
        il = len(punti) - 1
        archi = [{"a": i, "b": il, "da": 0.5 + passo * i, "durata": 0.9} for i in range(min(10, len(codici)))]
    lons = [x[0] for x in pos] or [0]
    cam = {"da": {"lon": min(lons) - 20, "lat": 28, "distanza": 4.5},
           "a": {"lon": max(lons) + 5, "lat": 24, "distanza": 4.1}, "spostamento_y": -0.11}
    return _render({"punti": punti, "archi": archi, "camera": cam}, durata, lavoro, "testate"), codici
