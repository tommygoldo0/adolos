"""
ADOLOS – motore notizie
=======================
Raccoglie notizie da oltre 100 paesi, le raggruppa per storia, calcola il "calore",
decide cosa pubblicare e cosa lasciare in bozza, e scrive i dati per il sito.

Comandi:
  python engine/adolos.py                 -> raccolta dal vivo + aggiornamento sito
  python engine/adolos.py --campione      -> usa i titoli di prova (senza internet)
  python engine/adolos.py approva <id>    -> pubblica una bozza
  python engine/adolos.py rifiuta <id>    -> nasconde una storia
"""

import hashlib
import os

import html
import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
ENGINE = RADICE / "engine"
SITO_DATI = RADICE / "site" / "data"
CACHE = ENGINE / "cache"                 # dati di lavoro: NON pubblici (salvati nella cache di GitHub Actions)
ARCHIVIO = CACHE / "archivio_items.json"
APPROVATI = ENGINE / "approvati.json"
FINESTRA_ORE = 48           # quanto indietro guardiamo
MAX_STORIE = 400            # quante storie finiscono nel sito

UA = "Mozilla/5.0 (compatible; AdolosBot/1.0; +https://github.com)"

# ---------------------------------------------------------------- paesi
PAESI = {
    "US": "Stati Uniti", "GB": "Regno Unito", "IT": "Italia", "FR": "Francia", "DE": "Germania", "ES": "Spagna",
    "PT": "Portogallo", "BR": "Brasile", "MX": "Messico", "AR": "Argentina", "CO": "Colombia", "CL": "Cile",
    "PE": "Perù", "VE": "Venezuela", "CU": "Cuba", "EC": "Ecuador", "UY": "Uruguay", "PY": "Paraguay",
    "JP": "Giappone", "KR": "Corea del Sud", "CN": "Cina", "TW": "Taiwan", "HK": "Hong Kong", "IN": "India",
    "PK": "Pakistan", "BD": "Bangladesh", "LK": "Sri Lanka", "NP": "Nepal", "TH": "Thailandia", "VN": "Vietnam",
    "ID": "Indonesia", "MY": "Malesia", "PH": "Filippine", "SG": "Singapore", "AU": "Australia", "NZ": "Nuova Zelanda",
    "CA": "Canada", "ZA": "Sudafrica", "NG": "Nigeria", "KE": "Kenya", "GH": "Ghana", "UG": "Uganda", "TZ": "Tanzania",
    "ZW": "Zimbabwe", "NA": "Namibia", "BW": "Botswana", "ET": "Etiopia", "EG": "Egitto", "SA": "Arabia Saudita",
    "AE": "Emirati Arabi", "LB": "Libano", "QA": "Qatar", "KW": "Kuwait", "JO": "Giordania", "IQ": "Iraq", "IR": "Iran",
    "IL": "Israele", "TR": "Turchia", "MA": "Marocco", "DZ": "Algeria", "TN": "Tunisia", "SN": "Senegal",
    "CI": "Costa d'Avorio", "CM": "Camerun", "RU": "Russia", "UA": "Ucraina", "KZ": "Kazakistan", "PL": "Polonia",
    "CZ": "Rep. Ceca", "SK": "Slovacchia", "HU": "Ungheria", "RO": "Romania", "BG": "Bulgaria", "GR": "Grecia",
    "RS": "Serbia", "HR": "Croazia", "SI": "Slovenia", "EE": "Estonia", "LV": "Lettonia", "LT": "Lituania",
    "NL": "Paesi Bassi", "BE": "Belgio", "CH": "Svizzera", "AT": "Austria", "SE": "Svezia", "NO": "Norvegia",
    "DK": "Danimarca", "FI": "Finlandia", "IE": "Irlanda", "AF": "Afghanistan", "SY": "Siria", "YE": "Yemen",
    "SD": "Sudan", "LY": "Libia", "CD": "Congo (RDC)", "AO": "Angola", "MZ": "Mozambico", "ZM": "Zambia",
    "RW": "Ruanda", "MM": "Myanmar", "KH": "Cambogia", "LA": "Laos", "MN": "Mongolia", "GE": "Georgia",
    "AM": "Armenia", "AZ": "Azerbaigian", "BY": "Bielorussia", "MD": "Moldavia", "AL": "Albania",
    "BA": "Bosnia ed Erzegovina", "MK": "Macedonia del Nord", "ME": "Montenegro", "XK": "Kosovo", "IS": "Islanda",
    "CY": "Cipro", "MT": "Malta", "LU": "Lussemburgo", "HT": "Haiti", "DO": "Rep. Dominicana", "GT": "Guatemala",
    "HN": "Honduras", "PA": "Panama", "CR": "Costa Rica", "JM": "Giamaica", "BO": "Bolivia", "VA": "Vaticano",
    "QA": "Qatar", "CG": "Congo", "PS": "Palestina", "WEB": "Web/social",
}

# testate internazionali con dominio .com: il paese vero della redazione
TESTATE_PAESE = {
    "bbc.": "GB", "reuters.com": "GB", "theguardian.com": "GB", "economist.com": "GB", "ft.com": "GB",
    "telegraph.co": "GB", "independent.co": "GB", "apnews.com": "US", "nytimes.com": "US", "washingtonpost.com": "US",
    "wsj.com": "US", "cnn.com": "US", "foxnews.com": "US", "nbcnews.com": "US", "cbsnews.com": "US", "abcnews": "US",
    "bloomberg.com": "US", "politico.com": "US", "aljazeera.com": "QA", "aljazeera.net": "QA", "france24.com": "FR", "rfi.fr": "FR",
    "euronews.com": "FR", "dw.com": "DE", "scmp.com": "HK", "vaticannews.va": "VA", "aol.co": "GB",
}
TLD_PAESE = {"uk": "GB", "gr": "GR", "va": "VA", "eu": None, "com": None, "org": None, "net": None, "info": None,
             "news": None, "co": None, "tv": None, "me": None, "io": None, "web": None}


def paese_da_sito(sito, predefinito):
    """Prova a capire il paese della testata dal suo indirizzo; se non si riesce usa l'edizione."""
    host = re.sub(r"^https?://", "", (sito or "").lower()).split("/")[0]
    if not host:
        return predefinito
    for chiave, cc in TESTATE_PAESE.items():
        if chiave in host:
            return cc
    tld = host.rsplit(".", 1)[-1]
    if tld in TLD_PAESE:
        return TLD_PAESE[tld] or predefinito
    cc = tld.upper()
    return cc if cc in PAESI else predefinito

# ---------------------------------------------------------------- categorie
CATEGORIE = {
    "Politica": ["governo", "elezion", "partito", "ministr", "parlament", "senato", "premier", "presidente", "meloni",
                 "salvini", "schlein", "government", "election", "minister", "senate", "congress", "parliament",
                 "gouvernement", "élection", "regierung", "wahl", "gobierno", "elecciones", "eleições", "governo",
                 "lula", "bolsonaro", "psoe", "podemos", "trump", "casa bianca", "white house", "maison blanche",
                 "portavoce", "press secretary", "sprecherin", "porte-parole", "secretária de imprensa", "voto", "vote"],
    "Esteri e conflitti": ["guerra", "ucraina", "ukraine", "kiev", "kyiv", "zelensky", "selenskyj", "putin", "russia",
                           "israel", "gaza", "cisgiordania", "west bank", "hamas", "huthi", "houthi", "jemen", "yemen",
                           "nato", "onu", "un security", "missil", "drone", "dron", "esercito", "army", "militar",
                           "starlink", "starshield", "tregua", "ceasefire", "waffenruhe", "settlers", "coloni"],
    "Economia": ["econom", "inflazion", "inflation", "pil", "gdp", "borsa", "mercat", "market", "tasse", "fisco",
                 "irpef", "tfr", "bollette", "gasolio", "carburant", "benzina", "prezzo", "prezzi", "price",
                 "bce", "fed ", "banca", "bank", "imf", "fmi", "world bank", "lavoro", "jobs", "licenziament",
                 "layoff", "azienda", "company", "fraude", "fraud", "americanas", "tabak", "oecd"],
    "Cronaca": ["arrest", "omicid", "uccis", "morto", "morti", "morte", "incidente", "polizia", "carabinieri",
                "indagin", "processo", "delitto", "killed", "shooting", "shooter", "police", "murder", "dead",
                "died", "crash", "fusillade", "tireur", "enquête", "angriff", "tote", "häftling", "juez", "imputa",
                "assaltar", "criminosos", "nurse", "arson", "fire", "evacuation", "incendi"],
    "Sport": ["calcio", "serie a", "champions", "inter", "juventus", "milan", "napoli", "lautaro", "gol", "partita",
              "football", "soccer", "nba", "nfl", "tennis", "sinner", "formula 1", "f1", "olimpi", "olympic",
              "mondiali", "world cup", "match", "allenatore", "coach"],
    "Tecnologia e crypto": ["bitcoin", "crypto", "cripto", "blockchain", "intelligenza artificiale", "artificial intelligence",
                            " ai ", "openai", "apple", "google", "meta", "musk", "tesla", "spacex", "chip", "smartphone",
                            "hacker", "cyber", "app ", "whatsapp", "tiktok", "instagram"],
    "Clima e ambiente": ["meteo", "maltempo", "alluvion", "terremoto", "sisma", "earthquake", "tifone", "typhoon",
                         "tempesta", "storm", "sturmflut", "uragano", "hurricane", "clima", "climate", "siccità",
                         "tormentas", "chubascos", "台風", "地震", "ฝน", "wildfire", "brush fires", "santa ana"],
    "Società": ["papa", "pope", "papst", "vatican", "chiesa", "scuola", "studenti", "students", "lycéen", "università",
                "sanità", "ospedale", "hospital", "salute", "health", "nhs", "proteste", "protesta", "protest",
                "manifestazion", "sciopero", "strike", "mobilisation", "immigra", "migranti", "migrants", "ebola", "virus",
                "epidemi", "pandemi", "covid", "vaccin", "malattia", "disease"],
}
PAROLE_CURIOSITA = ["curios", "bizzarr", "incredibile", "record", "virale", "viral", "weird", "bizarre", "strange",
                    "insolite", "insólito", "kurios", "tiger", "tigre", "sassofono", "saxophone", "sax", "lotteria",
                    "lottery", "jackpot", "travestit", "disguised", "mistero", "mystery",
                    "milionari", "หวย", "แซ็กโซโฟน", "gigante", "giant", "più grande", "world's largest", "primo al mondo"]
