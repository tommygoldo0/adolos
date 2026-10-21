"""
ADOLOS – collegamento all'intelligenza artificiale (facoltativo)
================================================================
Si usa solo con API ufficiali e solo se su GitHub c'è il secret AI_KEY.
Senza chiave tutto il resto funziona lo stesso, gratis.

Secret / variabili (GitHub > Settings > Secrets and variables > Actions):
  AI_KEY        la chiave dell'API (Anthropic, OpenAI, Mistral o Gemini)
  AI_PROVIDER   facoltativo: anthropic | openai | mistral | gemini (se manca vale quello in fonti.json)
  AI_MODEL      facoltativo: il modello (se manca vale quello in fonti.json)

Tetto di spesa: in engine/fonti.json, voce "ai" > "budget_mensile_usd". Il motore conta i token
usati nel mese (engine/cache/uso_ai.json) e quando arriva al tetto si ferma fino al mese dopo.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
CACHE = ENGINE / "cache"
USO = CACHE / "uso_ai.json"

OPENAI_COMPATIBILI = {
    "openai": "https://api.openai.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
}

# prezzi noti in dollari per milione di token (input, output), verificati a ottobre 2026
PREZZI = {
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "claude-haiku-5-5": (0.10, 0.50),
}

_conf = None


def conf():
    global _conf
    if _conf is None:
        try:
            _conf = json.loads((ENGINE / "fonti.json").read_text(encoding="utf-8")).get("ai", {})
        except Exception:
            _conf = {}
    return _conf


def attiva():
    return bool(os.environ.get("AI_KEY", "").strip())


def _mese():
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _leggi_uso():
    try:
        u = json.loads(USO.read_text(encoding="utf-8"))
        if u.get("mese") == _mese():
            return u
    except Exception:
        pass
    return {"mese": _mese(), "input": 0, "output": 0, "costo_usd": 0.0, "chiamate": 0}


def _scrivi_uso(u):
    CACHE.mkdir(parents=True, exist_ok=True)
    USO.write_text(json.dumps(u), encoding="utf-8")


def spesa_mese():
    return _leggi_uso()


def budget_rimasto():
    c = conf()
    return float(c.get("budget_mensile_usd", 5)) - _leggi_uso()["costo_usd"]


class TettoRaggiunto(Exception):
    pass


def chiedi(sistema, testo, max_token=1200):
    """Manda una richiesta al modello e restituisce il testo della risposta.
    Conta i token e rispetta il tetto di spesa mensile."""
    import requests
    if not attiva():
        raise RuntimeError("AI non configurata (manca AI_KEY)")
    if budget_rimasto() <= 0:
        raise TettoRaggiunto("tetto di spesa del mese raggiunto")
    c = conf()
    provider = (os.environ.get("AI_PROVIDER") or c.get("provider") or "gemini").strip().lower()
    modello = (os.environ.get("AI_MODEL") or c.get("modello") or "gemini-3.1-flash-lite").strip()
    chiave = os.environ["AI_KEY"].strip()

    for tentativo in range(3):
        if provider == "anthropic":
            r = requests.post("https://api.anthropic.com/v1/messages", timeout=90, headers={
                "x-api-key": chiave, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": modello, "max_tokens": max_token, "system": sistema,
                      "messages": [{"role": "user", "content": testo}]})
        else:
            base = OPENAI_COMPATIBILI.get(provider)
            if not base:
                raise RuntimeError(f"provider sconosciuto: {provider}")
            r = requests.post(base + "/chat/completions", timeout=90, headers={
                "Authorization": "Bearer " + chiave, "Content-Type": "application/json"},
                json={"model": modello, "max_tokens": max_token,
                      "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": testo}]})
        if r.status_code in (429, 500, 502, 503, 529) and tentativo < 2:
            time.sleep(4 * (tentativo + 1))
            continue
        if r.status_code >= 300:
            raise RuntimeError(f"AI {provider} {r.status_code}: {r.text[:200]}")
        break

    dati = r.json()
    if provider == "anthropic":
        risposta = "".join(b.get("text", "") for b in dati.get("content", []) if b.get("type") == "text")
        t_in = dati.get("usage", {}).get("input_tokens", 0)
        t_out = dati.get("usage", {}).get("output_tokens", 0)
    else:
        risposta = dati["choices"][0]["message"]["content"] or ""
        t_in = dati.get("usage", {}).get("prompt_tokens", 0)
        t_out = dati.get("usage", {}).get("completion_tokens", 0)

    u = _leggi_uso()
    u["input"] += t_in
    u["output"] += t_out
    u["chiamate"] += 1
    p_in, p_out = PREZZI.get(modello, (float(c.get("prezzo_input_per_milione", 0.25)),
                                       float(c.get("prezzo_output_per_milione", 1.50))))
    u["costo_usd"] = round(u.get("costo_usd", 0.0) + t_in / 1e6 * p_in + t_out / 1e6 * p_out, 4)
    _scrivi_uso(u)
    return risposta


def json_da(risposta):
    """Estrae il JSON dalla risposta (i modelli a volte aggiungono ``` o testo intorno)."""
    t = risposta.strip()
    if "```" in t:
        t = t.split("```")[1]
        if t.startswith("json"):
            t = t[4:]
    inizio = min([i for i in (t.find("{"), t.find("[")) if i >= 0] or [0])
    fine = max(t.rfind("}"), t.rfind("]"))
    return json.loads(t[inizio:fine + 1])
