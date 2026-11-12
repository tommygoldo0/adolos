"""
ADOLOS – approvazione da Telegram
=================================
Il bot manda nel gruppo della redazione ogni PACCHETTO PRONTO (copertina, titolo, sintesi) con due pulsanti:
"Approva (sito)" e "Scarta". Una persona preme; il motore legge il clic e cambia lo Stato della scheda Notion.

Regole:
  - Il pulsante lo preme sempre una persona. Qui dentro niente approva da solo.
  - Vale solo un clic fatto nel gruppo della redazione (TELEGRAM_CHAT_ID). Se la variabile TELEGRAM_APPROVATORI
    contiene degli ID utente Telegram (separati da virgola), valgono solo quelli.
  - "Approva" mette Stato = Approvata: la notizia va sul sito e si disegna il carosello.
    NON spunta "Pubblica su Instagram": quello si fa su Notion.
  - Zona Rossa: il primo clic chiede una conferma ("ho controllato nomi, accuse e fonti").
  - Prima di cambiare lo Stato si ricontrolla la scheda: deve essere ancora da decidere, con Pacchetto pronto,
    Titolo Adolos, Sintesi e Controllo legale diverso da "Da sistemare".
  - Sulla scheda resta scritto chi ha premuto e quando (campo "Motivo del bot").
  - Il token non finisce mai nel registro: gli errori riportano solo il codice e la descrizione di Telegram.

Serve: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, NOTION_TOKEN, NOTION_DB_REDAZIONE. Se manca qualcosa non fa niente.
"""

import io
import json
import os
from datetime import datetime, timezone, timedelta

import redazione

MAX_MESSAGGI_AL_GIRO = 6
DA_DECIDERE = ("Da valutare", "In revisione")
FILTRO_PRONTI = {"and": [{"property": "Pacchetto pronto", "checkbox": {"equals": True}},
                         {"or": [{"property": "Stato", "status": {"equals": x}} for x in DA_DECIDERE]}]}


def attivo():
    return bool(redazione._env("TELEGRAM_BOT_TOKEN") and redazione._env("TELEGRAM_CHAT_ID") and redazione.notion_attivo())


def _tg(metodo, dati=None, foto=None):
    """Chiamata all'API ufficiale di Telegram. Gli errori non contengono mai l'indirizzo (che ha dentro il token)."""
    import requests
    url = f"https://api.telegram.org/bot{redazione._env('TELEGRAM_BOT_TOKEN')}/{metodo}"
    try:
        if foto is not None:
            campi = {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in (dati or {}).items()}
            r = requests.post(url, data=campi, files={"photo": ("copertina.jpg", foto, "image/jpeg")}, timeout=40)
        else:
            r = requests.post(url, json=dati or {}, timeout=25)
        corpo = r.json()
    except Exception as e:
        raise RuntimeError(f"Telegram {metodo}: {type(e).__name__}") from None
    if not corpo.get("ok"):
        raise RuntimeError(f"Telegram {metodo}: {corpo.get('error_code')} {str(corpo.get('description'))[:120]}")
    return corpo.get("result")


def _ora_roma():
    # ora italiana senza librerie in più: +1 d'inverno, +2 d'estate (ultima domenica di marzo e di ottobre)
    u = datetime.now(timezone.utc)
    def ultima_domenica(mese):
        d = datetime(u.year, mese, 31, 1, tzinfo=timezone.utc)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    estate = ultima_domenica(3) <= u < ultima_domenica(10)
    return (u + timedelta(hours=2 if estate else 1)).strftime("%d/%m %H:%M")


# ---------------------------------------------------------------- 1. mandare i pacchetti pronti
def _tastiera(sid, zona, conferma=False):
    if conferma:
        return {"inline_keyboard": [[{"text": "⚠️ Confermo: ho controllato", "callback_data": f"ok:{sid}"}],
                                    [{"text": "↩️ Annulla", "callback_data": f"indietro:{sid}"}]]}
    approva = f"chk:{sid}" if zona == "Rossa" else f"ok:{sid}"
    return {"inline_keyboard": [[{"text": "✅ Approva (sito)", "callback_data": approva},
                                 {"text": "🗑 Scarta", "callback_data": f"no:{sid}"}]]}


def _copertina(s, gruppo, testi):
    """Anteprima della copertina del carosello (stessa grafica che uscirà dopo l'approvazione). Restituisce (bytes, credito)."""
    import social
    from sito import CONT_DI
    from adolos import PAESI
    foto = None
    try:
        import immagini
        foto = immagini.per_storia(s, testi.get("titolo") or s["titolo"], gruppo or [])
    except Exception as e:
        print("Telegram: foto della copertina non cercata:", str(e)[:120])
    t = {**testi, "_immagine": foto} if foto else testi
    img = social.carosello(s, t, PAESI, CONT_DI)[0]
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=85)
    return buf.getvalue(), (foto or {}).get("credito", "")