PAROLE_TRAGICHE = ["killed", "uccis", "morti", "morto", "morte", "death", "dead", "died", "shooting", "shooter",
                   "fusillade", "tireur", "attentat", "attack", "attacco", "angriff", "victim", "vittim", "war", "guerra",
                   "abuse", "abusi", "stupro", "rape", "pogrom", "tote"]
PAROLE_SCALPORE = ["esclusiv", "exclusive", "shock", "choc", "scandal", "breaking", "ultim'ora", "urgente",
                   "dimess", "resign", "licenzia", "fired", "gefeuert", "demitid", "arrestat", "arrested",
                   "smentisce", "denies", "leak", "trapelat", "rivelaz", "reveal", "bomba", "strage",
                   "massacre", "killed", "uccis", "morti", "attacco", "attack", "angriff", "guerra", "war"]

STOP_ENT = set("""
The This That With From After Before Over Under About Into Their There These Those What When Where Which While
Exclusive Live Video Foto Breaking News Update Oggi Ieri Domani Ecco Come Perché Dopo Sono Anche Ancora Della Delle
Dalla Nella Nelle Questo Questa Tutti Tutto Sabato Domenica Lunedì Martedì Mercoledì Giovedì Venerdì Monday Tuesday
Wednesday Thursday Friday Saturday Sunday Diese Nach Eine Einer Wird Pour Avec Dans Sans Cette Leur Para Como Pero
Desde Entre Sobre Será Ante Mais Pelo Pela Após DIRECT DIRETTA Direct Diretta Casa Bianca White House Weißen Hauses
Maison Blanche Blanca
Consiglio Sicurezza Stati Uniti Banca Mondiale Fondo Monetario Internazionale Corte Suprema Nazioni Unite Unione
Europea Primo Ministro Presidente Governo Paese Paesi Città Regione Polizia Ministero Partito Nuova Nuovo Ultim
Guerra Notizie Secondo Mentre Questa Quando Dove Perché Cosa Chi Gli Una Uno Dal Alla Nel Sul Per Con Tra
""".split())


# ---------------------------------------------------------------- utilità
def ora_utc():
    return datetime.now(timezone.utc)


def a_data(valore):
    """Converte date RSS / ISO / GDELT in datetime UTC."""
    if not valore:
        return None
    if isinstance(valore, datetime):
        return valore.astimezone(timezone.utc)
    s = str(valore).strip()
    for prova in (
        lambda x: parsedate_to_datetime(x),
        lambda x: datetime.fromisoformat(x.replace("Z", "+00:00")),
        lambda x: datetime.strptime(x, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc),
    ):
        try:
            d = prova(s)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d.astimezone(timezone.utc)
        except Exception:
            pass
    return None


def pulisci(testo):
    testo = html.unescape(re.sub(r"<[^>]+>", " ", testo or ""))
    return re.sub(r"\s+", " ", testo).strip()


def normalizza(testo):
    t = unicodedata.normalize("NFKD", testo.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^\w\s]", " ", t)


def togli_fonte_dal_titolo(titolo, fonte):
    """Google News scrive 'Titolo - Fonte': togliamo la coda."""
    if fonte and titolo.endswith(" - " + fonte):
        return titolo[: -len(fonte) - 3].strip()
    return re.sub(r"\s[-–]\s[^-–]{2,40}$", "", titolo).strip() if " - " in titolo else titolo


def lingua_da_hl(hl):
    return (hl or "").split("-")[0].lower() or "?"


def fid(*parti):
    return hashlib.sha1("|".join(parti).encode("utf-8")).hexdigest()[:10]


def leggi_json(percorso, default):
    try:
        return json.loads(Path(percorso).read_text(encoding="utf-8"))
    except Exception:
        return default


def scrivi_json(percorso, dati):
    Path(percorso).write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")


def item(titolo, link, data, fonte, paese, lingua, tipo, origine, riassunto="", gruppo=None, correlati=0,
         sezione=None):
    # niente foto delle testate: le immagini altrui non si importano (vedi LEGGIMI, regole legali)
    titolo = pulisci(titolo)
    return {
        "sezione_hint": sezione,     # se arriva da un feed per argomento (tecnologia, sport, curiosità...)
        "id": fid(link or titolo),
        "titolo": titolo[:220],
        "titolo_it": titolo[:220] if lingua == "it" else None,   # traduzione italiana (vedi traduci.py)
        "link": link,
        "data": (a_data(data) or ora_utc()).isoformat(),
        "fonte": pulisci(fonte) or "Sconosciuta",
        "paese": paese,
        "lingua": lingua,
        "tipo": tipo,                # agenzia | giornale | social
        "origine": origine,          # rss | gdelt (google_news, reddit, telegram solo se riattivati con permesso)
        "riassunto": pulisci(riassunto)[:400],   # descrizione del feed: serve solo alla sintesi, non va mai sul sito
        "gruppo": gruppo,            # suggerimento: stessi articoli correlati su Google News
        "correlati": correlati,
    }


# ---------------------------------------------------------------- raccolta dal vivo
def scarica(url, timeout=20):
    import requests
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r.text


RE_CORRELATI = re.compile(r'<a href="([^"]+)"[^>]*>([^<]+)</a>(?:&nbsp;|\s)*<font[^>]*>([^<]+)</font>')


ARGOMENTI_GN = {"TECHNOLOGY": "Tecnologia", "SCIENCE": "Tecnologia", "SPORTS": "Sport", "BUSINESS": "Economia",
                 "ENTERTAINMENT": "Società", "HEALTH": "Società"}


def da_google_news(edizione, argomento=None, ricerca=None, sezione=None):
    """Prima pagina di Google News di un paese; oppure una sua sezione (argomento) o una ricerca."""
    import feedparser
    from urllib.parse import quote
    paese, hl = edizione.split(":")
    lingua_ceid = hl.split("-")[0]
    coda = f"hl={hl}&gl={paese}&ceid={paese}:{lingua_ceid}"
    if argomento:
        url = f"https://news.google.com/rss/headlines/section/topic/{argomento}?{coda}"
        sezione = sezione or ARGOMENTI_GN.get(argomento)
    elif ricerca:
        url = f"https://news.google.com/rss/search?q={quote(ricerca)}&{coda}"
    else:
        url = f"https://news.google.com/rss?{coda}"
    feed = feedparser.parse(scarica(url))
    lingua = lingua_da_hl(hl)
    out = []
    for e in feed.entries[:40]:
        fonte = getattr(e, "source", {}).get("title", "") if hasattr(e, "source") else ""
        sito = getattr(e, "source", {}).get("href", "") if hasattr(e, "source") else ""
        principale = item(togli_fonte_dal_titolo(e.title, fonte), e.link, e.get("published"), fonte, paese_da_sito(sito, paese),
                          lingua, "giornale", "google_news", sezione=sezione)
        desc = html.unescape(e.get("summary", ""))
        rel = RE_CORRELATI.findall(desc)
        principale["gruppo"] = principale["id"]
        principale["correlati"] = len(rel)
        out.append(principale)
        for link, tit, f in rel:
            if pulisci(f) == principale["fonte"]:
                continue
            out.append(item(togli_fonte_dal_titolo(html.unescape(tit), f), link, e.get("published"), f,
                            paese_da_sito(link if "news.google" not in link else "", paese),
                            lingua, "giornale", "google_news", gruppo=principale["id"], sezione=sezione))
    return out


LINGUE_GDELT = {"English": "en", "Italian": "it", "French": "fr", "German": "de", "Spanish": "es",
                "Portuguese": "pt", "Arabic": "ar", "Russian": "ru", "Turkish": "tr", "Chinese": "zh"}


