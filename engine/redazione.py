"""
ADOLOS – collegamento con la redazione (area staff)
===================================================
Tutto qui è facoltativo: se le chiavi non ci sono, il motore funziona lo stesso.

Notion (l'area staff, privata, anche da telefono)
  NOTION_TOKEN          chiave dell'integrazione Notion (la crea Tommaso, vedi LEGGIMI)
  NOTION_DB_REDAZIONE   ID del database "Redazione Adolos": il bot ci crea una scheda per ogni
                        notizia che propone come post, storia o da verificare, con la bozza di
                        sintesi (se l'AI è attiva) da controllare.
  NOTION_DB_FONTI       ID del database "Fonti Adolos": testate (feed RSS) in più da seguire.

Come lavora la redazione sulla scheda:
  - corregge "Titolo Adolos", "Sintesi" e "Punti carosello" (o li scrive da zero se l'AI è spenta);
  - mette Stato = Approvata: la sintesi va sul sito e il sistema prepara il carosello;
  - spunta "Pubblica su Instagram": al giro dopo il carosello parte via API ufficiale;
  - Stato = Scartata: la notizia sparisce dal sito.

Telegram (avviso immediato sul telefono, con il vostro bot: API ufficiale)
  TELEGRAM_BOT_TOKEN    il token del vostro bot (lo dà @BotFather, gratis)
  TELEGRAM_CHAT_ID      la chat o il gruppo della redazione dove il bot scrive

  SITO_URL              indirizzo del sito, per mettere il link nei messaggi
"""

import json
import os
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
INVIATI = ENGINE / "cache" / "inviati.json"
NOTION_VER = "2022-06-28"
MAX_SCHEDE_AL_GIRO = 12

PAESI_NOMI = None  # riempito da adolos.PAESI al primo uso
INSTAGRAM = {"post": "Post", "storia": "Storia", "verifica": "No", "sito": "No", "ignora": "No"}


def _env(nome):
    v = os.environ.get(nome, "").strip()
    return v or None


def _leggi_inviati():
    try:
        st = json.loads(INVIATI.read_text(encoding="utf-8"))
    except Exception:
        st = {}
    st.setdefault("notion", {})
    st.setdefault("telegram", [])
    st.setdefault("bozze", [])
    st.setdefault("caroselli", [])
    st.setdefault("indice", {})
    return st


def _scrivi_inviati(st):
    st["notion"] = dict(list(st["notion"].items())[-3000:])
    st["indice"] = dict(list(st.get("indice", {}).items())[-3000:])
    for k in ("telegram", "bozze", "caroselli"):
        st[k] = st[k][-3000:]
    INVIATI.parent.mkdir(parents=True, exist_ok=True)
    INVIATI.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- Notion
def notion_attivo():
    return bool(_env("NOTION_DB_REDAZIONE") and _env("NOTION_TOKEN"))


def _notion(metodo, percorso, corpo=None):
    import requests
    r = requests.request(metodo, "https://api.notion.com/v1/" + percorso, json=corpo, timeout=20, headers={
        "Authorization": "Bearer " + _env("NOTION_TOKEN"), "Notion-Version": NOTION_VER,
        "Content-Type": "application/json"})
    if r.status_code >= 300:
        raise RuntimeError(f"Notion {r.status_code}: {r.text[:200]}")
    return r.json()


def _testo(t):
    return [{"type": "text", "text": {"content": (t or "")[:1900]}}]


def _leggi_testo(prop):
    if not prop:
        return ""
    for k in ("title", "rich_text"):
        if k in prop:
            return "".join(x.get("plain_text", "") for x in prop[k]).strip()
    if prop.get("type") == "url":
        return (prop.get("url") or "").strip()
    if prop.get("type") in ("select", "status"):
        return ((prop.get(prop["type"]) or {}).get("name") or "").strip()
    if prop.get("type") == "checkbox":
        return "si" if prop.get("checkbox") else ""
    return ""


def _tutte_le_righe(db):
    righe, cursore = [], None
    while True:
        corpo = {"page_size": 100}
        if cursore:
            corpo["start_cursor"] = cursore
        r = _notion("POST", f"databases/{db}/query", corpo)
        righe += r["results"]
        if not r.get("has_more"):
            return righe
        cursore = r["next_cursor"]