def _testo_pacchetto(p, s, credito=""):
    import html
    lt = redazione._leggi_testo
    zona = lt(p.get("Zona")) or "?"
    indice = (p.get("Indice virale") or {}).get("number")
    testate = (p.get("Redazioni indipendenti") or {}).get("number")
    righe = ["<b>PACCHETTO PRONTO</b> · " + html.escape(lt(p.get("Sezione")) or "")
             + (f" · indice {int(indice)}" if indice is not None else "")
             + (" · 🔴 ZONA ROSSA" if zona == "Rossa" else " · zona verde" if zona == "Verde" else ""),
             "", "<b>" + html.escape(lt(p.get("Titolo Adolos"))) + "</b>", "", html.escape(lt(p.get("Sintesi"))[:560]), ""]
    if zona == "Rossa":
        righe.append("🔴 Zona rossa: controlla nomi, accuse e fonti prima di approvare.")
    if testate is not None:
        righe.append(f"Testate: {int(testate)}" + (" (meno di 2: non approvare)" if testate < 2 else ""))
    fonti = lt(p.get("Fonti")).splitlines()
    if fonti:
        righe.append("Fonti: " + html.escape(fonti[0][:160]))
    if s:
        nota = redazione._nota_proprieta(s, "Proprietà (da verificare): ")
        if nota:
            righe.append(html.escape(nota))
    if credito:
        righe.append("Foto: " + html.escape(credito[:140]))
    righe.append("Testi preparati con l'AI: controlla i fatti sulle fonti.")
    return "\n".join(righe)


def invia_pacchetti(storie, gruppi=None):
    """Manda nel gruppo i pacchetti pronti non ancora mandati. Si chiama nel giro completo."""
    if not attivo():
        return 0
    st = redazione._leggi_inviati()
    mandati = st.setdefault("pacchetti", [])
    try:
        righe = redazione._tutte_le_righe(redazione._env("NOTION_DB_REDAZIONE"), FILTRO_PRONTI)
    except Exception as e:
        print("Telegram: pacchetti pronti non letti da Notion:", str(e)[:160])
        return 0
    per_id = {s["id"]: s for s in storie}
    chat, fatte = redazione._env("TELEGRAM_CHAT_ID"), 0
    for r in righe:
        if fatte >= MAX_MESSAGGI_AL_GIRO:
            break
        p = r["properties"]
        lt = redazione._leggi_testo
        sid = lt(p.get("ID storia"))
        if not sid or r["id"] in mandati:
            continue
        if not (lt(p.get("Titolo Adolos")) and lt(p.get("Sintesi"))) or lt(p.get("Controllo legale")) == "Da sistemare":
            continue                       # pacchetto incompleto o bloccato dal controllo legale: niente pulsanti
        s = per_id.get(sid)
        zona = lt(p.get("Zona"))
        foto, credito = None, ""
        if s:
            try:
                punti = [x.strip(" -•\t") for x in lt(p.get("Punti carosello")).splitlines() if x.strip(" -•\t")]
                foto, credito = _copertina(s, (gruppi or {}).get(sid), {"titolo": lt(p.get("Titolo Adolos")),
                                                                         "sintesi": lt(p.get("Sintesi")), "punti": punti[:4]})
            except Exception as e:
                print("Telegram: copertina non disegnata per", sid, "-", str(e)[:120])
        testo = _testo_pacchetto(p, s, credito)
        tasti = _tastiera(sid, zona)
        if r.get("url"):
            tasti["inline_keyboard"].append([{"text": "Apri la scheda su Notion", "url": r["url"]}])
        try:
            if foto:
                _tg("sendPhoto", {"chat_id": chat, "caption": testo[:1020], "parse_mode": "HTML", "reply_markup": tasti}, foto=foto)
            else:
                _tg("sendMessage", {"chat_id": chat, "text": testo, "parse_mode": "HTML",
                                    "disable_web_page_preview": True, "reply_markup": tasti})
            mandati.append(r["id"])
            fatte += 1
        except Exception as e:
            print("Telegram: pacchetto non inviato:", str(e)[:160])
            break
    st["pacchetti"] = mandati[-3000:]
    redazione._scrivi_inviati(st)
    print(f"Telegram: {fatte} pacchetti pronti inviati con i pulsanti")
    return fatte


# ---------------------------------------------------------------- 2. leggere i clic
def _autorizzato(cq):
    chat = str(((cq.get("message") or {}).get("chat") or {}).get("id", ""))
    if chat != str(redazione._env("TELEGRAM_CHAT_ID")):
        return False
    permessi = {x.strip() for x in (redazione._env("TELEGRAM_APPROVATORI") or "").split(",") if x.strip()}
    return not permessi or str((cq.get("from") or {}).get("id", "")) in permessi


def _nome(cq):
    u = cq.get("from") or {}
    return (" ".join(x for x in (u.get("first_name"), u.get("last_name")) if x) or u.get("username") or "sconosciuto")[:60]


def _scheda_per_id(sid):
    r = redazione._notion("POST", f"databases/{redazione._env('NOTION_DB_REDAZIONE')}/query",
                          {"page_size": 5, "filter": {"property": "ID storia", "rich_text": {"equals": sid}}})
    return r["results"][0] if r.get("results") else None