def da_gdelt(nome, codice):
    url = ("https://api.gdeltproject.org/api/v2/doc/doc?query=sourcecountry:" + nome +
           "&mode=artlist&format=json&maxrecords=40&sort=datedesc&timespan=6h")
    dati = json.loads(scarica(url) or "{}")
    return [item(a.get("title", ""), a.get("url"), a.get("seendate"), a.get("domain", ""),
                 paese_da_sito(a.get("domain", ""), codice),
                 LINGUE_GDELT.get(a.get("language", ""), "?"), "giornale", "gdelt")
            for a in dati.get("articles", []) if a.get("title")]


def da_rss(fonte):
    import feedparser
    feed = feedparser.parse(scarica(fonte["url"]))
    lingua = (feed.feed.get("language") or "en")[:2].lower()
    tipo = "agenzia" if fonte.get("tipo") == "agenzia" else "giornale"
    return [item(e.get("title", ""), e.get("link"), e.get("published") or e.get("updated"), fonte["nome"],
                 fonte["paese"], lingua, tipo, "rss", riassunto=e.get("summary", ""), sezione=fonte.get("sezione"))
            for e in feed.entries[:40]]


def da_reddit(sub):
    import feedparser
    feed = feedparser.parse(scarica(f"https://www.reddit.com/r/{sub['sub']}/top/.rss?t=day"))
    out = []
    for e in feed.entries[:25]:
        it = item(e.get("title", ""), e.get("link"), e.get("updated"), f"Reddit r/{sub['sub']}", "WEB", "en",
                  "social", "reddit")
        it["curiosita"] = bool(sub.get("curiosita"))
        out.append(it)
    return out


def da_telegram(canale):
    pagina = scarica(f"https://t.me/s/{canale['canale']}")
    out = []
    blocchi = pagina.split('class="tgme_widget_message_wrap')[1:]
    for b in blocchi[-25:]:
        post = re.search(r'data-post="([^"]+)"', b)
        testo = re.search(r'tgme_widget_message_text[^>]*>(.*?)</div>', b, re.S)
        quando = re.search(r'<time[^>]+datetime="([^"]+)"', b)
        if post and testo:
            t = pulisci_post(pulisci(testo.group(1).replace("<br/>", ". ").replace("<br>", ". ")))
            if len(t) < 25:
                continue
            aff = canale.get("affidabilita", "aggregatore")
            it = item(titolo_da_post(t), "https://t.me/" + post.group(1), quando.group(1) if quando else None,
                      canale.get("nome") or f"Telegram @{canale['canale']}", canale.get("paese", "WEB"),
                      canale.get("lingua", "?"), "giornale" if aff == "ufficiale" else "social", "telegram", riassunto=t)
            it["affidabilita"] = aff
            it["veloce"] = True
            out.append(it)
    return out


RE_CODA_POST = re.compile(r"(?i)(follow @\w+.*$|segui(ci)? su .*$|leggi l'articolo completo.*$|read:? https?://\S+.*$|"
                          r"🔗.*$|📰.*$|📱.*$|@\w+\s*$|https?://\S+)")
RE_TESTA_POST = re.compile(r"(?i)^(⚡️|🔴|🚨|‼️|❗️|\s)*(breaking( news)?|just in|ultim'ora|urgente|new|update|aggiornamento)\s*[:\-–—]\s*")


def pulisci_post(t):
    t = RE_CODA_POST.sub("", t).strip()
    t = RE_TESTA_POST.sub("", t).strip()
    return re.sub(r"\s+", " ", t)


def titolo_da_post(t):
    """Il titolo di un post Telegram è la prima frase (i canali scrivono titolo e testo attaccati)."""
    m = re.match(r"(.{25,200}?[.!?])(\s|[A-Z]|$)", t)
    return (m.group(1) if m else t[:180]).strip()


RE_SPAM = re.compile(r"(?i)(xxx|xvideos|xnxx|xhamster|porn|\+18|18\+|onlyfans|\bmms\b|leaked video|viral video link|"
                     r"video viral|viral video|full video|trending on social media|filtrad|𝕍|𝚅|™️|🍆)")


# titoli che non sono notizie: programmi tv, dirette, rubriche, oroscopi, newsletter, nomi di siti
RE_INIZIO_NON_NOTIZIA = re.compile(
    r"(?i)^\s*(assista|assistir|watch live|watch:|guarda il video|ascolta|listen|regarder|écouter|escucha|sehen sie|"
    r"podcast|newsletter|oroscopo|horoscope|horóscopo|meteo:|weather forecast|crossword|cruciverba|sudoku|"
    r"quiz:|the morning|the evening|buongiorno|good morning)\b")
RE_NON_NOTIZIA = re.compile(
    r"(?i)\b(ao vivo|en vivo|live stream|livestream|in streaming|diretta tv|tg\d* (delle|ore)|"
    r"edizione delle ore|replay|full episode|episodio completo|puntata del)\b")


def non_e_notizia(it):
    """Vero per i titoli che non raccontano un fatto (programmi, rubriche, nomi del sito)."""
    t = (it.get("titolo") or "").strip()
    parole = re.findall(r"\w+", t)
    if len(parole) < 4 and len(t) < 25 and " " in t:      # "Bom Dia ES", "Sport ES" (non i titoli giapponesi)
        return True
    if RE_INIZIO_NON_NOTIZIA.search(t):
        return True
    if len(parole) < 8 and RE_NON_NOTIZIA.search(t):     # "Jornal Nacional ao vivo", non le dirette con un fatto
        return True
    fonte = normalizza(it.get("fonte") or "").strip()
    return bool(fonte) and normalizza(t).strip() == fonte   # il titolo è solo il nome della testata


def e_spam(it, bloccati=()):
    t = it["titolo"]
    if RE_SPAM.search(t) or non_e_notizia(it):
        return True
    host = (it.get("link") or "").lower()
    if any(b in host or b in it["fonte"].lower() for b in bloccati):
        return True
    # emoji, simboli e lettere "matematiche" (𝕍𝕚𝕕𝕖𝕠) sono tipici dello spam
    simboli = sum(1 for c in t if unicodedata.category(c).startswith("S") or 0x1D400 <= ord(c) <= 0x1D7FF)
    return len(t) > 0 and simboli / len(t) > 0.08


