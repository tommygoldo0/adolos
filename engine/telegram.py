"""
ADOLOS – approvazione da Telegram
=================================
Il bot manda nel gruppo della redazione ogni PACCHETTO PRONTO (tutte le slide del carosello in un album, poi
titolo e sintesi) con due pulsanti:
"Approva (sito)" e "Scarta". Una persona preme; il motore legge il clic e cambia lo Stato della scheda Notion.

Regole:
  - Il pulsante lo preme sempre una persona. Qui dentro niente approva da solo.
  - Vale solo un clic fatto nel gruppo della redazione (TELEGRAM_CHAT_ID). Se la variabile TELEGRAM_APPROVATORI
    contiene degli ID utente Telegram (separati da virgola), valgono solo quelli.
  - "Approva (sito)" mette Stato = Approvata: la notizia va sul sito e si disegna il carosello.
  - "Approva + Instagram" fa lo stesso e in più spunta "Pubblica su Instagram": il post entra in coda ed esce al
    primo orario libero. Dopo un "Approva (sito)" resta il pulsante "Metti in coda Instagram".
    La casella la spunta sempre il clic di una persona: il motore da solo non la tocca mai.
  - Zona Rossa: il primo clic chiede una conferma ("ho controllato nomi, accuse e fonti") e servono DUE persone
    diverse. Se dopo 30 minuti (variabile TELEGRAM_ATTESA_SECONDA) non c'è una seconda persona, la prima può
    confermare da sola: sulla scheda resta scritto che ha approvato una persona sola.
  - Prima di cambiare lo Stato si ricontrolla la scheda: deve essere ancora da decidere, con Pacchetto pronto,
    Titolo Adolos, Sintesi e Controllo legale diverso da "Da sistemare".
  - Sulla scheda resta scritto chi ha premuto e quando (campo "Motivo del bot").
  - Il token non finisce mai nel registro: gli errori riportano solo il codice e la descrizione di Telegram.

Gli AVVISI (le notizie che crescono) hanno due pulsanti in più: "Prepara carosello" e "Prepara video". Il clic di una
persona mette la scheda "In revisione" e la prossima edizione la prepara per prima. Ogni pacchetto arriva anche
come file .zip con tutte le slide in qualità piena, da scaricare.

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


def _tg(metodo, dati=None, foto=None, allegati=None, documento=None):
    """Chiamata all'API ufficiale di Telegram. Gli errori non contengono mai l'indirizzo (che ha dentro il token).
    foto = una sola immagine (bytes); allegati = {nome: bytes} per un album (sendMediaGroup, "attach://nome");
    documento = (nome del file, bytes) per mandare un file da scaricare (sendDocument)."""
    import requests
    url = f"https://api.telegram.org/bot{redazione._env('TELEGRAM_BOT_TOKEN')}/{metodo}"
    try:
        if foto is not None or allegati or documento:
            campi = {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in (dati or {}).items()}
            file = {"photo": ("copertina.jpg", foto, "image/jpeg")} if foto is not None else \
                   {"document": (documento[0], documento[1], "application/zip")} if documento else \
                   {n: (n + ".jpg", b, "image/jpeg") for n, b in allegati.items()}
            r = requests.post(url, data=campi, files=file, timeout=90)
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
def _tastiera(sid, zona, conferma=None):
    """Pulsanti del pacchetto. "ok" = solo sito, "ig" = sito + coda Instagram, "no" = scarta.
    conferma = "ok" o "ig": secondo passo della zona rossa ("ho controllato")."""
    if conferma:
        return {"inline_keyboard": [[{"text": "⚠️ Confermo: ho controllato", "callback_data": f"{conferma}:{sid}"}],
                                    [{"text": "↩️ Annulla", "callback_data": f"indietro:{sid}"}]]}
    rossa = zona == "Rossa"
    return {"inline_keyboard": [[{"text": "✅ Approva (sito)", "callback_data": f"{'chk' if rossa else 'ok'}:{sid}"},
                                 {"text": "📸 Approva + Instagram", "callback_data": f"{'chkig' if rossa else 'ig'}:{sid}"}],
                                [{"text": "🗑 Scarta", "callback_data": f"no:{sid}"}]]}


ORARI_IG = "8:00, 12:30, 18:30, 21:00"


def _slide(s, gruppo, testi):
    """Anteprima di TUTTE le slide del carosello (la stessa grafica che uscirà dopo l'approvazione).
    Le disegna il codice, non un'AI: non costa niente. Restituisce (lista di JPEG in bytes, credito della foto)."""
    import social
    from sito import CONT_DI
    from adolos import PAESI
    foto = None
    try:
        import immagini
        foto = immagini.per_storia(s, testi.get("titolo") or s["titolo"], gruppo or [], "",
                                   (testi.get("sintesi") or "") + " " + " ".join(testi.get("punti") or []))
    except Exception as e:
        print("Telegram: foto della copertina non cercata:", str(e)[:120])
    t = {**testi, "_immagine": foto} if foto else testi
    fatte = []
    for img in social.carosello(s, t, PAESI, CONT_DI)[:10]:       # Telegram: al massimo 10 immagini per album
        buf = io.BytesIO()
        img.convert("RGB").save(buf, "JPEG", quality=85)
        fatte.append(buf.getvalue())
    return fatte, (foto or {}).get("credito", "")


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
    # "pacchetti_v3": con lo stile "Foto" i pacchetti ancora da decidere si rimandano una volta
    mandati = st.setdefault("pacchetti_v3", [])
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
        slide, credito = [], ""
        if s:
            try:
                punti = [x.strip(" -•\t") for x in lt(p.get("Punti carosello")).splitlines() if x.strip(" -•\t")]
                slide, credito = _slide(s, (gruppi or {}).get(sid), {"titolo": lt(p.get("Titolo Adolos")),
                                                                     "sintesi": lt(p.get("Sintesi")), "punti": punti[:4]})
            except Exception as e:
                print("Telegram: carosello non disegnato per", sid, "-", str(e)[:120])
        testo = _testo_pacchetto(p, s, credito)
        tasti = _tastiera(sid, zona)
        if r.get("url"):
            tasti["inline_keyboard"].append([{"text": "Apri la scheda su Notion", "url": r["url"]}])
        try:
            # un album non può avere pulsanti: prima tutte le slide, poi il messaggio con testo e pulsanti in risposta
            risposta = {}
            if len(slide) >= 2:
                try:
                    album = _tg("sendMediaGroup", {"chat_id": chat, "media": [
                        {"type": "photo", "media": f"attach://s{i}"} for i in range(len(slide))]},
                        allegati={f"s{i}": b for i, b in enumerate(slide)})
                    if album:
                        risposta = {"reply_to_message_id": album[0]["message_id"], "allow_sending_without_reply": True}
                except Exception as e:
                    print("Telegram: album non inviato, mando solo il testo:", str(e)[:160])
            if len(slide) >= 2:            # lo stesso carosello come file, in qualità piena, da scaricare con un tocco
                try:
                    import zipfile
                    pacco = io.BytesIO()
                    with zipfile.ZipFile(pacco, "w", zipfile.ZIP_STORED) as z:
                        for i, b in enumerate(slide, 1):
                            z.writestr(f"adolos-{sid}-{i:02d}.jpg", b)
                    _tg("sendDocument", {"chat_id": chat, "caption": "Carosello da scaricare (tutte le slide, 1080×1350)",
                                         "disable_notification": True, **risposta},
                        documento=(f"adolos-carosello-{sid}.zip", pacco.getvalue()))
                except Exception as e:
                    print("Telegram: file del carosello non inviato:", str(e)[:160])
            _tg("sendMessage", {"chat_id": chat, "text": testo, "parse_mode": "HTML",
                                "disable_web_page_preview": True, "reply_markup": tasti, **risposta})
            mandati.append(r["id"])
            fatte += 1
            # nel registro si deve capire come è arrivato ogni pacchetto
            print(f"Telegram: pacchetto {sid} inviato " + (f"con {len(slide)} slide" + (" e foto" if credito else ", senza foto")
                  if slide else "solo testo (la notizia non è più tra quelle delle ultime 48 ore: niente slide)"))
        except Exception as e:
            print("Telegram: pacchetto non inviato:", str(e)[:160])
            break
    st["pacchetti_v3"] = mandati[-3000:]
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


ATTESA_SECONDA_MIN = 30        # zona rossa: dopo questi minuti senza una seconda persona, la prima può confermare da sola
_RE_PRIMA = None


def _attesa_seconda():
    try:
        return max(0, int(redazione._env("TELEGRAM_ATTESA_SECONDA") or ATTESA_SECONDA_MIN))
    except ValueError:
        return ATTESA_SECONDA_MIN


def _prima_approvazione(nota):
    """Cerca nella nota della scheda la prima approvazione di zona rossa: (nome, id utente, minuti passati) o None."""
    global _RE_PRIMA
    import re
    if _RE_PRIMA is None:
        _RE_PRIMA = re.compile(r"Prima approvazione zona rossa: (.+?) \[(\d+)\] (\d{4}-\d\d-\d\dT\d\d:\d\d)")
    m = None
    for m in _RE_PRIMA.finditer(nota or ""):
        pass                               # vale l'ultima
    if not m:
        return None
    quando = datetime.strptime(m.group(3), "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    return m.group(1), m.group(2), (datetime.now(timezone.utc) - quando).total_seconds() / 60


def _decidi(azione, sid, chi, uid=""):
    """Cambia lo Stato della scheda dopo il clic di una persona. Restituisce (esito, frase per Telegram):
    esito "fatto" = Stato cambiato · "attesa" = zona rossa, registrata la prima approvazione · "no" = niente.
    Zona rossa: servono due persone diverse. Se dopo ATTESA_SECONDA_MIN minuti non c'è una seconda persona,
    la prima può confermare da sola (e sulla scheda resta scritto)."""
    lt = redazione._leggi_testo
    pagina = _scheda_per_id(sid)
    if not pagina:
        return "no", "Scheda non trovata su Notion."
    p = pagina["properties"]
    stato = lt(p.get("Stato"))
    titolo = lt(p.get("Titolo Adolos")) or lt(p.get("Titolo"))
    if azione == "igdopo":
        # notizia già approvata per il sito: una persona la mette anche in coda per Instagram
        if stato != "Approvata":
            return "no", f"Si può mettere in coda solo una notizia approvata: la scheda è \"{stato}\"."
        if lt(p.get("Link Instagram")):
            return "no", "È già stata pubblicata su Instagram."
        if lt(p.get("Pubblica su Instagram")) == "si":
            return "no", f"È già in coda per Instagram: esce al primo orario libero ({ORARI_IG})."
        if lt(p.get("Controllo legale")) == "Da sistemare":
            return "no", "Bloccata dal controllo legale: va sistemata su Notion."
        nota = (lt(p.get("Motivo del bot")) + f"\nMessa in coda Instagram da Telegram da {chi} il {_ora_roma()}.").strip()
        redazione._notion("PATCH", f"pages/{pagina['id']}", {"properties": {
            "Pubblica su Instagram": {"checkbox": True}, "Motivo del bot": {"rich_text": redazione._testo(nota[-1900:])}}})
        print(f"Telegram: {sid} messa in coda Instagram (premuto da una persona nel gruppo)")
        return "fatto", f"📸 In coda per Instagram, messa da {chi}: «{titolo[:90]}». Esce al primo orario libero ({ORARI_IG})."
    if stato not in DA_DECIDERE:
        return "no", f"Già decisa: la scheda è \"{stato}\"."
    instagram = azione == "ig"              # "ig" = come "ok", più la casella Instagram
    if instagram:
        azione = "ok"
    if azione == "ok":
        if lt(p.get("Pacchetto pronto")) != "si":
            return "no", "Il pacchetto non è più segnato come pronto: guarda la scheda su Notion."
        if lt(p.get("Controllo legale")) == "Da sistemare":
            return "no", "Bloccata dal controllo legale: va sistemata su Notion."
        if not (lt(p.get("Titolo Adolos")) and lt(p.get("Sintesi"))):
            return "no", "Mancano Titolo Adolos o Sintesi: non si può approvare."
    firma = chi
    if azione == "ok" and lt(p.get("Zona")) == "Rossa":
        prima, attesa = _prima_approvazione(lt(p.get("Motivo del bot"))), _attesa_seconda()
        if not prima:
            adesso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
            nota = (lt(p.get("Motivo del bot")) + f"\nPrima approvazione zona rossa: {chi} [{uid}] {adesso}").strip()
            redazione._notion("PATCH", f"pages/{pagina['id']}", {"properties": {
                "Motivo del bot": {"rich_text": redazione._testo(nota[-1900:])}}})
            print(f"Telegram: {sid} zona rossa, prima approvazione registrata: ne serve una seconda")
            return "attesa", (f"Zona rossa: prima approvazione di {chi}. Serve una seconda persona. "
                              f"Se tra {attesa} minuti non c'è nessuno, {chi} può confermare da solo.")
        if str(prima[1]) == str(uid):
            if prima[2] < attesa:
                return "no", (f"Hai già approvato: serve un'altra persona. Se non c'è nessuno, "
                              f"potrai confermare da solo tra {int(attesa - prima[2]) + 1} minuti.")
            firma = f"{chi} da solo (nessuna seconda persona dopo {attesa} minuti)"
        else:
            firma = f"{prima[0]} e {chi}"
    nuovo = "Approvata" if azione == "ok" else "Scartata"
    coda = " e messa in coda Instagram" if instagram else ""
    nota = (lt(p.get("Motivo del bot")) + f"\n{nuovo}{coda} da Telegram da {firma} il {_ora_roma()}.").strip()
    proprieta = {"Stato": {"status": {"name": nuovo}}, "Motivo del bot": {"rich_text": redazione._testo(nota[-1900:])}}
    if instagram:                          # la casella la spunta il clic di una persona, mai il motore da solo
        proprieta["Pubblica su Instagram"] = {"checkbox": True}
    redazione._notion("PATCH", f"pages/{pagina['id']}", {"properties": proprieta})
    print(f"Telegram: {sid} -> {nuovo}{coda} (premuto da una persona nel gruppo)")
    if instagram:
        return "fatto_ig", f"✅📸 Approvata da {firma} e in coda per Instagram: «{titolo[:80]}». Esce al primo orario libero ({ORARI_IG})."
    if azione == "ok":
        return "fatto", f"✅ Approvata da {firma} per il sito: «{titolo[:100]}». Per Instagram c'è il pulsante qui sopra."
    return "scartata", f"🗑 Scartata da {chi}: «{titolo[:120]}»."


def _richiedi(tipo, sid, chi):
    """Una persona chiede dal telefono di preparare il carosello ("req") o il video ("reqv") di una notizia.
    La scheda passa a "In revisione" (= "mi piace, preparala") e la richiesta resta scritta: la prepara la prossima
    edizione, con la precedenza sulle altre. Non approva e non pubblica niente."""
    lt = redazione._leggi_testo
    pagina = _scheda_per_id(sid)
    if not pagina:
        return "no", "Scheda non trovata su Notion."
    p = pagina["properties"]
    stato, cosa = lt(p.get("Stato")), "video" if tipo == "reqv" else "carosello"
    if stato not in DA_DECIDERE:
        return "no", f"Già decisa: la scheda è \"{stato}\"."
    testate = (p.get("Redazioni indipendenti") or {}).get("number") or 0
    if testate < 2:
        return "no", "Per ora ne parla una sola testata: serve almeno una seconda fonte prima di prepararla."
    nota = lt(p.get("Motivo del bot"))
    if f"Richiesto {cosa}" in nota:
        return "no", f"Il {cosa} è già stato richiesto: arriva con la prossima edizione."
    if cosa == "carosello" and lt(p.get("Pacchetto pronto")) == "si":
        return "no", "Il pacchetto è già pronto: cercalo tra i pacchetti con i pulsanti Approva."
    nota = (nota + f"\nRichiesto {cosa} da Telegram da {chi} il {_ora_roma()}.").strip()
    redazione._notion("PATCH", f"pages/{pagina['id']}", {"properties": {
        "Stato": {"status": {"name": "In revisione"}}, "Motivo del bot": {"rich_text": redazione._testo(nota[-1900:])}}})
    titolo = lt(p.get("Titolo Adolos")) or lt(p.get("Titolo"))
    print(f"Telegram: {sid} richiesto {cosa} (premuto da una persona nel gruppo)")
    return "richiesta", f"{'🎬' if cosa == 'video' else '🎠'} {chi} ha chiesto il {cosa}: «{titolo[:80]}». Lo prepara la prossima edizione."


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
            if azione in ("chk", "chkig", "indietro") and sid:
                # zona rossa: prima una conferma. Si tengono gli altri tasti (es. il link alla scheda)
                extra = [riga for riga in ((msg.get("reply_markup") or {}).get("inline_keyboard") or []) if any("url" in t for t in riga)]
                tasti = _tastiera(sid, "Rossa", conferma={"chk": "ok", "chkig": "ig"}.get(azione))
                tasti["inline_keyboard"] += extra
                _tg("editMessageReplyMarkup", {**dove, "reply_markup": tasti})
                _tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text":
                    "Annullato." if azione == "indietro" else "Zona rossa: conferma solo se hai controllato nomi, accuse e fonti."})
                continue
            if azione in ("req", "reqv") and sid:
                esito, frase = _richiedi(azione, sid, _nome(cq))
                _tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text": frase[:190], "show_alert": esito == "no"})
                if esito == "richiesta":
                    cambiate += 1
                    # resta l'altro pulsante (e il link): quello premuto si toglie
                    righe = [[t for t in riga if t.get("callback_data") != f"{azione}:{sid}"]
                             for riga in ((msg.get("reply_markup") or {}).get("inline_keyboard") or [])]
                    _tg("editMessageReplyMarkup", {**dove, "reply_markup": {"inline_keyboard": [r for r in righe if r]}})
                    _tg("sendMessage", {"chat_id": dove["chat_id"], "text": frase, "reply_to_message_id": dove["message_id"],
                                        "allow_sending_without_reply": True, "disable_notification": True})
                continue
            if azione not in ("ok", "ig", "igdopo", "no") or not sid:
                _tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text": "Pulsante non riconosciuto."})
                continue
            esito, frase = _decidi(azione, sid, _nome(cq), str((cq.get("from") or {}).get("id", "")))
            _tg("answerCallbackQuery", {"callback_query_id": cq["id"], "text": frase[:190], "show_alert": esito in ("no", "attesa")})
            extra = [riga for riga in ((msg.get("reply_markup") or {}).get("inline_keyboard") or []) if any("url" in t for t in riga)]
            if esito == "attesa":          # zona rossa: restano i pulsanti per la seconda persona
                _tg("editMessageReplyMarkup", {**dove, "reply_markup": {"inline_keyboard": [
                    [{"text": "✅ Seconda approvazione", "callback_data": f"ok:{sid}"},
                     {"text": "📸 Seconda + Instagram", "callback_data": f"ig:{sid}"}],
                    [{"text": "🗑 Scarta", "callback_data": f"no:{sid}"}]] + extra}})
                _tg("sendMessage", {"chat_id": dove["chat_id"], "text": frase, "reply_to_message_id": dove["message_id"],
                                    "allow_sending_without_reply": True})
            if esito in ("fatto", "fatto_ig", "scartata"):
                cambiate += 1
                # approvata solo per il sito: resta un pulsante per metterla in coda su Instagram più tardi
                dopo = [[{"text": "📸 Metti in coda Instagram", "callback_data": f"igdopo:{sid}"}]] \
                    if (esito == "fatto" and azione == "ok") else []
                _tg("editMessageReplyMarkup", {**dove, "reply_markup": {"inline_keyboard": dopo + (extra if dopo else [])}})
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