def aggiungi_fonti_da_notion(fonti):
    """Legge il database "Fonti Adolos" e aggiunge i feed RSS ufficiali a quelli di fonti.json.
    Le righe di tipo Telegram o Google News si leggono solo se riattivate in fonti.json (serve un permesso)."""
    db = _env("NOTION_DB_FONTI")
    if not (db and _env("NOTION_TOKEN")):
        return fonti
    try:
        righe = _tutte_le_righe(db)
    except Exception as e:
        print("Fonti da Notion non lette:", e)
        return fonti
    attive = fonti.get("fonti_attive", {})
    nuove = {"telegram": 0, "rss": 0, "google": 0, "saltate": 0}
    gia_tg = {c["canale"].lower() for c in fonti.get("telegram", [])}
    gia_rss = {f["url"] for f in fonti.get("rss_diretti", [])}
    for r in righe:
        p = r["properties"]
        nome = _leggi_testo(p.get("Nome"))
        tipo = _leggi_testo(p.get("Tipo")).lower()
        indirizzo = _leggi_testo(p.get("Indirizzo"))
        paese = (_leggi_testo(p.get("Paese")) or "WEB").upper()[:3]
        attiva = _leggi_testo(p.get("Attiva")) == "si"
        termini = "ok" if _leggi_testo(p.get("Termini verificati")) == "si" else "da_verificare"
        if not (indirizzo and attiva):
            continue
        if tipo.startswith("telegram"):
            if not attive.get("telegram_web"):
                nuove["saltate"] += 1
                continue
            canale = indirizzo.rstrip("/").split("/")[-1].lstrip("@")
            if canale.lower() not in gia_tg:
                fonti.setdefault("telegram", []).append({
                    "canale": canale, "nome": nome or canale, "paese": paese, "attivo": True,
                    "affidabilita": (_leggi_testo(p.get("Affidabilità")) or "aggregatore").lower()})
                gia_tg.add(canale.lower())
                nuove["telegram"] += 1
        elif tipo.startswith("google"):
            if not attive.get("google_news"):
                nuove["saltate"] += 1
                continue
            if ":" in indirizzo and indirizzo not in fonti["google_news_edizioni"]:
                fonti["google_news_edizioni"].append(indirizzo)
                nuove["google"] += 1
        elif indirizzo.startswith("http") and indirizzo not in gia_rss:
            fonti.setdefault("rss_diretti", []).append({
                "nome": nome or indirizzo, "paese": paese, "url": indirizzo, "attivo": True, "termini": termini,
                "tipo": "agenzia" if "agenzia" in tipo else "giornale"})
            gia_rss.add(indirizzo)
            nuove["rss"] += 1
    print(f"Fonti aggiunte da Notion: {nuove}")
    return fonti


def leggi_redazione():
    """Legge le schede: Stato, testi corretti dalla redazione e richieste di pubblicazione su Instagram."""
    out = {"si": set(), "no": set(), "testi": {}, "instagram": {}}
    if not notion_attivo():
        return out
    try:
        for r in _tutte_le_righe(_env("NOTION_DB_REDAZIONE")):
            p = r["properties"]
            sid = _leggi_testo(p.get("ID storia"))
            stato = _leggi_testo(p.get("Stato"))
            if not sid:
                continue
            if stato in ("Approvata", "Pubblicata"):
                out["si"].add(sid)
                sint = _leggi_testo(p.get("Sintesi"))
                if sint:
                    punti = [x.strip(" -•\t") for x in _leggi_testo(p.get("Punti carosello")).splitlines() if x.strip(" -•\t")]
                    out["testi"][sid] = {"titolo": _leggi_testo(p.get("Titolo Adolos")), "sintesi": sint,
                                         "punti": punti[:4], "didascalia": _leggi_testo(p.get("Didascalia Instagram"))}
                if (stato == "Approvata" and _leggi_testo(p.get("Pubblica su Instagram")) == "si"
                        and not _leggi_testo(p.get("Link Instagram"))
                        and _leggi_testo(p.get("Controllo legale")) != "Da sistemare"):   # il controllo legale blocca
                    out["instagram"][sid] = r["id"]
            elif stato == "Scartata":
                out["no"].add(sid)
    except Exception as e:
        print("Decisioni da Notion non lette:", e)
    return out


def decisioni_da_notion():
    d = leggi_redazione()
    return d["si"], d["no"]


def aggiorna_scheda(page_id, proprieta):
    """Cambia alcune proprietà di una scheda (usato per carosello e link Instagram)."""
    if not notion_attivo():
        return
    props = {}
    for k, v in proprieta.items():
        if k in ("Carosello", "Link Instagram"):
            props[k] = {"url": v}
        elif k == "Stato":
            props[k] = {"status": {"name": v}}
        else:
            props[k] = {"rich_text": _testo(v)}
    _notion("PATCH", f"pages/{page_id}", {"properties": props})