def raccogli_dal_vivo(fonti):
    tutti, errori = [], []

    def prova(nome, funzione, *args):
        try:
            risultato = funzione(*args)
            tutti.extend(risultato)
            print(f"  ok  {nome:<40} {len(risultato):>4}")
        except Exception as e:
            errori.append(f"{nome}: {e}")
            print(f"  --  {nome:<40} errore: {str(e)[:80]}")

    attive = {"rss_diretti": True, "gdelt": True, "google_news": False, "telegram_web": False, "reddit": False,
              **{k: v for k, v in fonti.get("fonti_attive", {}).items() if not k.startswith("_")}}
    print("Fonti attive:", ", ".join(k for k, v in attive.items() if v))
    if attive["rss_diretti"]:
        print("Feed RSS ufficiali delle testate")
        for f in fonti["rss_diretti"]:
            if f.get("attivo", True) and f.get("termini") != "no":
                prova(f["nome"], da_rss, f)
    if attive["gdelt"]:
        quanti = int(fonti.get("gdelt_per_giro", 12))
        print(f"GDELT, API aperta (paesi a rotazione: {quanti} per giro)")
        gdelt = fonti["gdelt_paesi"]
        giro = int(time.time() // 600) % max(1, -(-len(gdelt) // quanti))
        for nome, codice in gdelt[giro * quanti:(giro + 1) * quanti]:
            prova("GDELT " + nome, da_gdelt, nome, codice)
            time.sleep(6)  # GDELT chiede massimo 1 richiesta ogni 5 secondi
    # le fonti qui sotto sono spente: si riaccendono in fonti.json SOLO con un permesso o un contratto
    if attive["google_news"]:
        print("Google News")
        for ed in fonti["google_news_edizioni"]:
            prova("Google News " + ed, da_google_news, ed)
            time.sleep(0.15)
        for voce in fonti.get("google_news_argomenti", []):
            for arg in voce.get("argomenti", []):
                prova(f"Google News {voce['edizione']} {arg}", da_google_news, voce["edizione"], arg)
                time.sleep(0.15)
        for r in fonti.get("google_news_ricerche", []):
            prova(f"Ricerca {r['edizione']} {r['sezione']}", da_google_news, r["edizione"], None, r["q"], r["sezione"])
            time.sleep(0.15)
    if attive["reddit"]:
        print("Reddit")
        for s in fonti["reddit"]:
            if s.get("attivo", True):
                prova("Reddit r/" + s["sub"], da_reddit, s)
    if attive["telegram_web"]:
        print("Telegram")
        for c in fonti["telegram"]:
            if c.get("canale") and c.get("attivo", True):
                prova("Telegram " + c["canale"], da_telegram, c)
    return tutti, errori


# testate citate solo per nome (articoli correlati di Google News): da dove scrivono davvero
NOMI_TESTATE = {
    "cnn indonesia": "ID", "cnn arabic": "AE", "cnn brasil": "BR", "cnn.co.jp": "JP", "cnn chile": "CL",
    "bbc": "GB", "reuters": "GB", "guardian": "GB", "sky news": "GB", "the times": "GB", "telegraph": "GB",
    "financial times": "GB", "independent": "GB", "economist": "GB", "cnn": "US", "new york times": "US",
    "washington post": "US", "wsj": "US", "ap news": "US", "associated press": "US", "bloomberg": "US", "axios": "US",
    "politico": "US", "fox ": "US", "nbc": "US", "cbs": "US", "abc news": "US", "npr": "US", "pbs": "US",
    "al jazeera": "QA", "الجزيرة": "QA", "france 24": "FR", "euronews": "FR", "rfi": "FR", "dw.com": "DE",
    "vatican news": "VA", "south china morning post": "HK", "anadolu": "TR", "iran international": "GB",
    "times of israel": "IL", "the insider": "WEB", "meduza": "LV", "радио свобода": "CZ", "настоящее время": "CZ",
}


def paese_da_nome(nome, predefinito):
    n = nome.lower()
    for chiave, cc in NOMI_TESTATE.items():
        if chiave in n:
            return cc
    return paese_da_sito(nome if "." in nome and " " not in nome else "", predefinito)


def raccogli_campione():
    """Titoli veri raccolti da Google News il 17/10/2026 in 30 paesi, già tradotti,
    per provare il motore senza internet. Formato di ogni riga:
    paese|lingua|data|testata|sito|titolo originale|titolo italiano|altre testate;separate;da;punto e virgola"""
    out = []
    for file in sorted((ENGINE / "sample").glob("oggi_*.txt")):
        for riga in file.read_text(encoding="utf-8").splitlines():
            p = riga.split("|")
            if len(p) < 8:
                continue
            paese, lingua, data, fonte, sito, titolo, titolo_it, rel = p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]
            hint = p[8].strip() if len(p) > 8 and p[8].strip() else None
            link = "https://news.google.com/search?q=" + re.sub(r"\s+", "+", titolo[:90])
            correlate = [r.strip() for r in rel.split(";") if r.strip() and r.strip() != fonte]
            it = item(titolo, link, data + ":00+00:00", fonte, paese_da_sito(sito, paese), lingua, "giornale",
                      "google_news", correlati=len(correlate), sezione=hint)
            it["titolo_it"] = titolo_it or titolo
            it["gruppo"] = it["id"]
            out.append(it)
            for f in correlate:
                c = item(titolo, link + "&fonte=" + re.sub(r"\s+", "+", f), data + ":00+00:00", f,
                         paese_da_nome(f, paese), lingua, "giornale", "google_news", gruppo=it["id"], sezione=hint)
                c["titolo_it"] = it["titolo_it"]
                c["correlato"] = True          # citata da Google News come "altre testate", senza titolo proprio
                out.append(c)
    # i canali Telegram più veloci (raccolti lo stesso giorno): solo se riattivati in fonti.json
    conf = leggi_json(ENGINE / "fonti.json", {})
    canali = {c["canale"].lower(): c for c in conf.get("telegram", [])}
    tg = ENGINE / "sample" / "telegram_oggi.txt"
    if tg.exists() and conf.get("fonti_attive", {}).get("telegram_web"):
        for riga in tg.read_text(encoding="utf-8").splitlines():
            p = riga.split("|")
            if len(p) < 7:
                continue
            nome, lingua, paese, data, post, testo, testo_it = p[:7]
            c = canali.get(nome.lower(), {"canale": nome, "affidabilita": "aggregatore"})
            aff = c.get("affidabilita", "aggregatore")
            it = item(titolo_da_post(testo), "https://t.me/" + post, data + ":00+00:00", c.get("nome") or nome,
                      c.get("paese", paese), lingua, "giornale" if aff == "ufficiale" else "social", "telegram",
                      riassunto=testo)
            it["titolo_it"] = testo_it or it["titolo"]
            it["affidabilita"] = aff
            it["veloce"] = True
            out.append(it)
    return out, []


# ---------------------------------------------------------------- raggruppamento
# parole che cambiano da lingua a lingua ma indicano la stessa cosa
SINONIMI = {
    "papa": "PAPA", "pope": "PAPA", "papst": "PAPA", "pape": "PAPA", "leone": "PAPA", "leo": "PAPA",
    "ucraina": "UCRAINA", "ukraine": "UCRAINA", "ucrania": "UCRAINA", "ukraina": "UCRAINA", "kiev": "UCRAINA",
    "kyiv": "UCRAINA", "kyjiw": "UCRAINA", "zelensky": "ZELENSKY", "zelenskyy": "ZELENSKY", "selenskyj": "ZELENSKY",
    "oregon": "OREGON", "oregón": "OREGON", "putin": "PUTIN", "starlink": "STARLINK", "starshield": "STARLINK",
    "oleshky": "OLESHKY", "oleschky": "OLESHKY", "gaza": "GAZA", "cisgiordania": "CISGIORDANIA",
    "west bank": "CISGIORDANIA", "cisjordanie": "CISGIORDANIA", "westjordanland": "CISGIORDANIA",
}


def entita(titolo):
    parole = re.findall(r"\b[A-ZÀ-Ý][\w'’\-]{3,}\b", titolo)
    out = {normalizza(p).strip() for p in parole[1:] + parole[:1] if p not in STOP_ENT}
    basso = " " + titolo.lower() + " "
    for k, v in SINONIMI.items():
        if re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", basso):
            out.discard(normalizza(k).strip())
            out.add(v)
    return out


def gruppi_nomi(titolo):
    """Per ogni nome restituisce il numero del "blocco" di parole maiuscole in cui si trova:
    "Elon Musk" vale un solo nome, non due."""
    out = {}
    for k, m in enumerate(re.finditer(r"[A-ZÀ-Ý][\w'’\-]{3,}(?:\s+[A-ZÀ-Ý][\w'’\-]{3,})*", titolo)):
        for p in m.group(0).split():
            out.setdefault(normalizza(p).strip(), k)
    basso = " " + titolo.lower() + " "
    for k, v in SINONIMI.items():
        if re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", basso):
            out.setdefault(v, out.get(normalizza(k).strip(), "s-" + v))
    return out


PAROLE_VUOTE = set("""
alla alle allo agli dalla dalle dallo dagli della delle dello degli nella nelle nello negli sulla sulle sullo sugli
con per tra fra che chi cui non piu più dopo prima oggi ieri domani anche ancora come dove quando perche perché
sono stato stata stati essere sara sarà ha hanno aveva fatto fare dice dicono detto secondo verso contro senza sotto
sopra fino mentre questa questo questi queste quella quello loro suoi sue suo sua nuovo nuova nuovi nuove ultime ultim
notizie diretta live video foto ecco cosa tutto tutti tutte molto altre altri altro dell nell sull dall all
oltre circa dice dicono parla parlano grande grandi guerra casa bianca stati uniti white house
""".split())
SOGLIA_PAROLE = 10.0     # più alto = raggruppa meno
RAGGIO_TESTO = 0.40      # somiglianza delle lettere: più basso = raggruppa meno


# verbi che i traduttori rendono in modi diversi ma vogliono dire la stessa cosa
STESSA_RADICE = {"congel": "sospen", "blocca": "sospen", "ferma": "sospen", "esenta": "sospen", "allent": "sospen",
                 "rinunc": "sospen", "deroga": "sospen", "dimess": "lascia", "lascer": "lascia", "licenz": "lascia",
                 "uccis": "morti", "morto": "morti", "morta": "morti", "vittim": "morti", "attacc": "attacc",
                 "bombar": "attacc", "raid": "attacc", "colpis": "attacc", "incend": "incend", "fiamme": "incend"}


# parole di cronaca che compaiono in mille storie diverse: da sole non dicono "stesso fatto"
PAROLE_EVENTO = {"morti", "attacc", "feriti", "incend", "sospen", "lascia", "arrest", "uccide", "esplos",
                 "scontr", "proteste", "protes", "polizi", "manife", "allarm", "emerge", "milita"}


def radici_it(titolo):
    """Parole importanti di un titolo italiano, accorciate (sanzioni/sanzione -> sanzio)."""
    parole = re.findall(r"[a-z0-9]+", normalizza(titolo))
    out = []
    for w in parole:
        if len(w) >= 4 and w not in PAROLE_VUOTE:
            r = w[:6]
            out.append(STESSA_RADICE.get(r, r))
    return out


# nomi così comuni nelle notizie che, da soli, non bastano per dire "stessa storia"
NOMI_LARGHI = {"UCRAINA", "PUTIN", "ZELENSKY", "PAPA", "GAZA", "CISGIORDANIA", "trump", "russia", "israele",
               "cina", "usa", "europa", "italia", "meloni", "iran"}
COPERTURA_MIN = 0.34     # quota di articoli del gruppo più piccolo collegati all'altro: più alto = raggruppa meno


