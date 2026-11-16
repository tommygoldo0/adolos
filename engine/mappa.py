"""
ADOLOS – mappa notturna per i reel
==================================
Fondo "Terra di notte" con il paese della notizia illuminato in giallo, e mappa del mondo con i paesi delle testate
che si accendono. Serve a engine/reel_anim.py.

File (pubblici, scaricati una volta sul Mac, fuori dal repository):
  ~/.adolos/mappe/BlackMarble_2016_3km.jpg           NASA Earth Observatory, Black Marble 2016 (pubblico dominio)
  ~/.adolos/mappe/ne_50m_admin_0_countries.geojson   Natural Earth, confini dei paesi 1:50m (pubblico dominio)
Per riscaricarli: python engine/mappa.py scarica
Se mancano, il reel usa la foto sfocata come prima (niente errori).
"""

import json
import math
import re
import sys
from functools import lru_cache
from pathlib import Path

CARTELLA = Path.home() / ".adolos" / "mappe"
NOTTE = CARTELLA / "BlackMarble_2016_3km.jpg"
CONFINI = CARTELLA / "ne_50m_admin_0_countries.geojson"
URL = {NOTTE: "https://assets.science.nasa.gov/content/dam/science/esd/eo/images/imagerecords/144000/144898/BlackMarble_2016_3km.jpg",
       CONFINI: "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson"}
CREDITO = "Mappa: NASA Earth Observatory (Black Marble), confini Natural Earth."
GIALLO = (255, 212, 0)
S_MIN = 0.011            # gradi per pixel: oltre, la foto NASA (3 km per pixel) si sgrana troppo


def disponibile():
    return NOTTE.exists() and CONFINI.exists()


def scarica():
    import urllib.request
    CARTELLA.mkdir(parents=True, exist_ok=True)
    for file, url in URL.items():
        if not file.exists():
            print("Scarico", file.name, "...")
            urllib.request.urlretrieve(url, file)
    print("Mappe pronte in", CARTELLA)


# ---------------------------------------------------------------- paesi
@lru_cache(maxsize=1)
def _paesi():
    d = json.loads(CONFINI.read_text(encoding="utf-8"))
    out = {}
    for f in d["features"]:
        pr = f["properties"]
        cod = pr.get("ISO_A2_EH") if pr.get("ISO_A2_EH") not in (None, "-99") else pr.get("ISO_A2")
        if not cod or cod == "-99":
            continue
        g = f["geometry"]
        poligoni = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        anelli = [p[0] for p in poligoni]
        nome = pr.get("NAME_IT") or pr.get("NAME")
        if cod in out:      # stesso codice per più territori (es. Australia e isole Ashmore): si uniscono
            if max(map(_area, anelli)) > max(map(_area, out[cod]["anelli"])):
                out[cod]["nome"] = nome
            out[cod]["anelli"] += anelli
        else:
            out[cod] = {"nome": nome, "anelli": anelli}
    return out


def _area(r):
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1]))) / 2


@lru_cache(maxsize=256)
def _principale(cod):
    return max(_paesi()[cod]["anelli"], key=_area)


def centro(cod):
    r = _principale(cod)
    xs, ys = [p[0] for p in r], [p[1] for p in r]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


