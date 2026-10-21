"""
ADOLOS – voce AI per video e audio (Gemini TTS, API ufficiale a pagamento)
=========================================================================
Legge un copione e crea un file WAV (24 kHz, mono) da mettere nei video Hyperframes, Reel e TikTok.

Regole (vedi skill adolos-controllo-legale):
  - SEMPRE l'etichetta "Voce generata con AI": nel video (testo a schermo) e nella didascalia;
  - solo voci predefinite di Google. La replica di una voce si usa SOLO per un membro della redazione
    che dà il consenso scritto (e quello audio richiesto da Google). Mai voci di persone famose o terze;
  - niente dati personali nei copioni oltre a quelli già pubblici nella notizia.

Costi: nello Spazio Economico Europeo Google permette solo i servizi a pagamento per app e siti.
Con gemini-3.8-flash-tts (prezzi fino al 31/12/2026) un video di 30 secondi costa meno di 1 centesimo.
C'è un tetto di spesa mensile in fonti.json > "voce" > "budget_mensile_usd".

Chiave: variabile d'ambiente GEMINI_API_KEY (mai nel codice o nei file del repository).

Uso:
  python3 engine/voce.py video/<id>/copione.txt                     -> video/<id>/voce.wav
  python3 engine/voce.py copione.txt --voce Kore --stile "calm, warm" --out prova.wav
  python3 engine/voce.py --prova                                     -> controlla solo la configurazione
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
USO = ENGINE / "cache" / "uso_voce.json"
URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
PREDEFINITO = {
    "attiva": True,
    "modello": "gemini-3.8-flash-tts",
    "voce": "Charon",
    "stile": "Italian news presenter: clear, calm and neutral, steady brisk pace, no drama",
    "budget_mensile_usd": 3.0,
    "costo_per_10_secondi_usd": 0.00225,
    "max_caratteri": 1500,
}
ETICHETTA = "Voce generata con AI"


class TettoRaggiunto(Exception):
    pass


def conf():
    try:
        c = json.loads((ENGINE / "fonti.json").read_text(encoding="utf-8")).get("voce", {})
    except Exception:
        c = {}
    return {**PREDEFINITO, **{k: v for k, v in c.items() if not k.startswith("_")}}


def _chiave():
    """La voce usa GEMINI_API_KEY; se non c'è, la stessa chiave dei testi (AI_KEY) quando l'AI è Gemini."""
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if k:
        return k
    try:
        prov = (os.environ.get("AI_PROVIDER") or json.loads((ENGINE / "fonti.json").read_text(encoding="utf-8"))
                .get("ai", {}).get("provider", "")).strip().lower()
    except Exception:
        prov = ""
    return os.environ.get("AI_KEY", "").strip() if prov == "gemini" else ""


def _uso():
    mese = datetime.now(timezone.utc).strftime("%Y-%m")
    try:
        u = json.loads(USO.read_text(encoding="utf-8"))
    except Exception:
        u = {}
    if u.get("mese") != mese:
        u = {"mese": mese, "secondi": 0.0, "costo_usd": 0.0, "file": 0}
    return u


def _durata_wav(dati):
    """Secondi di un WAV PCM 16 bit (legge l'intestazione RIFF)."""
    import io
    import wave
    with wave.open(io.BytesIO(dati)) as w:
        return w.getnframes() / float(w.getframerate())


def leggi(testo, voce=None, stile=None, modello=None):
    """Restituisce i byte di un file WAV. Solleva TettoRaggiunto se il budget del mese è finito."""
    import requests
    c = conf()
    if not c["attiva"]:
        raise RuntimeError("voce spenta in fonti.json > voce > attiva")
    chiave = _chiave()
    if not chiave:
        raise RuntimeError("manca la chiave: GEMINI_API_KEY, oppure AI_KEY con l'AI impostata su Gemini")
    testo = (testo or "").strip()
    if not testo:
        raise ValueError("copione vuoto")
    if len(testo) > c["max_caratteri"]:
        raise ValueError(f"copione troppo lungo ({len(testo)} caratteri, massimo {c['max_caratteri']}): dividilo")
    u = _uso()
    if u["costo_usd"] >= float(c["budget_mensile_usd"]):
        raise TettoRaggiunto(f"tetto voce del mese raggiunto ({u['costo_usd']:.2f} $)")
    corpo = {
        "model": modello or c["modello"],
        "input": [{"type": "user_input", "content": [{
            "type": "text", "text": testo,
            "annotations": [{"type": "speech_metadata", "style": stile or c["stile"]}]}]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voce or c["voce"]}]},
    }
    r = requests.post(URL, json=corpo, timeout=120,
                      headers={"x-goog-api-key": chiave, "Content-Type": "application/json"})
    if r.status_code >= 300:
        raise RuntimeError(f"Gemini TTS {r.status_code}: {r.text[:300]}")
    audio = [x for st in r.json().get("steps", []) if st.get("type") == "model_output"
             for x in st.get("content", []) if x.get("type") == "audio"]
    if not audio:
        raise RuntimeError("risposta senza audio")
    dati = base64.b64decode(audio[-1]["data"])
    if dati[:4] != b"RIFF":
        raise RuntimeError("l'audio ricevuto non è un WAV: controlla il formato nella documentazione")
    secondi = _durata_wav(dati)
    u["secondi"] += secondi
    u["costo_usd"] += secondi / 10 * float(c["costo_per_10_secondi_usd"])
    u["file"] += 1
    USO.parent.mkdir(parents=True, exist_ok=True)
    USO.write_text(json.dumps(u), encoding="utf-8")
    return dati, secondi


def main(argv=None):
    p = argparse.ArgumentParser(description="Voce AI di Adolos (Gemini TTS)")
    p.add_argument("copione", nargs="?", help="file di testo con il copione (solo le parole da leggere)")
    p.add_argument("--out", help="file WAV di uscita (predefinito: voce.wav accanto al copione)")
    p.add_argument("--voce", help="voce predefinita di Google (es. Charon, Kore, Aoede)")
    p.add_argument("--stile", help="stile in linguaggio naturale, in inglese")
    p.add_argument("--prova", action="store_true", help="controlla solo la configurazione")
    a = p.parse_args(argv)
    c = conf()
    if a.prova or not a.copione:
        u = _uso()
        print(f"Voce: {'attiva' if c['attiva'] else 'spenta'} · modello {c['modello']} · voce {c['voce']}")
        print(f"Chiave: {'presente' if _chiave() else 'MANCA (GEMINI_API_KEY o AI_KEY con Gemini)'}")
        print(f"Questo mese: {u['file']} file, {u['secondi']:.0f} s, {u['costo_usd']:.3f} $ su {c['budget_mensile_usd']} $")
        return 0
    sorgente = Path(a.copione)
    uscita = Path(a.out) if a.out else sorgente.with_name("voce.wav")
    try:
        dati, secondi = leggi(sorgente.read_text(encoding="utf-8"), a.voce, a.stile)
    except Exception as e:
        print("Voce non creata:", e, file=sys.stderr)
        return 1
    uscita.write_bytes(dati)
    (uscita.with_suffix(".txt")).write_text(
        f"{ETICHETTA} ({c['modello']}, voce {a.voce or c['voce']}), {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.\n"
        "Mostrare l'etichetta nel video e nella didascalia.\n", encoding="utf-8")
    print(f"Creato {uscita} ({secondi:.1f} s). Ricorda l'etichetta: \"{ETICHETTA}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