def raggruppa(items):
    """Unisce gli articoli che parlano dello stesso fatto (anche in lingue diverse).

    Prima raccoglie i collegamenti tra coppie di articoli (testo simile, parole rare in comune,
    nomi propri in comune), poi unisce i gruppi partendo dai collegamenti più forti. Due gruppi si
    uniscono solo se abbastanza articoli dell'uno sono collegati a quelli dell'altro: così un solo
    articolo "ponte" (es. Zelensky che parla di Starlink) non incolla insieme due storie diverse
    (Starlink rallentato e fusione SpaceX-Tesla)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.neighbors import NearestNeighbors

    n = len(items)
    padre = list(range(n))
    membri = {i: [i] for i in range(n)}

    def trova(x):
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    def unisci(a, b):
        ra, rb = trova(a), trova(b)
        if ra == rb:
            return
        if len(membri[ra]) < len(membri[rb]):
            ra, rb = rb, ra
        padre[rb] = ra
        membri[ra].extend(membri.pop(rb))

    def vicini_nel_tempo(i, j, ore):
        di, dj = a_data(items[i]["data"]), a_data(items[j]["data"])
        return di is not None and dj is not None and abs((di - dj).total_seconds()) < ore * 3600

    archi = {}          # (i, j) -> forza del collegamento
    tipi = {}           # (i, j) -> da quale prova viene (per il controllo a mano)

    def collega(i, j, forza, tipo=""):
        if i == j:
            return
        k = (i, j) if i < j else (j, i)
        archi[k] = max(archi.get(k, 0.0), forza)
        tipi.setdefault(k, set()).add(tipo)

    # 1) suggerimenti di Google News (articoli correlati): si fidano, si uniscono subito
    per_gruppo = defaultdict(list)
    for i, it in enumerate(items):
        if it.get("gruppo"):
            per_gruppo[it["gruppo"]].append(i)
    for idx in per_gruppo.values():
        for j in idx[1:]:
            unisci(idx[0], j)

    unita = [trova(i) for i in range(n)]

    # 2) somiglianza del testo (n-grammi di caratteri, funziona tra titoli nella stessa lingua)
    testi = [normalizza(it["titolo"]) for it in items]
    if n > 1:
        tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1, sublinear_tf=True).fit_transform(testi)
        nn = NearestNeighbors(metric="cosine", algorithm="brute").fit(tfidf)
        dist, vic = nn.radius_neighbors(tfidf, radius=RAGGIO_TESTO)
        for i in range(n):
            for d, j in zip(dist[i], vic[i]):
                if i < j and vicini_nel_tempo(i, int(j), 36):
                    collega(i, int(j), 1.0 + (RAGGIO_TESTO - float(d)), "testo")

    # 2b) parole rare in comune nei titoli tradotti in italiano (funziona tra tutte le lingue)
    radici = [set(radici_it(it.get("titolo_it") or "")) for it in items]
    titoli_unici = {}
    for r, it in zip(radici, items):
        titoli_unici.setdefault(it.get("titolo_it") or it["titolo"], r)
    df_r = Counter(w for r in titoli_unici.values() for w in r)
    tot = max(1, len(titoli_unici))
    peso = {w: math.log(tot / c) for w, c in df_r.items()}
    indice_r = defaultdict(list)
    for i, r in enumerate(radici):
        if items[i].get("correlato"):
            continue
        for w in r:
            if df_r[w] <= max(6, tot * 0.12):
                indice_r[w].append(i)
    candidati = set()
    for lista in indice_r.values():
        if len(lista) <= 60:
            for x in range(len(lista)):
                for y in range(x + 1, len(lista)):
                    candidati.add((lista[x], lista[y]))
    # una parola maiuscola a inizio titolo ("Attacco", "Raid") non è un nome se altrove si scrive minuscola
    minuscole = Counter(w for t in titoli_unici for w in set(re.findall(r"(?<![\w'’])[a-zà-ÿ][\w'’\-]{3,}", t)))
    comune = {normalizza(w).strip() for w, c in minuscole.items() if c >= 2}
    ent = [{e for e in entita(it.get("titolo_it") or it["titolo"]) if e not in comune} for it in items]
    blocchi = [gruppi_nomi(it.get("titolo_it") or it["titolo"]) for it in items]
    radici_nomi = [{w[:6] for e in s for w in e.lower().split()} for s in ent]
    for i, j in candidati:
        comuni = radici[i] & radici[j]
        quota = len(comuni) / max(1, min(len(radici[i]), len(radici[j])))
        forza = sum(peso[w] for w in comuni)
        # oltre ai nomi (Musk, SpaceX...) servono almeno 2 parole comuni che dicono cosa è successo
        fatti = [w for w in comuni if w not in radici_nomi[i] and w not in radici_nomi[j]]
        specifici = [w for w in fatti if w not in PAROLE_EVENTO]
        if len(comuni) >= 3 and quota >= 0.4 and forza >= SOGLIA_PAROLE and len(fatti) >= 2 and specifici and \
                sum(peso[w] for w in fatti) >= SOGLIA_PAROLE / 2 and vicini_nel_tempo(i, j, 30):
            collega(i, j, 0.6 + min(0.6, forza / 40), "parole")

    # 3) nomi propri in comune (es. "Katie Zacharia" in inglese, francese, tedesco, portoghese)
    # quanti titoli DIVERSI contengono il nome (le copie di Google News contano una volta)
    ent_unici = {}
    for s_, it in zip(ent, items):
        ent_unici.setdefault(it.get("titolo_it") or it["titolo"], s_)
    df = Counter(e for s_ in ent_unici.values() for e in s_)
    limite = max(15, int(len(ent_unici) * 0.03))   # i nomi più frequenti di così non aiutano
    indice = defaultdict(list)
    for i, s in enumerate(ent):
        for e in s:
            if 1 < df[e] <= limite:
                indice[e].append(i)
    coppie = defaultdict(set)
    for e, lista in indice.items():
        for x in range(len(lista)):
            for y in range(x + 1, len(lista)):
                coppie[(lista[x], lista[y])].add(e)
    for (i, j), comuni in coppie.items():
        # "Elon Musk" conta come un solo nome (si contano i blocchi di parole maiuscole)
        nomi = min(len({blocchi[i].get(e, e) for e in comuni}), len({blocchi[j].get(e, e) for e in comuni}))
        rari = [e for e in comuni if e not in NOMI_LARGHI]
        # due nomi da soli non bastano ("Musk" e "SpaceX" compaiono in tante storie diverse):
        # serve anche una parola in comune che non sia un nome (fusione, rallentamento, portavoce...)
        altro = {w for w in radici[i] & radici[j] if w not in radici_nomi[i] | radici_nomi[j] and w not in PAROLE_EVENTO}
        if (nomi >= 3 or (nomi >= 2 and altro)) and rari and vicini_nel_tempo(i, j, 36):
            collega(i, j, 0.5 + 0.1 * len(rari), "nomi")
        # un nome completo ("Katie Zacharia") più una parola sul fatto ("portavoce") basta
        elif nomi == 1 and len(rari) >= 2 and altro and vicini_nel_tempo(i, j, 30):
            collega(i, j, 0.5, "nome completo")
        # un solo nome basta se è davvero raro (massimo 4 titoli) e le date sono vicine
        elif len(rari) == 1 and df[rari[0]] <= 4 and altro and vicini_nel_tempo(i, j, 24):
            collega(i, j, 0.4, "nome raro")

    # 4) unione prudente: dal collegamento più forte al più debole, solo tra gruppi ben collegati
    vicini = defaultdict(set)
    for i, j in archi:
        vicini[i].add(j)
        vicini[j].add(i)
    for (i, j), _ in sorted(archi.items(), key=lambda kv: -kv[1]):
        ra, rb = trova(i), trova(j)
        if ra == rb:
            continue
        a, b = membri[ra], membri[rb]
        if len(a) > len(b):
            a, b = b, a
        insieme_a, insieme_b = set(a), set(b)
        # si contano le "unità": un gruppo di Google News vale come un solo articolo
        ua, ub = {unita[x] for x in a}, {unita[x] for x in b}
        da_a = len({unita[x] for x in a if vicini[x] & insieme_b})      # unità di A collegate a B
        da_b = len({unita[x] for x in b if vicini[x] & insieme_a})      # unità di B collegate ad A
        if len(ua) > len(ub):
            ua, ub, da_a, da_b = ub, ua, da_b, da_a
        if da_a >= max(1, math.ceil(COPERTURA_MIN * len(ua))) and da_b >= max(1, math.ceil(COPERTURA_MIN / 2 * len(ub))):
            unisci(ra, rb)
    raggruppa.archi, raggruppa.tipi = archi, tipi       # per il controllo a mano

    gruppi = defaultdict(list)
    for i in range(n):
        gruppi[trova(i)].append(items[i])
    return list(gruppi.values())


# ---------------------------------------------------------------- classificazione e punteggio
_RE_PAROLE = {}


def contiene(t, k):
    """Parola chiave a inizio parola; le parole corte (inter, gol, pil...) devono essere intere."""
    k = normalizza(k).strip()
    if not k:
        return False
    r = _RE_PAROLE.get(k)
    if r is None:
        r = _RE_PAROLE[k] = re.compile(r"(?<!\w)" + re.escape(k) + (r"(?!\w)" if len(k) <= 5 else ""))
    return bool(r.search(t))


def categoria(testo):
    t = " " + normalizza(testo) + " "
    punti = {c: sum(1 for k in parole if contiene(t, k)) for c, parole in CATEGORIE.items()}
    migliore = max(punti, key=punti.get)
    return migliore if punti[migliore] > 0 else "Altro"


def e_curiosita(testo, gruppo):
    t = normalizza(testo)
    if any(normalizza(k) in t for k in PAROLE_TRAGICHE):
        return False
    return any(it.get("curiosita") for it in gruppo) or any(normalizza(k) in t for k in PAROLE_CURIOSITA)


RE_TITOLO_DEBOLE = re.compile(r"(?i)\b(live|diretta|direct|en vivo|ao vivo|opinione|opinion|meinung|le news|ultime notizie|le notizie)\b")


def bonta_titolo(x):
    """Preferisce titoli chiari: niente "in diretta", né titoli troppo corti o troppo lunghi."""
    t = x.get("titolo_it") or x["titolo"]
    return (x.get("origine") != "telegram", not RE_TITOLO_DEBOLE.search(t), x["tipo"] == "agenzia", -abs(len(t) - 85))


def scegli_titolo(gruppo):
    """Il titolo della storia è sempre in italiano: prima una testata italiana, se no la traduzione
    del titolo della testata più autorevole (agenzia, poi il titolo più chiaro)."""
    veri = [it for it in gruppo if it["tipo"] != "social" and not it.get("correlato")] or gruppo
    italiani = [it for it in veri if it["lingua"] == "it"]
    if italiani:
        migliore = max(italiani, key=bonta_titolo)
        if not RE_TITOLO_DEBOLE.search(migliore["titolo"]):
            return migliore, True
    for lingua in ("en", "fr", "es", "de", "pt"):
        cand = [it for it in veri if it["lingua"] == lingua and it.get("titolo_it")]
        if cand:
            migliore = max(cand, key=bonta_titolo)
            if not RE_TITOLO_DEBOLE.search(migliore["titolo_it"]) or lingua == "de":
                return migliore, False
    cand = [it for it in veri if it.get("titolo_it")]
    if cand:
        migliore = max(cand, key=bonta_titolo)
        return migliore, migliore["lingua"] == "it"
    return veri[0], veri[0]["lingua"] == "it"


# ---------------------------------------------------------------- dove va la notizia
def sezione_sito(cat, curiosita, paesi, gruppo):
    """Smista la storia nella sezione giusta del sito."""
    italiana = paesi == ["IT"] or (paesi and all(it["lingua"] == "it" for it in gruppo if not it.get("correlato")))
    hint = Counter(it["sezione_hint"] for it in gruppo if it.get("sezione_hint")).most_common(1)
    # se l'articolo arriva da un feed per argomento (sport, tecnologia...) vale quello, salvo guerre e cronaca nera
    if hint and cat not in ("Esteri e conflitti", "Cronaca"):
        return hint[0][0]
    if curiosita:
        return "Curiosità"
    if cat == "Sport":
        return "Sport"
    if cat == "Tecnologia e crypto":
        return "Tecnologia"
    if cat == "Economia":
        return "Economia"
    if cat == "Società":
        return "Italia" if italiana else "Società"
    if cat == "Politica":
        return "Politica"
    if italiana:
        return "Italia"
    return "Mondo"


BOT_PREDEFINITO = {
    "post_calore": 62, "post_paesi": 3,          # post Instagram: notizia grande, confermata, in più paesi
    "post_italia_calore": 50, "post_italia_fonti": 4,
    "storia_calore": 42,                          # storia Instagram
    "verifica_calore": 30,                        # sotto questa soglia le notizie non confermate si ignorano
    "max_post_al_giro": 3, "max_storie_al_giro": 6,
}


def decisione_bot(s, regole):
    """Il bot della redazione: per ogni storia propone cosa farne.
    post / storia / sito / verifica / ignora  (+ il motivo, in parole semplici)."""
    r = {**BOT_PREDEFINITO, **(regole or {})}
    n_paesi, c = len(s["paesi"]), s["calore"]
    conf = s["stato"] == "confermato"
    if s["stato"] == "voce":
        if c >= r["verifica_calore"] or s.get("crescita", 0) >= 2:
            return "verifica", f"Voce partita da {s['prima']['fonte']}, nessun giornale l'ha ancora ripresa. Da controllare."
        return "ignora", "Voce da un canale social, nessuna conferma."
    if not conf:
        if c >= r["verifica_calore"]:
            return "verifica", f"Per ora la dà solo {s['prima']['fonte']} (calore {c}). Da controllare prima di usarla."
        return "sito", f"Articolo di {s['prima']['fonte']}: va sul sito con una sola fonte, niente Instagram."
    if c >= r["post_calore"] and n_paesi >= r["post_paesi"]:
        return "post", f"Confermata da {s['n_fonti']} testate in {n_paesi} paesi, calore {c}: è una delle notizie del giorno."
    if s["sezione"] == "Italia" and c >= r["post_italia_calore"] and s["n_fonti"] >= r["post_italia_fonti"]:
        return "post", f"Notizia italiana ripresa da {s['n_fonti']} testate, calore {c}."
    if c >= r["storia_calore"] or (s["curiosita"] and s["n_fonti"] >= 2):
        return "storia", f"Confermata ({s['n_fonti']} testate), calore {c}: buona per una storia."
    return "sito", f"Confermata da {s['n_fonti']} testate: va sul sito, non serve Instagram."


def didascalia(s):
    """Bozza di didascalia per Instagram: semplice, con le fonti. La redazione la rilegge sempre."""
    # prima le testate che il pubblico italiano riconosce (italiane, agenzie, grandi nomi internazionali)
    def notorieta(f):
        n = f["fonte"]
        return (f["paese"] == "IT", any(k in n.lower() for k in NOMI_TESTATE), n.isascii())
    nomi = [f["fonte"] for f in sorted(s["fonti"], key=notorieta, reverse=True)]
    nomi = list(dict.fromkeys(nomi))[:3]
    altre = s["n_fonti"] - len(nomi)
    fonti = ", ".join(nomi) + (f" e altre {altre} testate" if altre > 0 else "")
    paesi = len(s["paesi"])
    dove = f" in {paesi} paesi" if paesi > 1 else ""
    stato = "" if s["stato"] == "confermato" else "\n\nAl momento c'è una sola fonte: la notizia è da verificare."
    tag = {"Italia": "#italia", "Politica": "#politica", "Mondo": "#esteri", "Economia": "#economia", "Società": "#società",
           "Tecnologia": "#tecnologia", "Sport": "#sport", "Curiosità": "#curiosità"}.get(s["sezione"], "#notizie")
    titolo = s["titolo"].rstrip(" .")
    if titolo[-1:] not in "?!»\"":
        titolo += "."
    quante = "una testata" if s["n_fonti"] == 1 else f"{s['n_fonti']} testate"
    return (f"{titolo}\n\nLa notizia è ripresa da {quante}{dove}.{stato}\n\n"
            f"Fonti: {fonti}.\n\n#adolos #oltreifatti {tag}")


RE_NOME_PERSONA = re.compile(r"\b[A-ZÀ-Ý][a-zà-ÿ'’]{2,}\s+[A-ZÀ-Ý][a-zà-ÿ'’]{2,}\b")
PAROLE_REATO = ["arrest", "indagat", "accusat", "denunciat", "condannat", "processo", "omicid", "uccis", "stupro",
                "abus", "violenz", "truffa", "frode", "corruzion", "arrested", "charged", "accused", "suspect",
                "convicted", "murder", "rape", "fraud", "police", "polizia", "carabinieri"]


def controllo_obbligatorio(gruppo, cat):
    """Notizie con nomi di persone legati a reati: la redazione deve controllarle per forza
    (rischio diffamazione, presunzione d'innocenza, niente nomi di minori o vittime)."""
    testo = " ".join((x.get("titolo_it") or x["titolo"]) for x in gruppo[:8])
    n = normalizza(testo)
    reato = cat == "Cronaca" or any(normalizza(k).strip() in n for k in PAROLE_REATO)
    nomi = [m for m in RE_NOME_PERSONA.findall(testo) if not any(w in STOP_ENT for w in m.split())]
    if reato and nomi:
        return "Nomi di persone in una notizia di cronaca o su un reato: controllare bene prima di pubblicare."
    return ""


# ---------------------------------------------------------------- attendibilità e diffusione
LIVELLI = [(85, "Certa"), (65, "Confermata"), (45, "Prime conferme"), (25, "Una fonte"), (0, "Voce")]


def livello(att):
    return next(nome for soglia, nome in LIVELLI if att >= soglia)


def attendibilita(fonti, n_testate, n_paesi, agenzia, solo_social, gruppo):
    """Da 0 a 100: quanto possiamo fidarci. Una voce su un canale parte bassa (rosso),
    ogni testata indipendente che la riprende la fa salire, fino al verde."""
    if solo_social:
        canali = {x["fonte"] for x in gruppo}
        di_parte = any(x.get("affidabilita") == "di parte" for x in gruppo)
        return min(24, (6 if di_parte else 12) + 4 * (len(canali) - 1))
    att = 30 + 18 * math.log2(max(1, n_testate)) + (12 if agenzia else 0) + 4 * min(max(0, n_paesi - 1), 4)
    return int(max(25, min(99, round(att))))


def cronologia(gruppo, fonti, adesso):
    """Quando è uscita, chi l'ha data per primo, quando è arrivata la prima conferma e come si sta diffondendo."""
    voci = sorted(gruppo, key=lambda x: x["data"])
    primo = voci[0]
    t0 = a_data(primo["data"])
    viste, conferma = {primo["fonte"].lower()}, None
    for x in voci[1:]:
        if x["fonte"].lower() not in viste and x["tipo"] != "social":
            conferma = x
            break
        viste.add(x["fonte"].lower())
    # curva: testate diverse accumulate nel tempo (12 punti dalla prima uscita a adesso)
    durata = max(1.0, (adesso - t0).total_seconds())
    prime_volte = {}
    for x in voci:
        prime_volte.setdefault(x["fonte"].lower(), a_data(x["data"]))
    curva = [sum(1 for d in prime_volte.values() if (d - t0).total_seconds() <= durata * k / 11) for k in range(12)]
    ora_fa = adesso - timedelta(hours=1)
    crescita = sum(1 for d in prime_volte.values() if d >= ora_fa)
    return {
        "prima": {"fonte": primo["fonte"], "data": primo["data"], "tipo": primo["tipo"],
                  "veloce": bool(primo.get("veloce")), "link": primo["link"]},
        "conferma": ({"fonte": conferma["fonte"], "data": conferma["data"],
                      "dopo_min": max(0, round((a_data(conferma["data"]) - t0).total_seconds() / 60))}
                     if conferma else None),
        "curva": curva,
        "crescita": crescita,
    }


def costruisci_storia(gruppo, adesso, affidabili, approvati, rifiutati, regole_bot=None):
    gruppo = sorted(gruppo, key=lambda x: x["data"])
    date = [a_data(x["data"]) for x in gruppo]
    principale, nativo = scegli_titolo(gruppo)
    testo_tutto = " ".join((x.get("titolo_it") or "") + " " + x["titolo"] for x in gruppo)

    fonti, viste = [], set()
    for x in sorted(gruppo, key=lambda x: (bool(x.get("correlato")), x["data"])):
        chiave = x["fonte"].lower()
        if chiave in viste:
            continue
        viste.add(chiave)
        f = {k: x[k] for k in ("fonte", "titolo", "link", "paese", "lingua", "data", "tipo", "origine")}
        f["titolo_it"] = x.get("titolo_it")
        if x.get("correlato"):
            f["correlato"] = True
        fonti.append(f)

    paesi = sorted({x["paese"] for x in gruppo if x["paese"] not in ("WEB", None)})
    lingue = sorted({x["lingua"] for x in gruppo if x["lingua"] != "?"})
    n_fonti = len(fonti)
    n_paesi = len(paesi)
    correlati = max((x.get("correlati", 0) for x in gruppo), default=0)
    recenti = sum(1 for d in date if (adesso - d).total_seconds() < 3 * 3600)
    eta_ore = max(0.0, (adesso - max(date)).total_seconds() / 3600)
    agenzia = any(any(a in f["fonte"].lower() for a in affidabili) for f in fonti)
    solo_social = all(x["tipo"] == "social" for x in gruppo)
    scalpore = sum(1 for k in PAROLE_SCALPORE if normalizza(k) in normalizza(testo_tutto))

    punteggio = (14 * math.log2(1 + n_fonti) + 12 * math.log2(1 + n_paesi) + 6 * math.log2(1 + len(lingue))
                 + 6 * math.log2(1 + recenti) + 2 * min(correlati, 5) + (6 if agenzia else 0) + 3 * min(scalpore, 3)
                 - 1.6 * eta_ore)
    calore = max(1, min(100, round(punteggio * 0.85)))

    n_testate = sum(1 for f in fonti if f["tipo"] != "social")
    confermato = (not solo_social) and (n_testate >= 2 or agenzia or correlati >= 2)
    stato = "confermato" if confermato else ("voce" if solo_social else "una_fonte")
    sid = fid(gruppo[0]["link"] or gruppo[0]["titolo"])
    if sid in rifiutati:
        return None
    # sul sito va tutto ciò che viene da una testata vera; le voci social restano nella Diretta finché qualcuno conferma
    pubblicata = (not solo_social) or sid in approvati
    att = attendibilita(fonti, n_testate, n_paesi, agenzia, solo_social, gruppo)
    tempi = cronologia(gruppo, fonti, adesso)
    cat = categoria(testo_tutto)
    curiosita = e_curiosita(testo_tutto, gruppo)

    storia = {
        "id": sid,
        "titolo": principale.get("titolo_it") or principale["titolo"],
        "titolo_originale": None if nativo else principale["titolo"],
        "lingua": "it" if nativo else principale["lingua"],
        "fonte_titolo": principale["fonte"],
        "categoria": cat,
        "curiosita": curiosita,
        "sezione": sezione_sito(cat, curiosita, paesi, gruppo),
        "calore": calore,
        "stato": stato,
        "attendibilita": att,
        "livello": livello(att),
        **tempi,
        "pubblicata": pubblicata,
        "approvata_a_mano": sid in approvati,
        "paesi": paesi,
        "lingue": lingue,
        "n_fonti": n_fonti,
        "prima_segnalazione": {"fonte": gruppo[0]["fonte"], "paese": gruppo[0]["paese"], "data": gruppo[0]["data"]},
        "aggiornata": max(date).isoformat(),
        "fonti": fonti[:30],
        "motivi": {
            "fonti": n_fonti, "paesi": n_paesi, "lingue": len(lingue), "ultime_3_ore": recenti, "agenzia": agenzia,
            "parole_forti": scalpore, "ore_dall_ultimo_aggiornamento": round(eta_ore, 1),
        },
    }
    storia["controllo"] = controllo_obbligatorio(gruppo, cat)
    storia["bot"], storia["bot_motivo"] = decisione_bot(storia, regole_bot)
    if storia["controllo"] and storia["bot"] in ("post", "storia"):
        storia["bot_motivo"] += " ATTENZIONE: " + storia["controllo"]
    storia["didascalia"] = didascalia(storia)
    return storia


# ---------------------------------------------------------------- statistiche per la pagina Dati
def statistiche(items, storie, adesso):
    paesi = Counter(x["paese"] for x in items if x["paese"] != "WEB")
    lingue = Counter(x["lingua"] for x in items)
    fonti = Counter(x["fonte"] for x in items)
    categorie = Counter(s["categoria"] for s in storie)
    ore = Counter()
    for x in items:
        d = a_data(x["data"])
        h = int((adesso - d).total_seconds() // 3600)
        if 0 <= h < 24:
            ore[h] += 1
    return {
        "articoli_analizzati": len(items),
        "storie": len(storie),
        "paesi_coperti": len(paesi),
        "fonti_diverse": len(fonti),
        "per_paese": [[c, PAESI.get(c, c), n] for c, n in paesi.most_common(25)],
        "per_lingua": lingue.most_common(12),
        "per_categoria": categorie.most_common(),
        "fonti_top": fonti.most_common(12),
        "per_ora": [[h, ore.get(h, 0)] for h in range(23, -1, -1)],
    }


# ---------------------------------------------------------------- principale
def esegui(campione=False, solo_archivio=False):
    fonti = leggi_json(ENGINE / "fonti.json", {})
    affidabili = [a.lower() for a in fonti.get("agenzie_affidabili", [])]
    stato_approv = leggi_json(APPROVATI, {"approvati": [], "rifiutati": []})
    approvati, rifiutati = set(stato_approv["approvati"]), set(stato_approv["rifiutati"])
    CACHE.mkdir(parents=True, exist_ok=True)
    testi_approvati = {}          # sintesi approvate dalla redazione (da Notion)
    da_pubblicare_ig = {}
    if campione:                  # esempio di sintesi approvata, solo per la prova senza internet
        testi_approvati = leggi_json(ENGINE / "sample" / "sintesi_prova.json", {})
        approvati |= set(testi_approvati)
    if not campione:
        import redazione
        dec = redazione.leggi_redazione()              # le scelte fatte dallo staff sulle schede Notion
        approvati |= dec["si"]
        rifiutati |= dec["no"]
        testi_approvati.update(dec["testi"])
        da_pubblicare_ig = dec["instagram"]

    if campione:
        nuovi, errori = raccogli_campione()
        adesso = max(a_data(x["data"]) for x in nuovi) + timedelta(minutes=20)
        archivio = []
    elif solo_archivio:
        # usato dopo Pubblica/Scarta: ricalcola senza riscaricare tutto
        nuovi, errori = [], leggi_json(SITO_DATI / "notizie.json", {}).get("errori_fonti", [])
        adesso = ora_utc()
        archivio = leggi_json(ARCHIVIO, [])
    else:
        import redazione
        fonti = redazione.aggiungi_fonti_da_notion(fonti)   # le testate e i canali aggiunti dallo staff su Notion
        nuovi, errori = raccogli_dal_vivo(fonti)
        adesso = ora_utc()
        archivio = leggi_json(ARCHIVIO, [])

    # unisci con l'archivio e tieni solo le ultime 48 ore, senza doppioni né spam
    bloccati = [b.lower() for b in fonti.get("domini_bloccati", [])]
    prima = len(nuovi)
    nuovi = [x for x in nuovi if not e_spam(x, bloccati)]
    if prima - len(nuovi):
        print(f"Spam scartato: {prima - len(nuovi)} titoli")
    visti, items = set(), []
    for x in nuovi + archivio:
        chiave = x["link"] or x["titolo"]
        d = a_data(x["data"])
        if chiave in visti or d is None or (adesso - d) > timedelta(hours=FINESTRA_ORE) or d > adesso + timedelta(hours=1):
            continue
        visti.add(chiave)
        items.append(x)
    # testate in modalità "conta_e_link": servono solo a contare e linkare, non vanno all'AI
    solo_conta = {f["nome"].lower() for f in fonti.get("rss_diretti", []) if f.get("uso") == "conta_e_link"}
    for x in items:
        if x["fonte"].lower() in solo_conta:
            x["uso"] = "conta_e_link"
    if not campione:
        import traduci
        traduci.traduci_items(items)          # thailandese, giapponese, arabo... tutto in italiano
        scrivi_json(ARCHIVIO, items)

    print(f"\nArticoli nella finestra: {len(items)}")
    regole = fonti.get("bot", {})
    gruppi = raggruppa(items)
    gruppo_di = {}
    storie = []
    for g in gruppi:
        s = costruisci_storia(g, adesso, affidabili, approvati, rifiutati, regole)
        if s:
            try:
                import copertura
                s["copertura"], s["punto_cieco"] = copertura.calcola(g, fonti.get("punto_cieco"))
            except Exception as e:
                print("Copertura non calcolata:", e)
                s["copertura"], s["punto_cieco"] = {}, ""
            storie.append(s)
            gruppo_di[s["id"]] = g
    storie.sort(key=lambda s: (s["calore"], s["n_fonti"]), reverse=True)
    storie = storie[:MAX_STORIE]
    # il bot non deve intasare Instagram: solo i primi N post e N storie, gli altri scalano di un gradino
    limiti = {**BOT_PREDEFINITO, **regole}
    conta = Counter()
    for s in storie:
        if s["bot"] == "post" and conta["post"] >= limiti["max_post_al_giro"]:
            s["bot"], s["bot_motivo"] = "storia", s["bot_motivo"] + " (già scelti abbastanza post: proposta come storia)"
        if s["bot"] == "storia" and conta["storia"] >= limiti["max_storie_al_giro"]:
            s["bot"], s["bot_motivo"] = "sito", s["bot_motivo"] + " (già scelte abbastanza storie: solo sito)"
        conta[s["bot"]] += 1

    # sintesi AI (bozze per la redazione) e testi approvati da Notion
    try:
        import sintesi
        conf_ai = fonti.get("ai", {})
        bozze = sintesi.prepara(storie, gruppo_di, int(conf_ai.get("sintesi_al_giro", 8)))
    except Exception as e:
        print("Errore nelle sintesi:", e)
        bozze = {}
    for s in storie:
        b = bozze.get(s["id"])
        if b and b.get("persone_accusate") and not s["controllo"]:
            s["controllo"] = "La sintesi parla di persone accusate: controllare bene prima di pubblicare."
        t = testi_approvati.get(s["id"])
        if t and t.get("sintesi") and (s["id"] in approvati):
            s["sintesi"] = {**t, "con_ai": bool(b and b.get("sintesi"))}
    for s in storie:
        s["_bozza"] = bozze.get(s["id"]) if bozze.get(s["id"], {}).get("sintesi") else None
    # indice di viralità e zona di rischio: servono solo a ordinare la coda su Notion (dati privati)
    try:
        import indice
        indici = indice.calcola(storie, {k: v for k, v in bozze.items() if v.get("sintesi")})
    except Exception as e:
        print("Errore nell'indice di viralità:", e)
        indici = {}

    # titoli scritti da Adolos: sul sito non mostriamo i titoli delle testate (vedi titoli.py)
    import titoli
    titoli_approvati = {sid: t.get("titolo") for sid, t in testi_approvati.items() if isinstance(t, dict)}
    if campione:
        titoli_approvati.update({k: v for k, v in leggi_json(ENGINE / "sample" / "titoli_prova.json", {}).items()
                                 if not k.startswith("_")})
    try:
        titoli_adolos = titoli.prepara(storie, gruppo_di, int(fonti.get("ai", {}).get("titoli_al_giro", 120)),
                                       approvati=titoli_approvati) if not campione else titoli_approvati
    except Exception as e:
        print("Errore nei titoli Adolos:", e)
        titoli_adolos = titoli_approvati
    uscita = {
        "aggiornato": adesso.isoformat(),
        "modalita": "campione" if campione else "dal_vivo",
        "paesi_nomi": PAESI,
        "storie": "da_riempire",
        "dati": statistiche(items, storie, adesso),
        "errori_fonti": errori[:50],
    }
    # le bozze non approvate NON vanno nei dati pubblici del sito
    privati = {s["id"]: s.pop("_bozza") for s in storie}
    try:
        import social
        social.genera_caroselli(storie)      # grafiche Adolos per le notizie approvate
    except Exception as e:
        print("Errore nei caroselli:", e)
    # la didascalia proposta su Notion non deve contenere il titolo della testata: usiamo quello di Adolos
    for s in storie:
        ta = titoli_adolos.get(s["id"])
        if s.get("didascalia", "").startswith(s["titolo"]):
            resto = s["didascalia"].split("\n\n", 1)[1] if "\n\n" in s["didascalia"] else ""
            s["didascalia"] = ((ta.rstrip(" .") + ".\n\n" + resto) if ta
                               else "Manca il titolo Adolos: scrivilo in 'Titolo Adolos' prima di usare la didascalia.")
    # dati pubblici: solo notizie con titolo Adolos; delle testate solo nome, paese, data e link
    uscita["storie"] = [titoli.versione_pubblica(s, titoli_adolos[s["id"]]) for s in storie if titoli_adolos.get(s["id"])]
    print(f"Sul sito: {len(uscita['storie'])} notizie con titolo Adolos, {len(storie) - len(uscita['storie'])} restano solo su Notion")
    SITO_DATI.mkdir(parents=True, exist_ok=True)
    scrivi_json(SITO_DATI / "notizie.json", uscita)
    # versione .js: così il sito funziona anche aprendo index.html con doppio clic
    (SITO_DATI / "notizie.js").write_text("window.ADOLOS = " + json.dumps(uscita, ensure_ascii=False) + ";",
                                         encoding="utf-8")
    pubbl = sum(1 for s in uscita["storie"] if s["pubblicata"])
    print(f"Storie sul sito: {len(uscita['storie'])}  (pubblicate {pubbl}, in bozza {len(uscita['storie']) - pubbl})")
    try:
        import sito
        sito.genera()
    except Exception as e:  # il sito non deve mai bloccare la raccolta
        print("Errore nella generazione del sito:", e)
    if not campione:
        try:
            import redazione
            redazione.invia(storie, privati, indici)  # schede su Notion e avviso su Telegram (se configurati)
        except Exception as e:
            print("Errore nell'invio alla redazione:", e)
    try:
        import social
        social.esegui(storie, da_pubblicare_ig, campione, indici)   # pubblicazione Instagram via API ufficiale
    except Exception as e:
        print("Errore nella pubblicazione su Instagram:", e)
    if not campione:
        try:
            indice.raccogli_risultati()      # risultati veri dei post di 2 giorni fa
            indice.calibra()                 # una volta a settimana aggiusta i pesi
        except Exception as e:
            print("Errore nella lettura dei risultati:", e)
    if indici:
        print("Coda per indice di viralità:")
        for sid, v in sorted(indici.items(), key=lambda kv: kv[1]["indice"], reverse=True)[:8]:
            s = next(x for x in storie if x["id"] == sid)
            print(f"  {v['indice']:>3} {v['zona']:<5} {s['sezione']:<10} {s['titolo'][:70]}")
    print("Il bot propone:", dict(Counter(s["bot"] for s in storie)))
    for s in storie[:12]:
        print(f"  {s['calore']:>3} {s['bot']:<8} {s['n_fonti']:>2}f {len(s['paesi']):>2}p  {s['sezione']:<10} {s['titolo'][:70]}")


def segna(azione, sid):
    stato = leggi_json(APPROVATI, {"approvati": [], "rifiutati": []})
    lista = "approvati" if azione == "approva" else "rifiutati"
    if sid not in stato[lista]:
        stato[lista].append(sid)
    scrivi_json(APPROVATI, stato)
    print(f"{sid} -> {lista}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] in ("approva", "rifiuta") and len(args) > 1:
        segna(args[0], args[1].strip())
        if ARCHIVIO.exists():
            esegui(solo_archivio=True)
    else:
        esegui(campione="--campione" in args, solo_archivio="--solo-archivio" in args)