def _props_bozza(b, s):
    import social
    return {
        "Titolo Adolos": {"rich_text": _testo(b.get("titolo", ""))},
        "Sintesi": {"rich_text": _testo(b.get("sintesi", ""))},
        "Punti carosello": {"rich_text": _testo("\n".join(b.get("punti", [])))},
        "Didascalia Instagram": {"rich_text": _testo(social.didascalia(s, {**b, "con_ai": True}))},
    }


def _props_indice(v):
    return {
        "Indice virale": {"number": v["indice"]},
        "Zona": {"select": {"name": v["zona"]}},
        "Perché virale": {"rich_text": _testo(v.get("perche", ""))},
        "Ganci alternativi": {"rich_text": _testo("\n".join(v.get("ganci", [])))},
    }


def _scheda(s, db, bozza, ind=None):
    global PAESI_NOMI
    if PAESI_NOMI is None:
        from adolos import PAESI
        PAESI_NOMI = PAESI
    fonti = s["fonti"]
    resto = s["n_fonti"] - min(6, len(fonti))
    elenco = ", ".join(f["fonte"] for f in fonti[:6]) + (" e un'altra" if resto == 1 else f" e altre {resto}" if resto > 1 else "")
    link = next((f["link"] for f in fonti if not f.get("correlato") and f["link"].startswith("http")), None)
    props = {
        "Titolo": {"title": _testo(s["titolo"][:200])},
        "Stato": {"status": {"name": "Da valutare"}},
        "Verifica": {"select": {"name": "Confermata" if s["stato"] == "confermato" else "Da verificare"}},
        "Instagram": {"select": {"name": INSTAGRAM.get(s["bot"], "No")}},
        "Importanza": {"number": s["calore"]},
        "Redazioni indipendenti": {"number": s["n_fonti"]},
        "Lingue": {"number": len(s.get("lingue", []))},
        "Sezione": {"select": {"name": s["sezione"]}},
        "Paesi": {"multi_select": [{"name": PAESI_NOMI.get(p, p)[:90]} for p in s["paesi"][:12]]},
        "Fonti": {"rich_text": _testo(elenco)},
        "Immagine": {"rich_text": _testo("Carosello Adolos generato dal sistema dopo l'approvazione. "
                                         "Niente foto delle testate: solo grafiche Adolos o foto con licenza libera.")},
        "Attendibilità": {"number": s.get("attendibilita", 0)},
        "Didascalia Instagram": {"rich_text": _testo(s.get("didascalia", ""))},
        "Data": {"date": {"start": s["aggiornata"][:10]}},
        "ID storia": {"rich_text": _testo(s["id"])},
        "Motivo del bot": {"rich_text": _testo(s.get("bot_motivo", ""))},
        "Controllo obbligatorio": {"checkbox": bool(s.get("controllo"))},
    }
    if bozza:
        props.update(_props_bozza(bozza, s))
    if ind:
        props.update(_props_indice(ind))
    if link:
        props["Link fonte"] = {"url": link}
    figli = []
    if s.get("controllo"):
        figli.append({"object": "block", "type": "callout", "callout": {
            "rich_text": _testo(s["controllo"] + " Presunzione d'innocenza, niente nomi di minori o di vittime."),
            "icon": {"type": "emoji", "emoji": "⚠️"}}})
    if bozza:
        figli.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": _testo("Bozza AI: i fatti da controllare")}})
        for k, v in (bozza.get("fatti") or {}).items():
            if v:
                figli.append({"object": "block", "type": "bulleted_list_item",
                              "bulleted_list_item": {"rich_text": _testo(f"{k.capitalize()}: {v}")}})
        if bozza.get("versioni_diverse"):
            figli.append({"object": "block", "type": "paragraph",
                          "paragraph": {"rich_text": _testo("Versioni diverse: " + bozza["versioni_diverse"])}})
        figli.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": _testo(
            "Controlla ogni fatto aprendo le fonti qui sotto. Correggi Titolo Adolos, Sintesi e Punti carosello, "
            "poi metti Stato = Approvata.")}})
    figli.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": _testo("Chi la riporta")}})
    for f in fonti[:25]:
        riga = f"{f['fonte']} ({PAESI_NOMI.get(f['paese'], f['paese'])})"
        if not f.get("correlato"):
            riga += f": {f['titolo']}"
            if f.get("titolo_it") and f["titolo_it"] != f["titolo"]:
                riga += f"  [{f['titolo_it']}]"
        testo = [{"type": "text", "text": {"content": riga[:1900],
                                           "link": {"url": f["link"]} if f["link"].startswith("http") else None}}]
        figli.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": testo}})
    return {"parent": {"database_id": db}, "properties": props, "children": figli}


