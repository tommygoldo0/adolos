"""
ADOLOS – costruzione del sito (v3)
==================================
Genera le pagine HTML statiche da:
  - engine/articoli.json      articoli della redazione (dai post Instagram)
  - site/data/notizie.json    notizie dal mondo raccolte dal motore
Scrive anche site/data/live.json, che le pagine aperte rileggono ogni minuto.

Uso:  python engine/sito.py
"""

import html
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RADICE = Path(__file__).resolve().parent.parent
SITO = RADICE / "site"
try:
    _CONF_SITO = json.loads((RADICE / "engine" / "fonti.json").read_text(encoding="utf-8")).get("sito", {})
except Exception:
    _CONF_SITO = {}
EMAIL = _CONF_SITO.get("email") or "redazioneadolos@gmail.com"
ROMA = ZoneInfo("Europe/Rome")
E = html.escape

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre"]
GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
SEZIONI = ["Italia", "Politica", "Mondo", "Economia", "Società", "Analisi", "Tecnologia", "Sport", "Curiosità"]
LINGUE = {"it": "italiano", "en": "inglese", "fr": "francese", "de": "tedesco", "es": "spagnolo", "pt": "portoghese",
          "th": "thailandese", "ja": "giapponese", "ko": "coreano", "zh": "cinese", "ar": "arabo", "ru": "russo",
          "uk": "ucraino", "tr": "turco", "pl": "polacco", "nl": "olandese", "he": "ebraico", "fa": "persiano",
          "hi": "hindi", "el": "greco", "sv": "svedese", "ro": "rumeno", "hu": "ungherese", "cs": "ceco",
          "vi": "vietnamita", "id": "indonesiano", "bn": "bengalese", "da": "danese", "no": "norvegese"}
CONTINENTI = {
    "Europa": "IT FR DE ES PT GB IE NL BE CH AT SE NO DK FI PL CZ SK HU RO BG GR RS HR SI EE LV LT UA RU BY MD AL BA MK ME XK IS CY MT LU VA",
    "Americhe": "US CA MX CU HT DO GT HN PA CR JM BR AR CO CL PE VE EC UY PY BO",
    "Asia e Medio Oriente": "JP KR CN TW HK IN PK BD LK NP TH VN ID MY PH SG KZ MN MM KH LA AF IR IQ IL PS TR SA AE QA KW JO LB SY YE GE AM AZ",
    "Africa": "EG MA DZ TN LY SD ET KE UG TZ NG GH SN CI CM ZA NA BW ZW ZM AO MZ RW CD CG",
    "Oceania": "AU NZ",
}
CONT_DI = {cc: c for c, codici in CONTINENTI.items() for cc in codici.split()}

LOGO = ('<svg class="alfa" viewBox="0 0 100 100" aria-hidden="true"><defs><linearGradient id="ga" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#ef3340"/><stop offset="1" stop-color="#a5121b"/></linearGradient></defs>'
        '<circle cx="50" cy="50" r="48" fill="#fff" stroke="#ececec" stroke-width="2"/>'
        '<text x="50" y="69" text-anchor="middle" font-family="Georgia, Times New Roman, serif" font-style="italic" '
        'font-weight="700" font-size="64" fill="url(#ga)">α</text></svg>')


# ---------------------------------------------------------------- utilità
def slug(t):
    t = unicodedata.normalize("NFKD", t.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:80].rstrip("-")


def roma(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ROMA)


def data_lunga(iso):
    d = roma(iso)
    return f"{d.day} {MESI[d.month - 1]} {d.year}, ore {d:%H:%M}"


def data_breve(iso):
    d = roma(iso)
    return f"{d.day} {MESI[d.month - 1]}"


def ora(iso):
    return f"{roma(iso):%H:%M}"


def mille(n):
    return f"{n:,}".replace(",", ".")


def prima_frase(t, max_len=190):
    m = re.match(r"(.+?[.!?])(\s|$)", t)
    f = m.group(1) if m else t
    return f if len(f) <= max_len else f[:max_len].rsplit(" ", 1)[0] + "…"


def sez_url(s):
    return f"sezione-{slug(s)}.html"


def storia_url(s):
    return f"storie/{s['id']}.html"


def termo(c):
    on = max(1, round(c / 10))
    i = "".join(f'<i class="{"on c" + str(min(4, -(-k * 10 // 25))) if k <= on else ""}"></i>' for k in range(1, 11))
    return f'<span class="termo" aria-label="Calore {c} su 100">{i}</span>'