def _decidi(azione, sid, chi):
    """Cambia lo Stato della scheda dopo il clic di una persona. Restituisce (riuscito, frase per Telegram)."""
    lt = redazione._leggi_testo
    pagina = _scheda_per_id(sid)
    if not pagina:
        return False, "Scheda non trovata su Notion."
    p = pagina["properties"]
    stato = lt(p.get("Stato"))
    if stato not in DA_DECIDERE:
        return False, f"Già decisa: la scheda è \"{stato}\"."
    if azione == "ok":
        if lt(p.get("Pacchetto pronto")) != "si":
            return False, "Il pacchetto non è più segnato come pronto: guarda la scheda su Notion."
        if lt(p.get("Controllo legale")) == "Da sistemare":
            return False, "Bloccata dal controllo legale: va sistemata su Notion."
        if not (lt(p.get("Titolo Adolos")) and lt(p.get("Sintesi"))):
            return False, "Mancano Titolo Adolos o Sintesi: non si può approvare."
    nuovo = "Approvata" if azione == "ok" else "Scartata"
    nota = (lt(p.get("Motivo del bot")) + f"\n{nuovo} da Telegram da {chi} il {_ora_roma()}.").strip()
    redazione._notion("PATCH", f"pages/{pagina['id']}", {"properties": {
        "Stato": {"status": {"name": nuovo}}, "Motivo del bot": {"rich_text": redazione._testo(nota[-1900:])}}})
    titolo = lt(p.get("Titolo Adolos")) or lt(p.get("Titolo"))
    print(f"Telegram: {sid} -> {nuovo} (premuto da una persona nel gruppo)")
    if azione == "ok":
        return True, f"✅ Approvata da {chi}: «{titolo[:120]}». Sul sito tra pochi minuti. Per Instagram: spunta su Notion."
    return True, f"🗑 Scartata da {chi}: «{titolo[:120]}»."


def leggi_risposte():
    """Legge i clic sui pulsanti e li applica a Notion. Restituisce quante schede ha cambiato.
    Non tiene memoria: Telegram conserva i clic finché non li confermiamo, quindi nessun clic si perde."""
    if not attivo():
        return 0
    try:
        aggiornamenti = _tg("getUpdates", {"timeout": 0, "allowed_updates": ["callback_query"]}) or []
    except Exception as e:
        print("Telegram: clic non letti:", str(e)[:160])
        return 0
    cambiate, ultimo = 0, None
    for a in aggiornamenti:
        ultimo = a.get("update_id")
        cq = a.get("callback_query")
        if not cq:
            continue
        azione, _, sid = str(cq.get("data", "")).partition(":")
        sid = "".join(c for c in sid if c.isalnum())[:40]
        msg = cq.get("message") or {}
        dove = {"chat_id": (msg.get("chat") or {}).get("id"), "message_id": msg.get("message_id")}
        try:
            if not _autorizzato(cq):
                _tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "Non sei tra chi può approvare.", "show_alert": True})
                print("Telegram: clic ignorato, non arriva dal gruppo della redazione o da una persona autorizzata")
                continue
            if azione in ("chk", "indietro") and sid:
                # zona rossa: prima una conferma. Si tengono gli altri tasti (es. il link alla scheda)
                extra = [riga for riga in ((msg.get("reply_markup") or {}).get("inline_keyboard") or []) if any("url" in t for t in riga)]
                tasti = _tastiera(sid, "Rossa", conferma=(azione == "chk"))
                tasti["inline_keyboard"] += extra
                _tg("editMessageReplyMarkup", {**dove, "reply_markup": tasti})
                _tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text":
                    "Zona rossa: conferma solo se hai controllato nomi, accuse e fonti." if azione == "chk" else "Annullato."})
                continue
            if azione not in ("ok", "no") or not sid:
                _tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "Pulsante non riconosciuto."})
                continue
            riuscito, frase = _decidi(azione, sid, _nome(cq))
            _tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text": frase[:190], "show_alert": not riuscito})
            if riuscito:
                cambiate += 1
                _tg("editMessageReplyMarkup", {**dove, "reply_markup": {"inline_keyboard": []}})
                _tg("sendMessage", {"chat_id": dove["chat_id"], "text": frase, "reply_to_message_id": dove["message_id"],
                                    "allow_sending_without_reply": True})
        except Exception as e:
            print("Telegram: clic non applicato:", str(e)[:160])
            try:                           # chi ha premuto deve saperlo: niente errori silenziosi
                _tg("answerCallbackQuery", {"callback_query_id": cq["id"], "show_alert": True,
                                            "text": "Errore: la scheda non è stata cambiata. Riprova tra un minuto o usa Notion."})
            except Exception:
                pass
    if ultimo is not None:
        try:                               # conferma a Telegram: questi clic sono stati letti
            _tg("getUpdates", {"timeout": 0, "offset": ultimo + 1, "allowed_updates": ["callback_query"]})
        except Exception as e:
            print("Telegram: clic non confermati (verranno riletti, senza danni):", str(e)[:160])
    if aggiornamenti:
        print(f"Telegram: {len(aggiornamenti)} clic letti, {cambiate} schede cambiate")
    return cambiate