MAX_AGGIORNAMENTI_INDICE = 20


def invia_notion(storie, st, bozze, indici=None):
    if not notion_attivo():
        return 0
    indici = indici or {}
    db = _env("NOTION_DB_REDAZIONE")
    fatte = aggiornate = agg_indice = 0
    # prima le notizie con l'indice più alto
    storie = sorted(storie, key=lambda s: indici.get(s["id"], {}).get("indice", 0), reverse=True)
    for s in storie:
        b = bozze.get(s["id"])
        ind = indici.get(s["id"])
        # indice cambiato di almeno 10 punti (o zona cambiata): aggiorniamo la scheda
        if s["id"] in st["notion"] and ind and agg_indice < MAX_AGGIORNAMENTI_INDICE:
            prima = st["indice"].get(s["id"])
            if not prima or abs(prima[0] - ind["indice"]) >= 10 or prima[1] != ind["zona"]:
                try:
                    _notion("PATCH", f"pages/{st['notion'][s['id']]}", {"properties": _props_indice(ind)})
                    st["indice"][s["id"]] = [ind["indice"], ind["zona"]]
                    agg_indice += 1
                except Exception as e:
                    print("Indice non aggiornato sulla scheda:", str(e)[:160])
        # scheda già creata e bozza arrivata dopo: la aggiungiamo
        if s["id"] in st["notion"]:
            if b and s["id"] not in st["bozze"]:
                try:
                    _notion("PATCH", f"pages/{st['notion'][s['id']]}", {"properties": _props_bozza(b, s)})
                    st["bozze"].append(s["id"])
                    aggiornate += 1
                except Exception as e:
                    print("Bozza non aggiunta alla scheda:", str(e)[:160])
            continue
        if fatte >= MAX_SCHEDE_AL_GIRO or s["bot"] not in ("post", "storia", "verifica"):
            continue
        try:
            pagina = _notion("POST", "pages", _scheda(s, db, b, ind))
            st["notion"][s["id"]] = pagina["id"]
            if ind:
                st["indice"][s["id"]] = [ind["indice"], ind["zona"]]
            if b:
                st["bozze"].append(s["id"])
            fatte += 1
        except Exception as e:
            print("Scheda Notion non creata:", str(e)[:160])
            break
    print(f"Notion: {fatte} schede nuove, {aggiornate} bozze aggiunte, {agg_indice} indici aggiornati")
    return fatte


def pagina_notion(sid):
    return _leggi_inviati()["notion"].get(sid)


# ---------------------------------------------------------------- Telegram (il vostro bot, API ufficiale)
def invia_telegram(storie, st, indici=None):
    token, chat = _env("TELEGRAM_BOT_TOKEN"), _env("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return 0
    import html
    import requests
    sito = (_env("SITO_URL") or "").rstrip("/")
    etichetta = {"post": "PROPOSTA POST", "storia": "PROPOSTA STORIA", "verifica": "DA VERIFICARE"}
    fatte = 0
    indici = indici or {}
    storie = sorted(storie, key=lambda s: indici.get(s["id"], {}).get("indice", 0), reverse=True)
    for s in storie:
        if fatte >= 8:
            break
        if s["bot"] not in etichetta or s["id"] in st["telegram"]:
            continue
        righe = [f"<b>{etichetta[s['bot']]}</b> · {html.escape(s['sezione'])} · calore {s['calore']}",
                 "", f"<b>{html.escape(s['titolo'])}</b>", "",
                 html.escape(s.get("bot_motivo", "")),
                 "Fonti: " + html.escape(", ".join(f["fonte"] for f in s["fonti"][:5]))]
        ind = indici.get(s["id"])
        if ind:
            righe.append(f"Indice virale {ind['indice']}/100 · zona {ind['zona'].lower()}")
        if s.get("controllo"):
            righe.append("⚠️ Controllo obbligatorio")
        if sito:
            righe.append(f'<a href="{sito}/storie/{s["id"]}.html">Apri sul sito</a>')
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=15, json={
                "chat_id": chat, "text": "\n".join(righe), "parse_mode": "HTML", "disable_web_page_preview": True})
            r.raise_for_status()
            st["telegram"].append(s["id"])
            fatte += 1
        except Exception as e:
            print("Telegram non inviato:", str(e)[:160])
            break
    print(f"Telegram: {fatte} avvisi inviati")
    return fatte


def invia(storie, bozze=None, indici=None):
    st = _leggi_inviati()
    invia_notion(storie, st, {k: v for k, v in (bozze or {}).items() if v}, indici)
    invia_telegram(storie, st, indici)
    _scrivi_inviati(st)