# capitali (lon, lat), punti indicativi per i segnaposto del globo: dove manca si usa il centro del paese
CAPITALI = {
    "US": (-77.04, 38.90), "GB": (-0.13, 51.50), "FR": (2.35, 48.85), "DE": (13.40, 52.52), "IT": (12.50, 41.90),
    "ES": (-3.70, 40.42), "PT": (-9.14, 38.72), "NL": (4.90, 52.37), "BE": (4.35, 50.85), "CH": (7.45, 46.95),
    "AT": (16.37, 48.20), "PL": (21.01, 52.23), "CZ": (14.42, 50.08), "RO": (26.10, 44.43), "HU": (19.04, 47.50),
    "GR": (23.73, 37.98), "SE": (18.07, 59.33), "NO": (10.75, 59.91), "DK": (12.57, 55.68), "FI": (24.94, 60.17),
    "IE": (-6.26, 53.35), "UA": (30.52, 50.45), "RU": (37.62, 55.75), "TR": (32.85, 39.93), "IL": (35.22, 31.77),
    "SA": (46.72, 24.63), "AE": (54.37, 24.45), "QA": (51.53, 25.29), "EG": (31.24, 30.04), "IR": (51.39, 35.69),
    "IQ": (44.37, 33.31), "IN": (77.21, 28.61), "PK": (73.05, 33.68), "CN": (116.40, 39.90), "JP": (139.69, 35.69),
    "KR": (126.98, 37.57), "TW": (121.56, 25.03), "HK": (114.17, 22.32), "SG": (103.82, 1.35), "TH": (100.50, 13.75),
    "VN": (105.84, 21.03), "ID": (106.85, -6.21), "PH": (120.98, 14.60), "MY": (101.69, 3.14), "AU": (149.13, -35.28),
    "NZ": (174.78, -41.29), "CA": (-75.70, 45.42), "MX": (-99.13, 19.43), "BR": (-47.93, -15.78), "AR": (-58.38, -34.60),
    "CL": (-70.65, -33.45), "CO": (-74.07, 4.71), "PE": (-77.04, -12.05), "VE": (-66.90, 10.48), "PY": (-57.58, -25.26),
    "UY": (-56.16, -34.90), "ZA": (28.19, -25.75), "NG": (7.40, 9.06), "KE": (36.82, -1.29), "ET": (38.74, 9.03),
    "MA": (-6.84, 34.02), "DZ": (3.06, 36.75), "TN": (10.18, 36.80), "GH": (-0.19, 5.56), "MD": (28.86, 47.01),
    "RS": (20.46, 44.79), "CY": (33.38, 35.17), "LV": (24.10, 56.95), "LT": (25.28, 54.69), "EE": (24.75, 59.44),
    "BG": (23.32, 42.70), "HR": (15.98, 45.81), "SK": (17.11, 48.15), "SI": (14.51, 46.06), "AZ": (49.87, 40.41),
    "AM": (44.50, 40.18), "GE": (44.80, 41.72), "KZ": (71.43, 51.13), "AF": (69.17, 34.53), "LB": (35.50, 33.89),
    "JO": (35.93, 31.95), "KW": (47.98, 29.38), "BD": (90.41, 23.81), "LK": (79.86, 6.93), "NP": (85.32, 27.72),
    "MM": (96.20, 16.80), "KH": (104.92, 11.56), "BY": (27.57, 53.90), "IS": (-21.90, 64.15), "LU": (6.13, 49.61),
}


def punto_paese(cod):
    """(lon, lat) della capitale; se non c'è, il centro del paese; se il paese non si trova, None."""
    if cod in CAPITALI:
        return CAPITALI[cod]
    return centro(cod) if esiste(cod) else None


def esiste(cod):
    return disponibile() and cod in _paesi()


def codice_da_testo(testo, nomi_extra=None):
    """Il paese nominato nel testo (es. "Spagna: primo sciopero..." -> ES). Prima i nomi più lunghi."""
    if not disponibile() or not testo:
        return None
    nomi = {v["nome"].lower(): k for k, v in _paesi().items() if v.get("nome")}
    nomi.update({"gaza": "PS", "cisgiordania": "PS", "usa": "US", "casa bianca": "US", "cremlino": "RU",
                 "stati uniti": "US", "regno unito": "GB", "inghilterra": "GB", "scozia": "GB", "taiwan": "TW"})
    for k, v in (nomi_extra or {}).items():
        if k in _paesi():
            nomi.setdefault(v.lower(), k)
    t = testo.lower()
    for nome in sorted(nomi, key=len, reverse=True):
        if len(nome) > 3 and re.search(r"(?<!\w)" + re.escape(nome) + r"(?!\w)", t):
            return nomi[nome]
    return None


# ---------------------------------------------------------------- disegno
class Vista:
    """Proiezione semplice (equirettangolare corretta per la latitudine): lon/lat -> pixel della tela."""

    def __init__(self, lon0, lat0, s, w, h, cy):
        self.lon0, self.lat0, self.s, self.w, self.h, self.cy = lon0, lat0, s, w, h, cy
        self.k = max(0.25, math.cos(math.radians(lat0)))

    def xy(self, lon, lat):
        dlon = ((lon - self.lon0 + 180) % 360) - 180
        return self.w / 2 + dlon * self.k / self.s, self.cy - (lat - self.lat0) / self.s


