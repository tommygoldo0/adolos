"""
ADOLOS – regia locale (gira sul Mac della redazione)
====================================================
Quando una persona preme "Prepara carosello", "Prepara video" o "Fammi il video" su Telegram, GitHub segna la
richiesta sulla scheda Notion (campo "Motivo del bot": "Richiesto video da ..."). Questo programma, acceso sul Mac,
guarda Notion ogni 30 secondi e per ogni richiesta nuova:

  1. se mancano i testi li scrive con l'AI (stessa regola delle sintesi: solo fatti delle fonti, niente copia,
     "secondo <testata>" se una sola) e li salva sulla scheda. Senza chiave AI aspetta i testi della prossima edizione;
  2. disegna il carosello (stile "Foto") e/o monta il reel (engine/reel.py: voce locale, gratis);
  3. manda tutto nel gruppo Telegram con i pulsanti Approva / Scarta. I clic li legge GitHub, come sempre.

Non approva e non pubblica niente: prepara e manda alla redazione. Il pulsante lo preme una persona.

Le chiavi NON stanno nei file: il programma le legge dal Portachiavi del Mac (le inserisce una persona, vedi LEGGIMI):
  adolos-telegram-token   il token del bot        adolos-telegram-chat   il numero della chat della redazione
  adolos-notion-token     il codice dell'integrazione Notion
La chiave dell'AI per i testi è la variabile ANTHROPIC_API_KEY (già nel profilo del terminale). Senza, niente testi AI.

    python engine/regia.py una          un solo controllo
    python engine/regia.py guardia      controlla ogni 30 secondi (è quello che lancia l'avvio automatico)
    python engine/regia.py installa     copia il progetto in ~/.adolos e lo fa partire da solo all'accensione del Mac
    python engine/regia.py stato        dice se le chiavi ci sono (senza mostrarle) e cosa ha fatto di recente
"""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
RADICE = ENGINE.parent
sys.path.insert(0, str(ENGINE))

CASA = Path.home() / ".adolos"
STATO = CASA / "regia.json"
VIDEO = CASA / "video"
TRACCIA_VIDEO = Path.home() / "Desktop" / "Adolos" / "video"
DB_REDAZIONE = "9c9a2cafbee14f1796df2978958984b8"
SEGRETI = {"TELEGRAM_BOT_TOKEN": "adolos-telegram-token", "TELEGRAM_CHAT_ID": "adolos-telegram-chat",
           "NOTION_TOKEN": "adolos-notion-token"}
PAUSA = 30
MAX_TENTATIVI = 2
MODELLO_TESTI = "claude-haiku-5-5"
FILTRO = {"and": [{"property": "Motivo del bot", "rich_text": {"contains": "Richiesto "}},
                  {"or": [{"property": "Stato", "status": {"equals": "In revisione"}},
                          {"property": "Stato", "status": {"equals": "Da valutare"}}]}]}


def _ora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def log(*parti):
    print(_ora(), *parti, flush=True)