# ---------------------------------------------------------------- dati
def carica():
    articoli = json.loads((RADICE / "engine" / "articoli.json").read_text(encoding="utf-8"))
    for a in articoli:
        a["slug"] = slug(a["titolo"])
        a["url"] = f"articoli/{a['slug']}.html"
        a["img"] = f"img/ig/{a['code']}.jpg"
        a["sommario"] = prima_frase(a["testo"][0])
    articoli.sort(key=lambda a: a["data"], reverse=True)
    try:
        notizie = json.loads((SITO / "data" / "notizie.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        notizie = {"storie": [], "dati": {}, "paesi_nomi": {}, "aggiornato": datetime.now(ROMA).isoformat()}
    tutte = notizie.get("storie", [])
    for s in tutte:
        conts = Counter(CONT_DI.get(p, "Altro") for p in s["paesi"]) or Counter({"Altro": 1})
        s["continenti"] = [c for c, _ in conts.most_common()]
        s.setdefault("attendibilita", 50)
        s.setdefault("livello", "Confermata")
        s.setdefault("prima", {"fonte": s["prima_segnalazione"]["fonte"], "data": s["prima_segnalazione"]["data"]})
        s.setdefault("curva", [])
        s.setdefault("crescita", 0)
        s.setdefault("conferma", None)
    storie = [s for s in tutte if s.get("pubblicata")]
    notizie["tutte"] = tutte
    return articoli, notizie, storie


def dati_live(notizie, storie):
    """Quello che le pagine aperte rileggono ogni minuto: tutte le notizie, anche le voci non confermate."""
    tutte = notizie.get("tutte", storie)
    paesi = Counter(p for s in storie for p in s["paesi"])
    # tutte le notizie delle ultime ore (anche le voci), fino a 400: le più recenti e le più calde
    recenti = sorted(tutte, key=lambda s: s["prima"]["data"], reverse=True)[:300]
    scelte = {s["id"]: s for s in storie[:100]}
    scelte.update({s["id"]: s for s in recenti})
    scelte.update({s["id"]: s for s in tutte if s.get("stato") == "voce"})
    return {
        "aggiornato": notizie.get("aggiornato"),
        "nomi": notizie.get("paesi_nomi", {}),
        "paesi": dict(paesi),
        "totale": len(tutte),
        "storie": [{"id": s["id"], "titolo": s["titolo"], "lingua": s.get("lingua"), "aggiornata": s["aggiornata"],
                    "sezione": s.get("sezione"), "calore": s["calore"], "paesi": s["paesi"], "n_fonti": s.get("n_fonti"),
                    "fonti": [f["fonte"] for f in s["fonti"][:5]], "pubblicata": bool(s.get("pubblicata")),
                    "stato": s.get("stato"), "att": s.get("attendibilita"), "livello": s.get("livello"),
                    "prima": {"fonte": s["prima"]["fonte"], "data": s["prima"]["data"], "veloce": s["prima"].get("veloce", False)},
                    "conferma": s.get("conferma"), "crescita": s.get("crescita", 0), "curva": s.get("curva", [])}
                   for s in sorted(scelte.values(), key=lambda s: s["calore"], reverse=True)],
    }


# ---------------------------------------------------------------- pezzi comuni
def pagina(titolo, descrizione, corpo, attiva="", prof="", live=None, ultime=None, og_img=None, script_globo=False):
    oggi = datetime.now(ROMA)
    data_testata = f"{GIORNI[oggi.weekday()].capitalize()} {oggi.day} {MESI[oggi.month - 1]} {oggi.year}"
    voci = [("Home", "index.html", "home"), ("Diretta", "diretta.html", "diretta"), ("Punto cieco", "punto-cieco.html", "cieco")] + [(s, sez_url(s), s) for s in SEZIONI] + [("Dati", "dati.html", "dati")]
    nav = "".join(f'<li><a href="{prof}{u}"{" class=on aria-current=page" if k == attiva else ""}{" class=nav-diretta" if k == "diretta" and k != attiva else ""}>'
                  + ('<span class="punto"></span>' if k == "diretta" else "") + f'{E(t)}</a></li>' for t, u, k in voci)
    nastro = ""
    if ultime:
        voci_n = "".join(f'<a href="{prof}{storia_url(s)}">{E(s["titolo"])}</a>' for s in ultime[:10])
        nastro = f'<div class="ultimora" aria-label="Ultim\'ora"><span class="lab">Ultim\'ora</span><div><span class="nastro">{voci_n}{voci_n}</span></div></div>'
    og = f'<meta property="og:image" content="{prof}{og_img}">' if og_img else ""
    live_js = f"<script>window.ADOLOS_LIVE = {json.dumps(live, ensure_ascii=False)};</script>" if live else ""
    globo_js = f'<script src="{prof}assets/globo.js"></script>' if script_globo else ""
    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(titolo)}</title>
<meta name="description" content="{E(descrizione)}">
<meta name="theme-color" content="#3a0b0e">
<meta property="og:title" content="{E(titolo)}">
<meta property="og:description" content="{E(descrizione)}">
<meta property="og:site_name" content="Adolos">
{og}
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='48' fill='white'/><text x='50' y='69' font-size='64' text-anchor='middle' fill='%23d3202b' font-family='Georgia' font-style='italic' font-weight='bold'>α</text></svg>">
<link rel="stylesheet" href="{prof}assets/adolos.css">
</head>
<body data-pagina="{E(attiva)}" data-base="{prof}">
<div class="util"><div class="wrap"><span>{data_testata}</span><a class="live" href="{prof}mondo.html"><span class="punto"></span><span>Il mondo, adesso:&nbsp;</span><span data-aggiornato>in diretta</span></a></div></div>
<header class="testata"><div class="wrap">
 <a class="logo" href="{prof}index.html" aria-label="Adolos, home">{LOGO}<span class="wordmark">Adolos</span></a>
 <nav class="sezioni" aria-label="Sezioni"><ul>{nav}</ul></nav>
</div></header>
{nastro}
<main>
{corpo}
</main>
<footer class="piede"><div class="wrap">
<div><a class="logo" href="{prof}index.html">{LOGO}<span class="wordmark">Adolos</span></a>
<p>Oltre i fatti. Progetto indipendente di analisi, ricerche e approfondimenti sull'attualità.</p>
<p>Le notizie dal mondo arrivano da testate di tutti i continenti. Per ognuna mostriamo chi la riporta e da quale paese, con il link all'articolo originale.</p></div>
<div><h4>Sezioni</h4>{"".join(f'<a href="{prof}{sez_url(s)}">{E(s)}</a>' for s in SEZIONI[:6])}</div>
<div><h4>Adolos</h4><a href="{prof}chi-siamo.html">Chi siamo e come lavoriamo</a><a href="{prof}fonti-diritti.html">Fonti, diritti e rimozioni</a><a href="{prof}privacy.html">Privacy e cookie</a><a href="{prof}dati.html">I dati</a><a href="https://www.instagram.com/adolos.it/" rel="noopener">Instagram</a><a href="mailto:{EMAIL}">{EMAIL}</a></div>
</div>
<div class="wrap" style="display:block;margin-top:22px;font-size:13px;opacity:.85">Titoli e link appartengono alle rispettive testate. Le sintesi sono scritte da Adolos e, quando preparate con l'aiuto dell'AI, sono sempre verificate dalla redazione. Parte dei dati: <a href="https://www.gdeltproject.org/" rel="noopener" style="display:inline;text-decoration:underline">The GDELT Project</a>.</div>
</footer>
<div class="avviso-privacy" id="avviso-privacy" hidden><span>Questo sito non usa cookie di profilazione né di statistica e non ti traccia. <a href="{prof}privacy.html">Privacy</a></span><button type="button" id="avviso-ok">Ho capito</button></div>
<script>(function(){{var a=document.getElementById("avviso-privacy");var visto=false;try{{visto=localStorage.getItem("adolos-privacy")==="1"}}catch(e){{}}if(!visto)a.hidden=false;document.getElementById("avviso-ok").onclick=function(){{a.hidden=true;try{{localStorage.setItem("adolos-privacy","1")}}catch(e){{}}}}}})();</script>
{live_js}
{globo_js}
<script src="{prof}assets/live.js" defer></script>
</body>
</html>
"""


def card(a, prof="", testo=True):
    return (f'<article class="card"><a href="{prof}{a["url"]}" tabindex="-1" aria-hidden="true"><img src="{prof}{a["img"]}" alt="" loading="lazy" width="720" height="900"></a>'
            f'<a class="sez" href="{prof}{sez_url(a["sezione"])}">{E(a["sezione"])}</a>'
            f'<a href="{prof}{a["url"]}"><h3 class="t">{E(a["titolo"])}</h3></a>'
            + (f'<p>{E(a["sommario"])}</p>' if testo else "") +
            f'<div class="meta">{data_breve(a["data"])}</div></article>')


def riga(a, prof="", sommario=False):
    return (f'<article class="riga"><a href="{prof}{a["url"]}" tabindex="-1" aria-hidden="true"><img src="{prof}{a["img"]}" alt="" loading="lazy" width="150" height="188"></a>'
            f'<div><a class="sez" href="{prof}{sez_url(a["sezione"])}">{E(a["sezione"])}</a>'
            f'<a href="{prof}{a["url"]}"><h3 class="t">{E(a["titolo"])}</h3></a>'
            + (f'<p>{E(a["sommario"])}</p>' if sommario else "") +
            f'<div class="meta">{data_breve(a["data"])}</div></div></article>')


def provenienza(s, nomi, n=2):
    fonti = [f["fonte"] for f in s["fonti"]]
    tot = max(s.get("n_fonti", len(fonti)), len(fonti))
    resto = tot - min(n, len(fonti))
    elenco = ", ".join(fonti[:n]) + (" e un'altra" if resto == 1 else f" e altre {resto}" if resto > 1 else "")
    p = len(s["paesi"])
    dove = f" in <b>{p} paesi</b>" if p > 1 else ""
    return f'<span class="prov">Ripresa da <b>{tot} {"testata" if tot == 1 else "testate"}</b>{dove}: {E(elenco)}</span>'


def voce(s, nomi, prof=""):
    return (f'<a class="voce" href="{prof}{storia_url(s)}"><span class="riga-calore"><span class="ora">{ora(s["aggiornata"])}</span>{termo(s["calore"])}'
            f'<span class="liv-pill mini" style="--a:{s.get("attendibilita", 50)}">{E(s.get("livello", ""))}</span>'
            f'<span class="chip-cat">{E(s.get("sezione", ""))}</span></span>'
            f'<h4 class="t">{E(s["titolo"])}</h4>{provenienza(s, nomi)}</a>')


def flusso(storie, nomi, prof="", n=8, sezione=None, live=True):
    if sezione:
        storie = [s for s in storie if s.get("sezione") == sezione]
    if not storie:
        return '<p class="meta">Le notizie dal mondo compariranno qui al primo aggiornamento.</p>'
    attr = f' id="flusso-live" data-quante="{n}"' + (f' data-sezione="{E(sezione)}"' if sezione else "") if live else ""
    return f'<div class="flusso"{attr}>' + "".join(voce(s, nomi, prof) for s in storie[:n]) + "</div>"


def originale(s):
    """Riga sotto il titolo: da quale lingua è tradotto, con il titolo originale."""
    if not s.get("titolo_originale"):
        return ""
    lingua = LINGUE.get(s.get("lingua"), s.get("lingua")) or "originale"
    dal = "dall'" if lingua[0] in "aeiou" else "dal "
    return (f'<p class="orig">Tradotto {dal}{E(lingua)} · titolo originale di {E(s.get("fonte_titolo", ""))}: '
            f'<span dir="auto" lang="{E(s.get("lingua", ""))}">{E(s["titolo_originale"])}</span></p>')


def globo_html(live):
    n_storie = len(live["storie"])
    n_paesi = len(live["paesi"])
    return (f'<div class="globo-box"><canvas id="globo" tabindex="0" role="img" aria-label="Globo con i paesi da cui arrivano le notizie in questo momento. Trascina per ruotarlo, clicca un paese per vederne le notizie."></canvas>'
            f'<div class="globo-tip" id="globo-tip"></div>'
            f'<div class="didascalia">In questo momento <b>{n_storie} storie</b> da <b>{n_paesi} paesi</b>. Trascina il globo, tocca un paese.</div></div>')


def per_sezione(storie, nomi, prof=""):
    out = []
    for sez in ["Italia", "Mondo", "Politica", "Economia", "Società", "Tecnologia", "Sport", "Curiosità"]:
        lista = [s for s in storie if s.get("sezione") == sez][:4]
        if not lista:
            continue
        voci = "".join(f'<li><a href="{prof}{storia_url(s)}">{E(s["titolo"])}</a><span class="meta"> · {len(s["fonti"])} testate</span></li>' for s in lista)
        out.append(f'<div class="blocco-sez"><h3><a href="{prof}{sez_url(sez)}">{E(sez)}</a></h3><ol>{voci}</ol></div>')
    return "".join(out)


# ---------------------------------------------------------------- pagine
# ---------------------------------------------------------------- diretta: attendibilità e diffusione
LIVELLI_INFO = [("Voce", 12, "Solo un canale social o un aggregatore. Nessun giornale l'ha ancora ripresa."),
                ("Una fonte", 32, "La dà una testata vera, ma per ora è l'unica."),
                ("Prime conferme", 52, "Ripresa da una seconda testata indipendente."),
                ("Confermata", 72, "Più testate, spesso in paesi diversi."),
                ("Certa", 92, "Tante testate in molti paesi, o agenzie di stampa.")]


def durata(minuti):
    if minuti < 60:
        return f"{minuti} min"
    h, m = divmod(minuti, 60)
    return f"{h} h" + (f" {m} min" if m else "")


def curva_svg(curva, w=120, h=34):
    if not curva or max(curva) == min(curva):
        return ""
    mx = max(curva)
    passo = w / max(1, len(curva) - 1)
    punti = " ".join(f"{k * passo:.1f},{h - 3 - (v / mx) * (h - 6):.1f}" for k, v in enumerate(curva))
    area = f"0,{h} {punti} {w},{h}"
    return (f'<svg class="curva" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true">'
            f'<polygon points="{area}" class="area"/><polyline points="{punti}" class="linea"/></svg>')


def stato_fonte(s):
    c = s.get("conferma")
    if c:
        if c["dopo_min"] < 5:
            return f'Ripresa subito da <b>{E(c["fonte"])}</b>'
        return f'Confermata da <b>{E(c["fonte"])}</b> dopo {durata(c["dopo_min"])}'
    if s.get("stato") == "voce":
        return "Nessun giornale l'ha ancora ripresa"
    if s.get("stato") == "una_fonte":
        return "Per ora la dà solo questa testata"
    return f"Ripresa insieme da {s.get('n_fonti', 1)} testate"


def riga_diretta(s, prof=""):
    a = s.get("attendibilita", 50)
    prima = s["prima"]
    veloce = " · canale veloce" if prima.get("veloce") else ""
    fuoco = f'<span class="sale">+{s["crescita"]} nell\'ultima ora</span>' if s.get("crescita", 0) >= 2 else ""
    return (f'<a class="rd{" voce" if s.get("stato") == "voce" else ""}" href="{prof}{storia_url(s)}" data-id="{s["id"]}" style="--a:{a}">'
            f'<div class="rd-tempo"><span class="ora">{ora(prima["data"])}</span><span class="fa" data-t="{prima["data"]}"></span></div>'
            f'<div class="rd-corpo"><div class="rd-top"><span class="liv">{E(s.get("livello", ""))}</span>'
            f'<span class="chip-cat">{E(s.get("sezione", ""))}</span>{fuoco}</div>'
            f'<h4>{E(s["titolo"])}</h4>'
            f'<p class="rd-orig">Uscita da <b>{E(prima["fonte"])}</b>{veloce} · {stato_fonte(s)}</p>'
            f'<div class="rd-barra" role="img" aria-label="Attendibilità {a} su 100"><i style="width:{a}%"></i></div></div>'
            f'<div class="rd-curva">{curva_svg(s.get("curva"))}<span>{s.get("n_fonti", 1)} testate · {len(s["paesi"])} paesi</span></div></a>')


def legenda():
    return '<ul class="legenda">' + "".join(
        f'<li style="--a:{a}"><span class="pallino"></span><span><b>{E(n)}</b> {E(t)}</span></li>' for n, a, t in LIVELLI_INFO) + "</ul>"


def diretta(notizie, storie, live):
    tutte = sorted(notizie.get("tutte", storie), key=lambda s: s["prima"]["data"], reverse=True)
    sezioni = sorted({s.get("sezione") for s in tutte if s.get("sezione")})
    opz = "".join(f'<option value="{E(x)}">{E(x)}</option>' for x in sezioni)
    voci = sum(1 for s in tutte if s.get("stato") == "voce")
    corpo = f"""
<section class="diretta-testa"><div class="wrap">
 <div>
  <span class="kicker-live"><span class="punto"></span> In diretta</span>
  <h1>Segui la notizia</h1>
  <p>Le notizie appena uscite, anche quando le dà una sola fonte. Guarda da dove arrivano e come crescono: la barra è rossa finché è solo una voce e diventa verde man mano che altre testate, in altri paesi, la confermano.</p>
 </div>
 {legenda()}
</div></section>
<div class="wrap">
 <div class="dir-controlli">
  <div class="schede" role="tablist" aria-label="Ordina">
   <button type="button" role="tab" aria-selected="true" class="on" data-ordina="nuove">Appena uscite</button>
   <button type="button" role="tab" aria-selected="false" data-ordina="crescita">In crescita</button>
   <button type="button" role="tab" aria-selected="false" data-ordina="att">Più confermate</button>
  </div>
  <div class="filtri-dir">
   <label><input type="checkbox" id="solo-voci"> Solo voci ({voci})</label>
   <select id="dir-sezione" aria-label="Sezione"><option value="">Tutte le sezioni</option>{opz}</select>
  </div>
 </div>
 <p class="dir-stato" id="dir-stato" aria-live="polite">{len(tutte)} notizie nelle ultime 48 ore. La pagina si aggiorna da sola.</p>
 <div class="dir-lista" id="diretta-lista">{"".join(riga_diretta(s) for s in tutte[:80])}</div>
</div>"""
    return pagina("Segui la notizia | Adolos", "Le notizie appena uscite e quanto sono confermate, in diretta.",
                  corpo, "diretta", live=live, ultime=storie)


def home(articoli, notizie, storie, live):
    nomi = notizie.get("paesi_nomi", {})
    ultime = articoli[:6]
    usati = {a["n"] for a in ultime}
    analisi = [a for a in articoli if a["sezione"] == "Analisi"][:3]
    curiosita = [a for a in articoli if a["sezione"] == "Curiosità"][:4]
    d = notizie.get("dati", {})
    tutte = sorted(notizie.get("tutte", storie), key=lambda s: s["prima"]["data"], reverse=True)
    ultima = tutte[0] if tutte else None

    def blocco(nome, n=4):
        lista = [a for a in articoli if a["sezione"] == nome and a["n"] not in usati][:n] or [a for a in articoli if a["sezione"] == nome][:n]
        return (f'<section><div class="sez-testa"><h2>{E(nome)}</h2><a href="{sez_url(nome)}">Tutto {E(nome.lower())}</a></div>'
                + "".join(riga(a) for a in lista) + "</section>") if lista else ""

    an = "".join(f'<article><a class="sez" href="{a["url"]}">Analisi</a><a href="{a["url"]}"><h3 class="t">{E(a["titolo"])}</h3></a>'
                 f'<p>{E(a["sommario"])}</p><div class="meta">{data_breve(a["data"])}</div></article>' for a in analisi)
    ult = (f'<p class="hero-ultima" id="hero-ultima">Ultima arrivata alle <b>{ora(ultima["prima"]["data"])}</b>: '
           f'<a href="{storia_url(ultima)}">{E(ultima["titolo"])}</a></p>') if ultima else ""
    corpo = f"""
<section class="hero-globo"><div class="wrap">
 <div class="hero-testo">
  <span class="kicker-live"><span class="punto"></span> In diretta da <b data-hero="paesi">{len(live["paesi"])}</b> paesi</span>
  <h1>Il mondo, adesso</h1>
  <p>Ogni punto è un paese da cui sta arrivando una notizia. Più è grande, più se ne parla. Trascina il globo, tocca un paese.</p>
  <div class="hero-numeri"><div><b data-hero="storie">{len(tutte)}</b><span>notizie</span></div><div><b>{mille(d.get('fonti_diverse', 0))}</b><span>testate</span></div><div><b>{len(d.get('per_lingua', []))}</b><span>lingue tradotte</span></div></div>
  {ult}
  <div class="hero-bottoni"><a class="btn3d giallo" href="diretta.html"><span class="punto"></span>Segui la diretta</a><a class="btn3d chiaro" href="mondo.html">Tutte le notizie</a></div>
 </div>
 <div class="hero-globo-box"><canvas id="globo" tabindex="0" role="img" aria-label="Globo con i paesi da cui arrivano le notizie in questo momento. Trascina per ruotarlo, clicca un paese per vederne le notizie."></canvas><div class="globo-tip" id="globo-tip"></div></div>
</div></section>

<div class="wrap">
 <div class="doppia">
  <section><div class="sez-testa"><h2>Le ultime di Adolos</h2></div><div class="griglia">{"".join(card(a) for a in ultime)}</div></section>
  <section><div class="sez-testa"><h2><span class="punto-rosso"></span>In diretta</h2><a href="diretta.html">Segui la diretta</a></div>
   <div class="dir-lista compatta" id="diretta-mini" data-quante="8">{"".join(riga_diretta(s) for s in tutte[:8])}</div></section>
 </div>
</div>

<section class="fascia"><div class="wrap">
 <div class="sez-testa"><h2>Analisi</h2><a href="{sez_url('Analisi')}">Tutte le analisi</a></div>
 <div class="analisi">{an}</div>
</div></section>

<div class="wrap">
 <section><div class="sez-testa"><h2>Dal mondo, sezione per sezione</h2><a href="mondo.html">Tutte le notizie</a></div>
 <div class="per-sezione">{per_sezione(storie, nomi)}</div></section>
 <div class="tre">{blocco("Mondo", 3)}{blocco("Politica", 3)}{blocco("Economia", 3)}</div>
 <section><div class="sez-testa"><h2>Curiosità</h2><a href="{sez_url('Curiosità')}">Tutte le curiosità</a></div>
 <div class="griglia q4">{"".join(card(a, testo=False) for a in curiosita)}</div></section>
 <section><div class="sez-testa"><h2>I numeri di oggi</h2><a href="dati.html">Tutti i dati</a></div>
 <div class="numeri">
  <div><div class="v" data-n="{d.get('articoli_analizzati', 0)}">{mille(d.get('articoli_analizzati', 0))}</div><div class="l">articoli letti nelle ultime 48 ore</div></div>
  <div><div class="v" data-n="{d.get('paesi_coperti', 0)}">{d.get('paesi_coperti', 0)}</div><div class="l">paesi da cui arrivano</div></div>
  <div><div class="v" data-n="{d.get('fonti_diverse', 0)}">{mille(d.get('fonti_diverse', 0))}</div><div class="l">testate e fonti diverse</div></div>
  <div><div class="v" data-n="{d.get('storie', 0)}">{d.get('storie', 0)}</div><div class="l">storie individuate</div></div>
 </div></section>
</div>"""
    og = ultime[0]["img"] if ultime else None
    return pagina("Adolos, oltre i fatti", "Notizie, analisi e curiosità dall'Italia e dal mondo, con le fonti sempre in vista.",
                  corpo, "home", live=live, ultime=storie, og_img=og, script_globo=True)


def articolo(a, articoli, storie, nomi):
    prof = "../"
    correlati = [x for x in articoli if x["sezione"] == a["sezione"] and x["n"] != a["n"]][:4]
    if len(correlati) < 4:
        correlati += [x for x in articoli if x["n"] != a["n"] and x not in correlati][: 4 - len(correlati)]
    paragrafi = "".join(f"<p>{E(p)}</p>" for p in a["testo"])
    fonti = "".join(f"<li>{E(f)}</li>" for f in a.get("fonti", [])) or "<li>Redazione Adolos</li>"
    paesi = "".join(f"<span>{E(nomi.get(p, p))}</span>" for p in a.get("luoghi", []))
    corpo = f"""
<header class="art-testa"><div class="wrap">
 <div>
  <a class="sez" href="{prof}{sez_url(a['sezione'])}">{E(a['sezione'])}</a>
  <h1>{E(a['titolo'])}</h1>
  <div class="firma">Di <b>Redazione Adolos</b>, {data_lunga(a['data'])}</div>
 </div>
 <img src="{prof}{a['img']}" alt="Grafica di Adolos: {E(a['titolo'])}" width="720" height="900">
</div></header>
<div class="wrap">
 <div class="art-corpo">
  <article class="testo">{paragrafi}</article>
  <aside class="scheda">
   <h2>Da dove arriva</h2>
   <div class="paesi">{paesi}</div>
   <h2>Fonti</h2>
   <ul>{fonti}</ul>
   <a class="btn3d chiaro piccolo" href="https://www.instagram.com/p/{a['code']}/" rel="noopener">Vedi il post su Instagram</a>
  </aside>
 </div>
 <section><div class="sez-testa"><h2>Leggi anche</h2></div>
 <div class="griglia q4">{"".join(card(x, prof, testo=False) for x in correlati)}</div></section>
</div>"""
    return pagina(f"{a['titolo']} | Adolos", a["sommario"], corpo, a["sezione"], prof, ultime=storie, og_img=a["img"])


def sezione(nome, articoli, storie, nomi):
    lista = [a for a in articoli if a["sezione"] == nome]
    dal_mondo = [s for s in storie if s.get("sezione") == nome]
    righe = "".join(riga(a, sommario=True) for a in lista)
    if not righe:
        righe = '<p class="meta">Gli articoli della redazione su questo tema arriveranno presto. Intanto, le notizie dal mondo:</p>'
    lato = (f'<section><div class="sez-testa" style="margin-top:0"><h2>{E(nome)}, adesso</h2><span class="meta">{len(dal_mondo)} notizie</span></div>'
            f'{flusso(dal_mondo, nomi, n=40)}</section>') if dal_mondo else \
           f'<section><div class="sez-testa" style="margin-top:0"><h2>Il mondo, adesso</h2><a href="mondo.html">Tutte</a></div>{flusso(storie, nomi, n=10)}</section>'
    corpo = f"""
<div class="wrap">
 <div class="sez-testa" style="margin-top:36px"><h2>{E(nome)}</h2><span class="meta">{len(lista)} articoli della redazione · {len(dal_mondo)} notizie dal mondo</span></div>
 <div class="doppia">
  <div class="lista-sezione">{righe}</div>
  {lato}
 </div>
</div>"""
    return pagina(f"{nome} | Adolos", f"Le notizie e le analisi di Adolos: {nome}.", corpo, nome, ultime=storie)


def mondo(notizie, storie, live):
    nomi = notizie.get("paesi_nomi", {})
    conts = Counter(s["continenti"][0] for s in storie)
    bottoni = '<button type="button" class="btn3d chiaro piccolo on" data-c="tutti" aria-pressed="true">Tutti i continenti</button>' + "".join(
        f'<button type="button" class="btn3d chiaro piccolo" data-c="{E(c)}" aria-pressed="false">{E(c)} ({n})</button>' for c, n in conts.most_common())
    righe = []
    for s in storie:
        fonti = "".join(
            f'<li><div><div class="chi">{E(f["fonte"])} <span>da {E(nomi.get(f["paese"], f["paese"]))}, {data_lunga(f["data"])}</span></div>'
            + fonte_titolo(f) + "</div></li>" for f in s["fonti"])
        traduci = originale(s)
        stato = f'<span class="liv-pill" style="--a:{s.get("attendibilita", 50)}">{E(s.get("livello", ""))}</span>' + badge_cieco(s)
        prima = s["prima_segnalazione"]
        righe.append(f"""<article class="storia" id="{s['id']}" data-c="{E(s['continenti'][0])}" data-p="{' '.join(s['paesi'])}">
 <div class="quando"><span class="ora">{ora(s['aggiornata'])}</span>{data_breve(s['aggiornata'])}</div>
 <div>
  <div class="riga-calore">{stato}{termo(s['calore'])}<span class="chip-cat">{E(s.get('sezione', s['categoria']))}</span></div>
  <h3><a href="{storia_url(s)}">{E(s['titolo'])}</a></h3>{traduci}
  <div>{provenienza(s, nomi, 4)}</div>
  <details><summary><span class="btn3d chiaro piccolo">Chi la riporta e da dove</span></summary>
   <p class="meta" style="margin:14px 0 0">La prima a darla è stata <b>{E(prima['fonte'])}</b> ({E(nomi.get(prima['paese'], prima['paese']))}), {data_lunga(prima['data'])}.</p>
   <ol>{fonti}</ol>
  </details>
 </div>
</article>""")
    d = notizie.get("dati", {})
    corpo = f"""
<section class="mondo-testa"><div class="wrap">
 <div class="testo">
  <h1>Il mondo, adesso</h1>
  <p>Le notizie più riprese in questo momento dalle testate di tutti i continenti. Per ognuna vedi chi la sta raccontando e da quale paese, con il link all'articolo.</p>
  <p style="font-size:16px">{mille(d.get('articoli_analizzati', 0))} articoli letti da {d.get('paesi_coperti', 0)} paesi. La pagina si aggiorna da sola.</p>
 </div>
 {globo_html(live)}
</div></section>
<div class="wrap">
 <div class="filtri" id="filtri" role="group" aria-label="Filtra per continente">{bottoni}</div>
 <div class="filtro-paese" id="filtro-paese" aria-live="polite"></div>
 <div id="storie">{"".join(righe) or '<p class="meta">Nessuna notizia al momento.</p>'}</div>
</div>"""
    return pagina("Il mondo, adesso | Adolos", "Le notizie più riprese dalle testate di tutto il mondo, con le fonti originali.",
                  corpo, "mondo", live=live, ultime=storie, script_globo=True)


def _dominio(url):
    m = re.match(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else "il sito della testata"


def fonte_titolo(f):
    """Link all'articolo di una testata. Il titolo originale NON si mostra (scelta legale, vedi titoli.py)."""
    if f.get("correlato"):
        return f'<span class="meta">Riporta la stessa notizia.</span>'
    if not f.get("titolo"):
        if not str(f.get("link", "")).startswith("http"):
            return '<span class="meta">Riporta la stessa notizia.</span>'
        return (f'<a class="leggi-fonte" href="{E(f["link"])}" rel="noopener nofollow" target="_blank">'
                f'Leggi l\'articolo su {E(_dominio(f["link"]))} ↗</a>')
    it = f.get("titolo_it") or f["titolo"]
    h = f'<a href="{E(f["link"])}" rel="noopener nofollow" target="_blank">{E(it)}</a>'
    if f["lingua"] not in ("it",) and it != f["titolo"]:
        h += f'<div class="orig-f" dir="auto" lang="{E(f["lingua"])}">{E(LINGUE.get(f["lingua"], f["lingua"]).capitalize())}: {E(f["titolo"])}</div>'
    return h


ORDINE_CONT = ["Europa", "Americhe", "Asia e Medio Oriente", "Africa", "Oceania"]
ETICHETTE_CIECO = {"italia": "Punto cieco italiano", "solo_italia": "Solo in Italia"}


def badge_cieco(s):
    k = s.get("punto_cieco")
    return f'<span class="badge-cieco {k}">{E(ETICHETTE_CIECO[k])}</span>' if k in ETICHETTE_CIECO else ""


def copertura_html(s):
    """Chi ne parla: Italia contro estero e testate per continente (numeri controllabili, niente etichette politiche)."""
    c = s.get("copertura") or {}
    if not c:
        return ""
    conts = c.get("continenti", {})
    tot = max(1, sum(conts.values()))
    righe = "".join(
        f'<div class="cop-riga"><span>{E(k)}</span><div class="cop-barra"><i style="width:{round(conts.get(k, 0) * 100 / tot)}%"></i></div>'
        f'<b>{conts.get(k, 0)}</b></div>' for k in ORDINE_CONT)
    it, est = c.get("italia", 0), c.get("estero", 0)
    quota = round(it * 100 / max(1, it + est))
    frase = {"italia": "Molte testate straniere la raccontano, quelle italiane che leggiamo ancora no.",
             "solo_italia": "La raccontano solo testate italiane: all'estero per ora non se ne parla."}.get(s.get("punto_cieco"), "")
    return f"""<section class="copertura">
   <h2>Chi ne parla</h2>
   {badge_cieco(s)}
   <div class="cop-it"><div class="cop-barra doppia"><i style="width:{quota}%"></i></div>
    <p class="meta"><b>{it}</b> {"testata italiana" if it == 1 else "testate italiane"} · <b>{est}</b> {"testata estera" if est == 1 else "testate estere"} da {c.get("paesi_esteri", 0)} paesi</p></div>
   {f'<p class="meta">{frase}</p>' if frase else ""}
   <div class="cop-cont">{righe}</div>
   <p class="meta piccolo">Contiamo le testate che leggiamo (feed ufficiali), non tutte quelle esistenti.</p>
  </section>"""


def punto_cieco(notizie, storie):
    blocchi = []
    for k, titolo, testo in (
            ("italia", "Il mondo ne parla, l'Italia no",
             "Notizie riprese da molte testate straniere in più paesi, che nelle testate italiane che leggiamo non compaiono ancora."),
            ("solo_italia", "Se ne parla solo in Italia",
             "Notizie raccontate da più testate italiane che all'estero, per ora, nessuno riprende.")):
        lista = [s for s in storie if s.get("punto_cieco") == k]
        voci = "".join(
            f'<li><a href="{storia_url(s)}"><span class="riga-calore">{termo(s["calore"])}<span class="chip-cat">{E(s.get("sezione", ""))}</span></span>'
            f'<h3>{E((s.get("sintesi") or {}).get("titolo") or s["titolo"])}</h3></a>'
            f'<p class="meta">{(s.get("copertura") or {}).get("estero", 0)} testate estere da {(s.get("copertura") or {}).get("paesi_esteri", 0)} paesi · '
            f'{(s.get("copertura") or {}).get("italia", 0)} italiane</p></li>' for s in lista[:30])
        blocchi.append(f'<section class="cieco-blocco"><h2>{E(titolo)}</h2><p>{E(testo)}</p>'
                       + (f'<ol class="cieco-lista">{voci}</ol>' if voci else '<p class="meta">In questo momento nessuna.</p>') + "</section>")
    corpo = f"""
<section class="mondo-testa"><div class="wrap"><div class="testo">
 <h1>Punto cieco</h1>
 <p>Cosa raccontano gli altri paesi e in Italia non arriva, e cosa raccontiamo solo noi. Lo calcoliamo contando le testate che riportano ogni notizia, paese per paese: nessuna etichetta politica, solo numeri che puoi controllare aprendo le fonti.</p>
</div></div></section>
<div class="wrap">{"".join(blocchi)}</div>"""
    return pagina("Punto cieco | Adolos", "Le notizie che il mondo racconta e l'Italia no, e quelle che si raccontano solo in Italia.",
                  corpo, "cieco", ultime=storie)


def pagina_storia(s, storie, nomi):
    prof = "../"
    a = s.get("attendibilita", 50)
    stato = f'<span class="liv-pill" style="--a:{a}">{E(s.get("livello", ""))} · {a}/100</span>'
    prima = s["prima_segnalazione"]
    p1 = s["prima"]
    c = s.get("conferma")
    passi = [f'<li><b>{ora(p1["data"])}</b> Esce per prima su <b>{E(p1["fonte"])}</b>'
             + (" (canale veloce)" if p1.get("veloce") else "") + "</li>"]
    if c:
        passi.append(f'<li><b>{ora(c["data"])}</b> Prima conferma da <b>{E(c["fonte"])}</b>'
                     + (f', dopo {durata(c["dopo_min"])}' if c["dopo_min"] >= 5 else ", quasi in contemporanea") + "</li>")
    passi.append(f'<li><b>Adesso</b> {s["n_fonti"]} {"testata" if s["n_fonti"] == 1 else "testate"} in {len(s["paesi"])} '
                 f'{"paese" if len(s["paesi"]) == 1 else "paesi"}' + (f', +{s["crescita"]} nell\'ultima ora' if s.get("crescita") else "") + "</li>")
    avviso = ""
    if s.get("stato") == "voce":
        avviso = ('<div class="avviso-voce"><b>Attenzione: è una voce.</b> Per ora la riporta solo un canale social o un aggregatore. '
                  'Nessuna testata l\'ha confermata: prendila con le pinze. Se arriva una conferma, questa pagina si aggiorna.</div>')
    elif s.get("stato") == "una_fonte":
        avviso = '<div class="avviso-voce tenue">Per ora la notizia arriva da una sola testata.</div>'
    traccia = f"""<section class="traccia" style="--a:{a}">
   {avviso}
   <h2>Come sta andando</h2>
   <div class="traccia-grid">
    <div><div class="rd-barra grande"><i style="width:{a}%"></i></div><p class="meta">Attendibilità: <b>{E(s.get("livello", ""))}</b>, {a} su 100. Sale ogni volta che una testata indipendente la riprende.</p>
    <ol class="tappe">{"".join(passi)}</ol></div>
    {f'<div class="curva-box">{curva_svg(s.get("curva"), 260, 80)}<p class="meta">Testate che la riportano, dalla prima uscita a ora</p></div>' if curva_svg(s.get("curva")) else ""}
   </div>
  </section>"""
    fonti = "".join(
        f'<li><div><div class="chi">{E(f["fonte"])} <span>da {E(nomi.get(f["paese"], f["paese"]))}, {data_lunga(f["data"])}</span></div>'
        + fonte_titolo(f) + "</div></li>" for f in s["fonti"])
    paesi = "".join(f'<a href="{prof}mondo.html?paese={p}">{E(nomi.get(p, p))}</a>' for p in s["paesi"])
    lingue = ", ".join(LINGUE.get(l, l) for l in s.get("lingue", []))
    simili = [x for x in storie if x.get("sezione") == s.get("sezione") and x["id"] != s["id"]][:6]
    t = s.get("sintesi")
    in_breve = ""
    titolo_h1 = s["titolo"]
    if t and t.get("sintesi"):
        titolo_h1 = t.get("titolo") or s["titolo"]
        punti = "".join(f"<li>{E(p)}</li>" for p in t.get("punti", []))
        etichetta = ("Sintesi preparata con l'aiuto dell'intelligenza artificiale e verificata dalla redazione"
                     if t.get("con_ai") else "Sintesi della redazione di Adolos")
        in_breve = (f'<section class="in-breve"><h2>In breve</h2><p>{E(t["sintesi"])}</p>'
                    + (f"<ul>{punti}</ul>" if punti else "")
                    + f'<span class="etichetta-ai">{etichetta}. Fonti qui sotto.</span></section>')
        if s.get("carosello"):
            in_breve += ('<div class="carosello-strip" aria-label="Il carosello Adolos su questa notizia">'
                         + "".join(f'<img src="{prof}{u}" alt="" loading="lazy" width="216" height="270">' for u in s["carosello"])
                         + "</div>")
    corpo = f"""
<header class="storia-testa"><div class="wrap">
 <a class="sez" href="{prof}{sez_url(s.get('sezione', 'Mondo'))}">{E(s.get('sezione', 'Mondo'))}</a>
 <h1>{E(titolo_h1)}</h1>
 {originale(s)}
 <div class="riga-calore">{stato}{termo(s['calore'])}<span class="quando">Aggiornata {data_lunga(s['aggiornata'])}</span></div>
</div></header>
<div class="wrap">
 <div class="art-corpo">
  <article class="storia-unica">
   {in_breve}
   {traccia}
   {copertura_html(s)}
   <p class="intro">{provenienza(s, nomi, 4)}. La prima a darla è stata <b>{E(prima['fonte'])}</b> ({E(nomi.get(prima['paese'], prima['paese']))}), {data_lunga(prima['data'])}.</p>
   <h2>Chi la riporta</h2>
   <ol class="elenco-fonti">{fonti}</ol>
  </article>
  <aside class="scheda">
   <h2>Da dove arriva</h2>
   <div class="paesi">{paesi}</div>
   <h2>In che lingue</h2>
   <p class="meta">{E(lingue) or "—"}</p>
   <h2>Perché è qui</h2>
   <ul><li>{s['n_fonti']} {"testata" if s['n_fonti'] == 1 else "testate diverse"}</li><li>{len(s['paesi'])} {"paese" if len(s['paesi']) == 1 else "paesi"}</li><li>Calore {s['calore']} su 100</li></ul>
   <a class="btn3d chiaro piccolo" href="{prof}mondo.html">Tutte le notizie dal mondo</a>
  </aside>
 </div>
 <section><div class="sez-testa"><h2>Altre notizie: {E(s.get('sezione', ''))}</h2><a href="{prof}{sez_url(s.get('sezione', 'Mondo'))}">Tutte</a></div>
 {flusso(simili, nomi, prof, n=6, live=False)}</section>
</div>"""
    descr = f"{titolo_h1}. Ripresa da {s['n_fonti']} testate in {len(s['paesi'])} paesi."
    og = s["carosello"][0] if s.get("carosello") else None
    return pagina(f"{titolo_h1} | Adolos", descr, corpo, s.get("sezione", ""), prof, ultime=storie, og_img=og)


def redazione(notizie):
    """Area staff (non collegata dal sito): cosa propone il bot, con la didascalia pronta da copiare."""
    tutte = notizie.get("storie", [])
    etichette = [("post", "Post Instagram"), ("storia", "Storia Instagram"), ("verifica", "Da verificare"), ("sito", "Solo sito")]
    blocchi = []
    for chiave, nome in etichette:
        lista = [s for s in tutte if s.get("bot") == chiave][:40 if chiave == "sito" else 20]
        if not lista:
            continue
        righe = "".join(f"""<article class="proposta" data-id="{s['id']}">
  <div class="riga-calore"><span class="chip-cat">{E(s.get('sezione', ''))}</span>{termo(s['calore'])}<span class="meta">{s['n_fonti']} testate · {len(s['paesi'])} paesi</span></div>
  <h3><a href="{storia_url(s)}">{E(s['titolo'])}</a></h3>
  <p class="motivo">{E(s.get('bot_motivo', ''))}</p>
  {('<p class="meta"><b>Controllo obbligatorio:</b> ' + E(s['controllo']) + '</p>') if s.get('controllo') else ''}
  {('<p class="meta">Sintesi approvata, carosello pronto.</p>') if s.get('carosello') else ''}
  <details><summary>Didascalia pronta</summary><textarea readonly rows="7">{E(s.get('didascalia', ''))}</textarea>
  <button type="button" class="btn3d piccolo copia">Copia</button></details>
 </article>""" for s in lista)
        blocchi.append(f'<section><div class="sez-testa"><h2>{nome} ({len([s for s in tutte if s.get("bot") == chiave])})</h2></div>{righe}</section>')
    corpo = f"""
<div class="wrap redazione">
 <div class="sez-testa" style="margin-top:36px"><h2>Redazione</h2><span class="meta">Pagina interna, non collegata dal sito</span></div>
 <p class="intro">Il bot di Adolos legge tutte le testate e i canali, raggruppa le notizie e propone cosa farne. Le stesse proposte arrivano come schede su Notion (con Stato da cambiare) e come messaggio sul gruppo Telegram della redazione.</p>
 {"".join(blocchi) or '<p class="meta">Nessuna proposta al momento.</p>'}
</div>
<script>document.addEventListener("click",function(e){{var b=e.target.closest(".copia");if(!b)return;var t=b.parentNode.querySelector("textarea");t.select();try{{navigator.clipboard.writeText(t.value)}}catch(x){{document.execCommand("copy")}}b.textContent="Copiata";setTimeout(function(){{b.textContent="Copia"}},1500)}});</script>"""
    h = pagina("Redazione | Adolos", "Area interna della redazione.", corpo, "redazione", ultime=None)
    return h.replace('<meta name="viewport"', '<meta name="robots" content="noindex, nofollow">\n<meta name="viewport"', 1)


def barre(titolo, sotto, righe):
    mx = max([v for _, v in righe] or [1]) or 1
    corpo = "".join(f'<div class="barra" title="{E(str(e))}: {v}"><span class="et">{E(str(e))}</span><span class="tr"><i style="width:{v / mx * 100:.1f}%"></i></span><span class="val">{mille(v)}</span></div>' for e, v in righe)
    tot = sum(v for _, v in righe) or 1
    tab = "".join(f'<tr><td title="{E(str(e))}">{E(str(e))}</td><td>{mille(v)}</td><td>{v / tot * 100:.0f}%</td></tr>' for e, v in righe)
    return (f'<div class="grafico"><h3>{E(titolo)}</h3><p class="sotto">{E(sotto)}</p>{corpo}<details class="tab"><summary>Vedi la tabella</summary>'
            f'<div class="tabella"><table><thead><tr><th>Voce</th><th>Numero</th><th>Quota</th></tr></thead><tbody>{tab}</tbody></table></div></details></div>')


def dati(articoli, notizie, storie):
    d = notizie.get("dati", {})
    per_cont = Counter()
    for c, _, n in d.get("per_paese", []):
        per_cont[CONT_DI.get(c, "Altro")] += n
    spesa = next((a for a in articoli if a.get("dato")), None)
    confronto = ""
    if spesa:
        confronto = f"""
 <section><div class="sez-testa"><h2>Il costo della vita, prima e oggi</h2><a href="{spesa['url']}">Leggi l'analisi</a></div>
 <div class="grafici"><div>
 <table class="confronto"><thead><tr><th>Voce</th><th style="text-align:right">10 anni fa</th><th style="text-align:right">Oggi</th><th style="text-align:right">Variazione</th></tr></thead><tbody>
  <tr><td>Pieno di gasolio, 50 litri</td><td class="n">64 €</td><td class="n">113 €</td><td class="su">+77%</td></tr>
  <tr><td>Pieno di benzina, 50 litri</td><td class="n">72 €</td><td class="n">102 €</td><td class="su">+42%</td></tr>
  <tr><td>Bolletta del gas in un anno</td><td class="n">1.064 €</td><td class="n">1.740 €</td><td class="su">+64%</td></tr>
  <tr><td>Benzina, gasolio, pane e pasta</td><td class="n">6,82 €</td><td class="n">10,12 €</td><td class="su">+48%</td></tr>
  <tr><td>Stipendi nominali</td><td class="n"></td><td class="n"></td><td class="n">+18%</td></tr>
 </tbody></table>
 <p class="nota-fonti">Fonti: {E(", ".join(spesa.get("fonti", [])))}. Media annua 2016 (dati Mise) e prezzo medio self Mimit al 7 ottobre 2026.</p>
 </div>
 {barre("Quanto è aumentato", "Variazione in dieci anni, in percentuale", [("Gasolio", 77), ("Bolletta del gas", 64), ("Spesa di base", 48), ("Benzina", 42), ("Stipendi", 18)])}
 </div></section>"""
    corpo = f"""
<div class="wrap">
 <div class="sez-testa" style="margin-top:36px"><h2>I numeri dietro le notizie</h2></div>
 <p style="font-family:var(--serif);font-size:19px;max-width:60ch;margin:0 0 26px">Da dove arrivano le notizie in questo momento, in che lingua sono scritte e di cosa parlano. Si aggiorna da solo insieme a "Il mondo, adesso".</p>
 <div class="numeri">
  <div><div class="v" data-n="{d.get('articoli_analizzati', 0)}">{mille(d.get('articoli_analizzati', 0))}</div><div class="l">articoli letti nelle ultime 48 ore</div></div>
  <div><div class="v" data-n="{d.get('paesi_coperti', 0)}">{d.get('paesi_coperti', 0)}</div><div class="l">paesi</div></div>
  <div><div class="v" data-n="{d.get('fonti_diverse', 0)}">{mille(d.get('fonti_diverse', 0))}</div><div class="l">testate e fonti</div></div>
  <div><div class="v" data-n="{d.get('storie', 0)}">{d.get('storie', 0)}</div><div class="l">storie individuate</div></div>
 </div>
 <section><div class="sez-testa"><h2>Il flusso delle notizie</h2></div>
 <div class="grafici">
  {barre("Da dove arrivano", "Articoli per paese della testata", [(n, v) for _, n, v in d.get('per_paese', [])[:12]])}
  {barre("Per continente", "Articoli per continente", per_cont.most_common())}
  {barre("Di cosa si parla", "Storie per argomento", d.get('per_categoria', []))}
  {barre("In che lingua", "Articoli per lingua originale", [(LINGUE.get(l, l), v) for l, v in d.get('per_lingua', [])])}
  {barre("Le testate più attive", "Articoli per testata", d.get('fonti_top', [])[:10])}
  {barre("Le storie più riprese", "Testate diverse che riportano la stessa storia", [(s['titolo'][:70], s['n_fonti']) for s in sorted(storie, key=lambda s: s['n_fonti'], reverse=True)[:8]])}
 </div></section>
 {confronto}
</div>"""
    return pagina("Dati | Adolos", "I numeri dietro le notizie: da dove arrivano, in che lingua, di cosa parlano.", corpo, "dati", ultime=storie)


def chi_siamo(storie):
    corpo = f"""
<div class="pagina">
 <h1>Chi siamo</h1>
 <p>Adolos è un progetto indipendente dedicato ad analisi, ricerche e approfondimenti sull'attualità. È ideato e curato da un gruppo di giovani con l'ambizione di crescere, analizzare il presente e offrire nuove chiavi di lettura sul mondo.</p>
 <p>Il nostro motto è oltre i fatti: ogni notizia arriva con il contesto e i numeri che servono per capirla.</p>
 <h2>Come lavoriamo</h2>
 <p>Il sistema di Adolos legge, più volte all'ora, i feed RSS ufficiali delle testate di tutti i continenti. Quando più giornali raccontano lo stesso fatto li raggruppiamo e mostriamo chi lo riporta e da quale paese, con il link all'articolo originale. Il titolo lo scriviamo noi: non riportiamo titoli né testi delle testate.</p>
 <p>Ogni notizia ha un livello di attendibilità: sale ogni volta che una testata indipendente la riprende. Con una sola fonte lo diciamo chiaramente.</p>
 <p>Non copiamo articoli e non ne traduciamo il testo. Le nostre sintesi partono dai fatti riportati da almeno due testate e sono scritte da zero; quando ci aiuta l'intelligenza artificiale lo indichiamo, e una persona della redazione le controlla sempre prima della pubblicazione.</p>
 <p>Tutti i dettagli su fonti, immagini e richieste di rimozione: <a href="fonti-diritti.html" style="color:var(--rosso);text-decoration:underline">Fonti, diritti e rimozioni</a>.</p>
 <h2>Contatti</h2>
 <p>Per segnalazioni e correzioni scrivi a <a href="mailto:{EMAIL}" style="color:var(--rosso);text-decoration:underline">{EMAIL}</a>.</p>
</div>"""
    return pagina("Chi siamo | Adolos", "Chi siamo e come lavoriamo.", corpo, ultime=storie)


def _responsabile():
    nome = (_CONF_SITO.get("responsabile") or "").strip()
    return E(nome) if nome else "<i>da completare (vedi LEGGIMI)</i>"


def fonti_diritti(storie):
    try:
        conf = json.loads((RADICE / "engine" / "fonti.json").read_text(encoding="utf-8"))
    except Exception:
        conf = {}
    feed = sorted((f for f in conf.get("rss_diretti", []) if f.get("attivo", True) and f.get("termini") != "no"),
                  key=lambda f: f["nome"].lower())
    elenco = "".join(f'<li>{E(f["nome"])} <span class="meta">({E(f.get("paese", ""))})'
                     + (" · solo conteggio e link" if f.get("uso") == "conta_e_link" else "") + '</span></li>' for f in feed)
    corpo = f"""
<div class="pagina">
 <h1>Fonti, diritti e rimozioni</h1>
 <p>Adolos racconta i fatti, non ripubblica il lavoro degli altri. Questa pagina spiega da dove prendiamo le notizie, cosa mostriamo e come chiederci una correzione o una rimozione.</p>

 <h2>Da dove arrivano le notizie</h2>
 <p>Leggiamo solo i <b>feed RSS ufficiali</b> che le testate pubblicano proprio per essere letti da altri siti e app, e l'API aperta di <a href="https://www.gdeltproject.org/" rel="noopener" style="text-decoration:underline">The GDELT Project</a>, che è libera anche per uso commerciale con citazione. Non scarichiamo le pagine degli articoli e non leggiamo siti o social in modo automatico senza un'API ufficiale.</p>

 <h2>Cosa mostriamo</h2>
 <ul>
  <li>Il <b>nome della testata</b>, il paese, la data e il <b>link</b> all'articolo, che resta sul sito della testata.</li>
  <li>Il <b>titolo</b> di ogni notizia lo scriviamo noi, con parole nostre. Non riportiamo i titoli delle testate né le loro traduzioni.</li>
  <li>Mai il testo degli articoli, intero o in parte, e mai le loro foto.</li>
  <li>Per alcune testate (segnate qui sotto) usiamo il feed <b>solo per contare</b> chi riporta una notizia e per mettere il link: nessun loro contenuto viene rielaborato.</li>
 </ul>

 <h2>Le nostre sintesi</h2>
 <p>Quando un fatto è riportato da almeno due testate, possiamo scriverne una sintesi breve. Partiamo solo dai fatti (chi, cosa, dove, quando, perché) e scriviamo un testo nuovo. Un controllo automatico verifica che non ci siano frasi copiate dalle fonti. Se la sintesi è preparata con l'aiuto dell'intelligenza artificiale lo scriviamo, e in ogni caso una persona della redazione la controlla prima che vada online.</p>

 <h2>Immagini</h2>
 <p>Usiamo grafiche create da Adolos e foto da archivi con licenza libera (come Wikimedia Commons), sempre con autore e licenza indicati. Non usiamo immagini create con l'intelligenza artificiale che ritraggono persone reali; se usiamo un'immagine illustrativa creata con l'AI, lo scriviamo sull'immagine.</p>

 <h2>Dove usiamo l'intelligenza artificiale</h2>
 <ul>
  <li><b>Titoli e sintesi</b>: l'AI propone un testo nuovo partendo dai fatti riportati da più testate. Una persona della redazione lo controlla prima che vada online. Sotto ogni sintesi lo indichiamo.</li>
  <li><b>Traduzioni interne</b>: l'AI ci aiuta a capire articoli in altre lingue. Le traduzioni non vengono pubblicate.</li>
  <li><b>Voce</b>: alcuni video e audio sono letti da una voce sintetica. Lo scriviamo sempre nel video e nella didascalia ("Voce generata con AI"). Non imitiamo la voce di persone reali.</li>
  <li><b>Ordine delle notizie</b>: un indice calcolato in automatico aiuta la redazione a scegliere quali notizie preparare. La scelta finale è sempre di una persona.</li>
 </ul>

 <h2>Correzioni e rimozioni</h2>
 <p>Se sei titolare di un contenuto, se una notizia ti riguarda o se trovi un errore, scrivi a <a href="mailto:{EMAIL}?subject=Richiesta%20di%20rimozione%20o%20rettifica" style="text-decoration:underline">{EMAIL}</a> con oggetto "Rimozione" o "Rettifica". Indica il link della pagina, cosa chiedi e perché, e come ricontattarti.</p>
 <p>Rispondiamo entro 48 ore lavorative. Se una testata non vuole comparire su Adolos, la togliamo dal sistema entro 48 ore dalla richiesta. Se la richiesta riguarda un contenuto di cui sei titolare, lo togliamo subito in via cautelativa mentre verifichiamo.</p>

 <h2>Chi è responsabile</h2>
 <p>Responsabile del sito: {_responsabile()}. Contatto: {E(EMAIL)}.</p>

 <h2>Le testate che seguiamo ({len(feed)} feed)</h2>
 <ul class="fonti-elenco">{elenco}</ul>
 <p class="nota">Oltre a queste, articoli da molti altri paesi arrivano tramite The GDELT Project. Titoli, marchi e link appartengono alle rispettive testate.</p>
</div>"""
    return pagina("Fonti, diritti e rimozioni | Adolos", "Da dove prendiamo le notizie, cosa mostriamo e come chiedere una rimozione.",
                  corpo, ultime=storie)


def privacy(storie):
    corpo = f"""
<div class="pagina">
 <h1>Privacy e cookie</h1>
 <p>In breve: Adolos non usa cookie di profilazione né di statistica, non ha pubblicità e non raccoglie dati personali dei lettori.</p>

 <h2>Cookie e memoria del browser</h2>
 <p>Il sito non installa cookie. Usa solo la memoria del tuo browser (localStorage) per ricordare che hai chiuso l'avviso sulla privacy: resta sul tuo dispositivo e puoi cancellarla quando vuoi dalle impostazioni del browser.</p>
 <p>I caratteri tipografici sono ospitati sul nostro sito: le pagine non fanno richieste a Google Fonts o ad altri servizi esterni.</p>

 <h2>Hosting</h2>
 <p>Il sito è ospitato da GitHub Pages (GitHub, Inc.). Come ogni servizio di hosting, GitHub registra dati tecnici delle visite, tra cui l'indirizzo IP, per motivi di sicurezza. Trovi i dettagli nell'<a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener" style="text-decoration:underline">informativa privacy di GitHub</a>.</p>

 <h2>Se ci scrivi</h2>
 <p>Se ci mandi un'email, usiamo il tuo indirizzo e quello che scrivi solo per risponderti, e non li diamo a nessuno.</p>

 <h2>I tuoi diritti</h2>
 <p>Puoi chiederci in ogni momento quali dati abbiamo su di te, correggerli o cancellarli, scrivendo a {E(EMAIL)}. Puoi anche rivolgerti al Garante per la protezione dei dati personali.</p>

 <h2>Titolare</h2>
 <p>Titolare del trattamento: {_responsabile()}. Contatto: {E(EMAIL)}.</p>
</div>"""
    return pagina("Privacy e cookie | Adolos", "Come Adolos tratta i dati: niente cookie di profilazione, niente tracciamento.",
                  corpo, ultime=storie)


# ---------------------------------------------------------------- costruzione
def genera():
    articoli, notizie, storie = carica()
    nomi = notizie.get("paesi_nomi", {})
    live = dati_live(notizie, storie)
    (SITO / "data").mkdir(parents=True, exist_ok=True)
    (SITO / "data" / "live.json").write_text(json.dumps(live, ensure_ascii=False), encoding="utf-8")
    (SITO / "articoli").mkdir(parents=True, exist_ok=True)
    for vecchio in (SITO / "articoli").glob("*.html"):
        vecchio.unlink()
    scrivi = lambda nome, testo: (SITO / nome).write_text(testo, encoding="utf-8")
    scrivi("index.html", home(articoli, notizie, storie, live))
    scrivi("mondo.html", mondo(notizie, storie, live))
    scrivi("dati.html", dati(articoli, notizie, storie))
    scrivi("chi-siamo.html", chi_siamo(storie))
    scrivi("fonti-diritti.html", fonti_diritti(storie))
    scrivi("privacy.html", privacy(storie))
    for s in SEZIONI:
        scrivi(sez_url(s), sezione(s, articoli, storie, nomi))
    for a in articoli:
        scrivi(a["url"], articolo(a, articoli, storie, nomi))
    (SITO / "storie").mkdir(parents=True, exist_ok=True)
    for vecchio in (SITO / "storie").glob("*.html"):
        vecchio.unlink()
    for s in notizie.get("tutte", storie):
        scrivi(storia_url(s), pagina_storia(s, storie, nomi))
    scrivi("diretta.html", diretta(notizie, storie, live))
    scrivi("punto-cieco.html", punto_cieco(notizie, storie))
    # l'area staff è su Notion: la vecchia pagina redazione.html non si pubblica più
    if (SITO / "redazione.html").exists():
        (SITO / "redazione.html").unlink()
    print(f"Sito generato: {len(articoli)} articoli, {len(storie)} notizie dal mondo (una pagina per ognuna), {len(SEZIONI)} sezioni")


if __name__ == "__main__":
    genera()