@lru_cache(maxsize=2)
def _notte(ridotta):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None          # file NASA noto: 13500 x 6750
    img = Image.open(NOTTE)
    if ridotta:                            # per le viste larghe e per quelle che passano la linea del cambio data
        img.draft("RGB", (img.width // 4, img.height // 4))
        img = img.convert("RGB")
        from PIL import Image as I
        tripla = I.new("RGB", (img.width * 3, img.height))
        for i in range(3):
            tripla.paste(img, (i * img.width, 0))
        return tripla, img.width
    return img.convert("RGB"), img.width


def _sfondo(v):
    from PIL import Image, ImageEnhance
    largo = v.w * v.s / v.k                                    # gradi di longitudine visibili
    x_sx = v.lon0 - largo / 2
    ridotta = v.s > 0.06 or x_sx < -180 or x_sx + largo > 180
    src, larghezza = _notte(ridotta)
    sw, sh = larghezza, src.height
    base = sw if ridotta else 0                                # nella copia tripla si parte da quella di mezzo
    a = v.s / v.k / 360 * sw
    c = base + (v.lon0 - v.w / 2 * v.s / v.k + 180) / 360 * sw
    e = v.s / 180 * sh
    f = (90 - v.lat0 - v.cy * v.s) / 180 * sh
    img = src.transform((v.w, v.h), Image.AFFINE, (a, 0, c, 0, e, f), resample=Image.BILINEAR, fillcolor=(3, 5, 12))
    return ImageEnhance.Brightness(img).enhance(0.92)


def strato_paesi(v, codici, forte=True):
    """Paesi illuminati: riempimento giallo trasparente, bordo giallo e un alone."""
    from PIL import Image, ImageDraw, ImageFilter
    riempi = Image.new("RGBA", (v.w, v.h), (0, 0, 0, 0))
    bordo = Image.new("RGBA", (v.w, v.h), (0, 0, 0, 0))
    dr, db = ImageDraw.Draw(riempi), ImageDraw.Draw(bordo)
    for cod in codici:
        if cod not in _paesi():
            continue
        for anello in _paesi()[cod]["anelli"]:
            lons = [p[0] for p in anello]
            if max(lons) - min(lons) > 180:                    # anelli a cavallo del cambio data: si saltano
                continue
            punti = [v.xy(lon, lat) for lon, lat in anello]
            xs, ys = [p[0] for p in punti], [p[1] for p in punti]
            if max(xs) < 0 or min(xs) > v.w or max(ys) < 0 or min(ys) > v.h or len(punti) < 3:
                continue
            dr.polygon(punti, fill=GIALLO + ((62 if forte else 46),))
            db.line(punti + [punti[0]], fill=GIALLO + (235,), width=3 if forte else 2, joint="curve")
    alone = bordo.filter(ImageFilter.GaussianBlur(9))
    out = Image.alpha_composite(riempi, alone)
    out = Image.alpha_composite(out, alone)
    return Image.alpha_composite(out, bordo)


def vista_paese(cod, w, h, cy, larghezza_frame=1080, altezza_frame=1920):
    r = _principale(cod)
    xs, ys = [p[0] for p in r], [p[1] for p in r]
    lon0, lat0 = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    k = max(0.25, math.cos(math.radians(lat0)))
    s = max((max(xs) - min(xs)) * k / (0.62 * larghezza_frame), (max(ys) - min(ys)) / (0.36 * altezza_frame), S_MIN)
    return Vista(lon0, lat0, min(s, 0.25), w, h, cy)


def vista_insieme(codici, w, h, cy, larghezza_frame=1080, altezza_frame=1920):
    punti = [centro(c) for c in codici if c in _paesi()]
    if not punti:
        return Vista(10, 30, 0.12, w, h, cy)
    lons, lats = [p[0] for p in punti], [p[1] for p in punti]
    # longitudine: si cerca il "giro" più corto (es. Giappone + Stati Uniti passano dal Pacifico)
    lons_s = sorted(lons)
    salti = [(lons_s[(i + 1) % len(lons_s)] - lons_s[i]) % 360 for i in range(len(lons_s))]
    i = max(range(len(salti)), key=salti.__getitem__)
    inizio = lons_s[(i + 1) % len(lons_s)]
    ampiezza = 360 - salti[i] if len(lons_s) > 1 else 0
    lon0 = ((inizio + ampiezza / 2 + 180) % 360) - 180
    lat0 = (min(lats) + max(lats)) / 2
    k = max(0.25, math.cos(math.radians(lat0)))
    s = max((ampiezza + 30) * k / (0.86 * larghezza_frame), (max(lats) - min(lats) + 22) / (0.30 * altezza_frame), 0.03)
    return Vista(lon0, lat0, s, w, h, cy)


def fondo(v, codici=(), forte=True):
    """Immagine RGB della vista, con i paesi indicati già illuminati."""
    from PIL import Image
    img = _sfondo(v).convert("RGBA")
    if codici:
        img = Image.alpha_composite(img, strato_paesi(v, codici, forte))
    return img.convert("RGB")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "scarica":
        scarica()
    else:
        print("Mappe", "presenti" if disponibile() else "mancanti (python engine/mappa.py scarica)", "in", CARTELLA)