# ---------------------------------------------------------------- chiavi (dal Portachiavi, mai nei file né nel registro)
def carica_segreti():
    """Mette le chiavi nelle variabili d'ambiente di QUESTO programma. Restituisce i nomi che mancano."""
    mancano = []
    for nome, voce in SEGRETI.items():
        if os.environ.get(nome, "").strip():
            continue
        r = subprocess.run(["security", "find-generic-password", "-s", voce, "-w"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            os.environ[nome] = r.stdout.strip()
        else:
            mancano.append(voce)
    os.environ.setdefault("NOTION_DB_REDAZIONE", DB_REDAZIONE)
    if os.environ.get("ANTHROPIC_API_KEY", "").strip() and not os.environ.get("AI_KEY"):
        os.environ["AI_KEY"] = os.environ["ANTHROPIC_API_KEY"].strip()
        os.environ["AI_PROVIDER"] = "anthropic"
        os.environ["AI_MODEL"] = MODELLO_TESTI
    return mancano


def _leggi_stato():
    try:
        return json.loads(STATO.read_text(encoding="utf-8"))
    except Exception:
        return {"tentativi": {}, "avvisati": [], "fatte": []}


def _scrivi_stato(st):
    st["fatte"] = st.get("fatte", [])[-200:]
    st["avvisati"] = st.get("avvisati", [])[-500:]
    CASA.mkdir(parents=True, exist_ok=True)
    STATO.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- Notion: la scheda e le sue fonti
def _fonti_scheda(page_id):
    """Le righe "Chi la riporta" della scheda: [{fonte, paese (codice), titolo, link}]."""
    import redazione
    from adolos import PAESI
    nome_a_codice = {v.lower(): k for k, v in PAESI.items()}
    righe, cursore = [], None
    while True:
        q = f"blocks/{page_id}/children?page_size=100" + (f"&start_cursor={cursore}" if cursore else "")
        r = redazione._notion("GET", q)
        righe += r.get("results", [])
        if not r.get("has_more"):
            break
        cursore = r.get("next_cursor")
    fonti, dentro = [], False
    for b in righe:
        tipo = b.get("type")
        testo = "".join(x.get("plain_text", "") for x in (b.get(tipo) or {}).get("rich_text", []))
        if tipo == "heading_3":
            dentro = testo.strip().lower().startswith("chi la riporta")
            continue
        if not dentro or tipo != "bulleted_list_item":
            continue
        link = next(((x.get("text") or {}).get("link") or {}).get("url", "") for x in (b.get(tipo) or {}).get("rich_text", [])) \
            if (b.get(tipo) or {}).get("rich_text") else ""
        m = re.match(r"\s*(.+?)\s*\(([^)]+)\)\s*(?::\s*(.*))?$", testo)
        if not m:
            continue
        titolo = (m.group(3) or "").strip()
        tradotto = re.search(r"\s\s\[(.+)\]\s*$", titolo)
        fonti.append({"fonte": m.group(1).strip(), "paese": nome_a_codice.get(m.group(2).strip().lower(), "WEB"),
                      "titolo": re.sub(r"\s\s\[.+\]\s*$", "", titolo).strip(), "titolo_it": tradotto.group(1) if tradotto else "",
                      "link": link or "", "tipo": "giornale"})
    return fonti


def _storia(pagina, fonti):
    """Mette insieme quello che serve a carosello e reel, dai campi della scheda e dalle sue fonti."""
    import redazione
    from adolos import PAESI
    lt, p = redazione._leggi_testo, pagina["properties"]
    nome_a_codice = {v.lower(): k for k, v in PAESI.items()}
    paesi = [nome_a_codice.get(x.get("name", "").lower(), x.get("name", "")) for x in (p.get("Paesi") or {}).get("multi_select", [])]
    viste, uniche = set(), []
    for f in fonti:
        if f["fonte"].lower() not in viste:
            viste.add(f["fonte"].lower())
            uniche.append(f)
    n = int((p.get("Redazioni indipendenti") or {}).get("number") or len(uniche) or 1)
    italia = sum(1 for f in uniche if f["paese"] == "IT")
    estero = len(uniche) - italia
    paesi_esteri = len({f["paese"] for f in uniche if f["paese"] not in ("IT", "WEB")})
    cieco = "italia" if (estero >= 5 and paesi_esteri >= 3 and italia == 0) else ""
    return {"id": lt(p.get("ID storia")), "titolo": lt(p.get("Titolo")), "sezione": lt(p.get("Sezione")) or "Notizie",
            "paesi": paesi or sorted({f["paese"] for f in uniche}), "n_fonti": n, "fonti": uniche, "punto_cieco": cieco}


# ---------------------------------------------------------------- testi con l'AI (solo se mancano)
def scrivi_testi(pagina, s, fonti):
    """Scrive titolo, sintesi, punti, copione e didascalia dalle fonti della scheda e li salva su Notion.
    Le testate italiane servono solo a contare: non vanno all'AI. Restituisce i testi o lancia un errore spiegato."""
    import ai
    import redazione
    import sintesi
    import social
    if not ai.attiva():
        raise RuntimeError("mancano i testi e sul Mac non c'è la chiave dell'AI: li scrive la prossima edizione")
    try:
        solo_conta = {f["nome"].lower() for f in json.loads((ENGINE / "fonti.json").read_text(encoding="utf-8"))["rss_diretti"]
                      if f.get("uso") == "conta_e_link"}
    except Exception:
        solo_conta = set()
    adesso = datetime.now(timezone.utc).isoformat()
    materiale = [dict(f, data=adesso, riassunto="", uso="conta_e_link" if (f["paese"] == "IT" or f["fonte"].lower() in solo_conta) else "")
                 for f in fonti if f.get("titolo")]
    righe, testi_fonti = sintesi._materiale(s, materiale)
    if not righe:
        raise RuntimeError("non ci sono fonti estere leggibili sulla scheda (le italiane servono solo a contare)")
    zona = redazione._leggi_testo(pagina["properties"].get("Zona"))
    if len(righe) < 2 and zona == "Rossa":
        raise RuntimeError("una sola fonte in zona rossa: non si prepara (cronaca o accuse con una fonte sola)")
    richiesta = "Fonti sullo stesso fatto:\n" + "\n".join(righe)
    if len(righe) < 2:
        richiesta += ("\n\nATTENZIONE: c'è UNA SOLA testata. Scrivi ogni fatto con \"secondo " +
                      materiale[0]["fonte"] + "\", anche nel titolo, e non aggiungere niente che non sia nel titolo.")
    bozza, avviso = None, ""
    for _ in range(2):
        b = ai.json_da(ai.chiedi(sintesi.SISTEMA, richiesta + avviso, max_token=1500))
        tutto = " ".join([b.get("titolo", ""), b.get("sintesi", ""), b.get("copione_tiktok", "")] + list(b.get("punti", [])))
        copiate = sintesi.frasi_copiate(tutto, testi_fonti)
        if not copiate:
            bozza = b
            break
        avviso = "\n\nATTENZIONE: la versione precedente ripeteva frasi delle fonti, riscrivile: " + "; ".join(copiate[:6])
    if not bozza or not bozza.get("sintesi"):
        raise RuntimeError("l'AI ha ripetuto frasi delle fonti anche al secondo tentativo: la scheda resta da scrivere a mano")
    testi = {"titolo": str(bozza.get("titolo", "")).strip()[:120], "sintesi": str(bozza.get("sintesi", "")).strip(),
             "punti": [str(x).strip() for x in bozza.get("punti", []) if str(x).strip()][:4],
             "copione": str(bozza.get("copione_tiktok", "")).strip()[:1500]}
    didas = social.didascalia(dict(s, didascalia=""), {**testi, "didascalia": ""})
    nota = (redazione._leggi_testo(pagina["properties"].get("Motivo del bot")) +
            f"\nTesti scritti dall'AI sul Mac il {_ora()} (anti-copia superato). Da controllare prima di approvare.").strip()
    redazione._notion("PATCH", f"pages/{pagina['id']}", {"properties": {
        "Titolo Adolos": {"rich_text": redazione._testo(testi["titolo"])},
        "Sintesi": {"rich_text": redazione._testo(testi["sintesi"])},
        "Punti carosello": {"rich_text": redazione._testo("\n".join(testi["punti"]))},
        "Copione TikTok": {"rich_text": redazione._testo(testi["copione"])},
        "Didascalia Instagram": {"rich_text": redazione._testo(didas)},
        "Pacchetto pronto": {"checkbox": True},
        "Motivo del bot": {"rich_text": redazione._testo(nota[-1900:])}}})
    log(f"{s['id']}: testi scritti con l'AI e salvati su Notion")
    return testi


# ---------------------------------------------------------------- lavoro su una richiesta
def _segna(pagina, riga):
    import redazione
    nota = (redazione._leggi_testo(pagina["properties"].get("Motivo del bot")) + "\n" + riga).strip()
    redazione._notion("PATCH", f"pages/{pagina['id']}", {"properties": {"Motivo del bot": {"rich_text": redazione._testo(nota[-1900:])}}})
    pagina["properties"]["Motivo del bot"] = {"type": "rich_text", "rich_text": [{"plain_text": nota[-1900:]}]}


def prepara(pagina, st):
    """Fa quello che è stato chiesto sulla scheda. Restituisce una riga per il registro."""
    import io
    import zipfile
    import immagini
    import redazione
    import reel
    import social
    import telegram
    from adolos import PAESI
    from sito import CONT_DI
    inizio = time.time()
    lt, p = redazione._leggi_testo, pagina["properties"]
    nota, sid = lt(p.get("Motivo del bot")), lt(p.get("ID storia"))
    vuole_video = "Richiesto video" in nota and "Video inviato su Telegram" not in nota and "Video non fatto" not in nota
    vuole_carosello = ("Richiesto carosello" in nota and "Pacchetto inviato su Telegram" not in nota
                       and "Carosello non fatto" not in nota)
    if not (vuole_video or vuole_carosello):
        return None
    import ai
    if not (lt(p.get("Titolo Adolos")) and lt(p.get("Sintesi"))) and not ai.attiva():
        # controllo PRIMA di scrivere nel gruppo: niente "Preparo..." se poi non si può fare
        raise RuntimeError("mancano i testi e sul Mac non c'è la chiave dell'AI: li scrive la prossima edizione")
    chat = os.environ["TELEGRAM_CHAT_ID"]
    titolo_scheda = lt(p.get("Titolo Adolos")) or lt(p.get("Titolo"))
    cosa = "il video" if vuole_video and not vuole_carosello else "il carosello" if not vuole_video else "carosello e video"
    attesa = telegram._tg("sendMessage", {"chat_id": chat, "disable_notification": True,
                                          "text": f"⏳ Preparo {cosa}: «{titolo_scheda[:90]}»"})
    risposta = {"reply_to_message_id": attesa["message_id"], "allow_sending_without_reply": True} if attesa else {}
    fonti = _fonti_scheda(pagina["id"])
    s = _storia(pagina, fonti)
    testi = {"titolo": lt(p.get("Titolo Adolos")), "sintesi": lt(p.get("Sintesi")),
             "punti": [x.strip(" -•\t") for x in lt(p.get("Punti carosello")).splitlines() if x.strip(" -•\t")][:4],
             "copione": lt(p.get("Copione TikTok"))}
    scritti_ora = False
    if not (testi["titolo"] and testi["sintesi"]):
        testi = scrivi_testi(pagina, s, fonti)
        scritti_ora = True
        pagina = redazione._notion("GET", f"pages/{pagina['id']}")
        p = pagina["properties"]
    if lt(p.get("Controllo legale")) == "Da sistemare":
        raise RuntimeError("la scheda è bloccata dal controllo legale: va sistemata su Notion")
    # pacchetto nuovo (testi appena scritti) o mai mandato: il carosello va mandato comunque, insieme al video
    manda_carosello = vuole_carosello or scritti_ora or (
        "Pacchetto inviato su Telegram" not in nota and lt(p.get("Pacchetto pronto")) != "si")
    foto = immagini.per_storia(s, testi["titolo"], [], "", testi["sintesi"] + " " + " ".join(testi["punti"]))
    t_car = {**testi, "_immagine": foto} if foto else dict(testi)
    if foto:
        s["immagine"] = {"credito": foto["credito"], "tipo": foto["tipo"]}
    slide = []
    for img in social.carosello(s, t_car, PAESI, CONT_DI)[:10]:
        b = io.BytesIO()
        img.convert("RGB").save(b, "JPEG", quality=88)
        slide.append(b.getvalue())
    if manda_carosello:
        telegram._tg("sendMediaGroup", {"chat_id": chat, "media": [{"type": "photo", "media": f"attach://s{i}"} for i in range(len(slide))],
                                        **risposta}, allegati={f"s{i}": x for i, x in enumerate(slide)})
        pacco = io.BytesIO()
        with zipfile.ZipFile(pacco, "w", zipfile.ZIP_STORED) as z:
            for i, x in enumerate(slide, 1):
                z.writestr(f"adolos-{sid}-{i:02d}.jpg", x)
        telegram._tg("sendDocument", {"chat_id": chat, "caption": "Carosello da scaricare (tutte le slide, 1080×1350)",
                                      "disable_notification": True, **risposta}, documento=(f"adolos-carosello-{sid}.zip", pacco.getvalue()))
    if vuole_video:
        VIDEO.mkdir(parents=True, exist_ok=True)
        pacchetto = {"id": sid, "titolo": testi["titolo"], "sintesi": testi["sintesi"], "punti": testi["punti"],
                     "copione": testi["copione"], "sezione": s["sezione"], "paesi": s["paesi"], "n_fonti": s["n_fonti"],
                     "fonti": [{"fonte": f["fonte"], "paese": f["paese"]} for f in s["fonti"]]}
        f_pacchetto = CASA / f"pacchetto-{sid}.json"
        f_pacchetto.write_text(json.dumps(pacchetto, ensure_ascii=False), encoding="utf-8")
        mp4 = reel.genera(f_pacchetto, VIDEO)
        try:                                    # copia sulla Scrivania, se il Mac lo permette
            TRACCIA_VIDEO.mkdir(parents=True, exist_ok=True)
            (TRACCIA_VIDEO / mp4.name).write_bytes(mp4.read_bytes())
        except Exception as e:
            log("video non copiato sulla Scrivania:", str(e)[:120])
        telegram._tg("sendVideo", {"chat_id": chat, "supports_streaming": True, "width": 1080, "height": 1920,
                                   "caption": "Reel pronto. Voce generata con AI. Si scarica da qui: la pubblicazione "
                                              "automatica dei reel non c'è ancora.", **risposta},
                     video=(mp4.name, mp4.read_bytes()))
    # il messaggio con i pulsanti (gli stessi dei pacchetti: i clic li legge GitHub)
    testo = telegram._testo_pacchetto(p, s, (foto or {}).get("credito", ""))
    if scritti_ora:
        testo += "\n⚠️ Testi scritti adesso dall'AI sul Mac: anti-copia superato, controllo legale NON fatto. Leggili bene."
    testo += f"\nPreparato sul Mac in {time.time() - inizio:.0f} secondi."
    tasti = telegram._tastiera(sid, lt(p.get("Zona")))
    if vuole_video:                    # il video c'è già: al posto di "Fammi il video" resta solo "Scarta"
        tasti["inline_keyboard"] = [r for r in tasti["inline_keyboard"]
                                    if not any(t.get("callback_data", "").startswith("reqv:") for t in r)]
        tasti["inline_keyboard"].append([{"text": "🗑 Scarta", "callback_data": f"no:{sid}"}])
    if pagina.get("url"):
        tasti["inline_keyboard"].append([{"text": "Apri la scheda su Notion", "url": pagina["url"]}])
    telegram._tg("sendMessage", {"chat_id": chat, "text": testo, "parse_mode": "HTML", "disable_web_page_preview": True,
                                 "reply_markup": tasti, **risposta})
    if manda_carosello or lt(p.get("Pacchetto pronto")) == "si":
        _segna(pagina, f"Pacchetto inviato su Telegram dal Mac il {_ora()}.")
    if vuole_video:
        _segna(pagina, f"Video inviato su Telegram dal Mac il {_ora()}.")
    fatto = ", ".join(x for x, y in (("carosello", manda_carosello), ("video", vuole_video), ("pulsanti", True)) if y)
    return f"{sid}: inviati {fatto} in {time.time() - inizio:.0f} s ({'con foto' if foto else 'senza foto'})"


def una(st=None):
    """Un controllo: legge le richieste su Notion e le prepara. Restituisce quante ne ha fatte."""
    import redazione
    import telegram
    st = st or _leggi_stato()
    try:
        pagine = redazione._tutte_le_righe(DB_REDAZIONE, FILTRO)
    except Exception as e:
        log("Notion non letto:", str(e)[:160])
        return 0
    fatte = 0
    for pagina in pagine:
        pid = pagina["id"]
        nota = redazione._leggi_testo(pagina["properties"].get("Motivo del bot"))
        # cambia quando arriva una richiesta nuova o quando qualcuno scrive i testi sulla scheda
        impronta = f"{len(nota)}-{len(redazione._leggi_testo(pagina['properties'].get('Sintesi')))}"
        t = st["tentativi"].get(pid, {})
        if t.get("impronta") == impronta and t.get("n", 0) >= MAX_TENTATIVI:
            continue
        try:
            riga = prepara(pagina, st)
            if riga:
                log(riga)
                st["fatte"].append(riga)
                fatte += 1
            st["tentativi"].pop(pid, None)
        except Exception as e:
            motivo = str(e)[:200]
            aspetta_testi = motivo.startswith("mancano i testi")
            n = 0 if aspetta_testi else (t.get("n", 0) + 1) if t.get("impronta") == impronta else 1
            st["tentativi"][pid] = {"impronta": impronta, "n": n, "errore": motivo}
            if aspetta_testi and pid in st["avvisati"]:
                continue
            log(f"{pid}: richiesta non fatta ({n}/{MAX_TENTATIVI}):", motivo)
            if n >= MAX_TENTATIVI or aspetta_testi:
                try:
                    titolo = redazione._leggi_testo(pagina["properties"].get("Titolo Adolos")) or \
                        redazione._leggi_testo(pagina["properties"].get("Titolo"))
                    telegram._tg("sendMessage", {"chat_id": os.environ["TELEGRAM_CHAT_ID"],
                                                 "text": f"⚠️ Non riesco a preparare «{titolo[:80]}»: {motivo}"})
                    if aspetta_testi:
                        st["avvisati"].append(pid)
                    else:
                        cosa = "Video" if "Richiesto video" in nota else "Carosello"
                        _segna(pagina, f"{cosa} non fatto dal Mac il {_ora()}: {motivo}")
                except Exception as e2:
                    log("avviso di errore non mandato:", str(e2)[:120])
    _scrivi_stato(st)
    return fatte


def guardia():
    log("Regia Adolos accesa: controllo le richieste ogni", PAUSA, "secondi")
    ultimo_pull = 0
    while True:
        mancano = carica_segreti()
        if mancano:
            log("Mancano nel Portachiavi:", ", ".join(mancano), "- riprovo tra 5 minuti (vedi LEGGIMI, Regia sul Mac)")
            time.sleep(300)
            continue
        if time.time() - ultimo_pull > 600 and (RADICE / ".git").exists() and str(RADICE).startswith(str(CASA)):
            ultimo_pull = time.time()
            prima = subprocess.run(["git", "-C", str(RADICE), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
            subprocess.run(["git", "-C", str(RADICE), "pull", "-q", "--ff-only"], capture_output=True, text=True)
            dopo = subprocess.run(["git", "-C", str(RADICE), "rev-parse", "HEAD"], capture_output=True, text=True).stdout
            if prima != dopo and subprocess.run(["git", "-C", str(RADICE), "diff", "--quiet", prima.strip(), dopo.strip(), "--", "engine/*.py"]).returncode:
                log("Codice aggiornato da GitHub: riparto")
                os.execv(sys.executable, [sys.executable, str(ENGINE / "regia.py"), "guardia"])
        try:
            una()
        except Exception as e:
            log("Errore nel controllo:", str(e)[:200])
        time.sleep(PAUSA)


# ---------------------------------------------------------------- avvio automatico sul Mac
PLIST = Path.home() / "Library" / "LaunchAgents" / "it.adolos.regia.plist"


def installa():
    """Copia il progetto in ~/.adolos/adolos (fuori dalla Scrivania sincronizzata) e lo fa partire all'accensione."""
    CASA.mkdir(parents=True, exist_ok=True)
    copia = CASA / "adolos"
    if not (copia / ".git").exists():
        subprocess.run(["git", "clone", "-q", "https://github.com/tommygoldo0/adolos.git", str(copia)], check=True)
    else:
        subprocess.run(["git", "-C", str(copia), "pull", "-q", "--ff-only"], check=False)
    python = Path.home() / ".venvs" / "faceless" / "bin" / "python"
    comando = f"exec {python} {copia / 'engine' / 'regia.py'} guardia"
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>it.adolos.regia</string>
  <key>ProgramArguments</key><array><string>/bin/zsh</string><string>-ic</string><string>{comando}</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>60</integer>
  <key>WorkingDirectory</key><string>{copia}</string>
  <key>StandardOutPath</key><string>{CASA / 'regia.log'}</string>
  <key>StandardErrorPath</key><string>{CASA / 'regia.log'}</string>
</dict></plist>
""", encoding="utf-8")
    dominio = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", dominio, str(PLIST)], capture_output=True)
    r = subprocess.run(["launchctl", "bootstrap", dominio, str(PLIST)], capture_output=True, text=True)
    print("Avvio automatico installato" if r.returncode == 0 else f"launchctl: {r.stderr.strip()}")
    print(f"Registro: {CASA / 'regia.log'}")


def stato():
    mancano = carica_segreti()
    print("Chiavi nel Portachiavi:", "tutte presenti" if not mancano else "mancano " + ", ".join(mancano))
    print("Chiave AI per i testi:", "presente" if os.environ.get("AI_KEY") else "assente (si aspettano i testi delle edizioni)")
    st = _leggi_stato()
    print("Ultime richieste fatte:", *(st.get("fatte", [])[-5:] or ["nessuna"]), sep="\n  ")
    for pid, t in st.get("tentativi", {}).items():
        print(f"  in sospeso {pid}: {t.get('errore')}")


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else ""
    if comando == "guardia":
        guardia()
    elif comando == "una":
        mancano = carica_segreti()
        if mancano:
            sys.exit("Mancano nel Portachiavi: " + ", ".join(mancano))
        print("Richieste preparate:", una())
    elif comando == "installa":
        installa()
    elif comando == "stato":
        stato()
    else:
        print(__doc__)
