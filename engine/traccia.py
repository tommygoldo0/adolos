"""
ADOLOS – traccia locale di quello che è stato pubblicato
========================================================
Copia in una cartella del computer (di norma "Adolos" sulla Scrivania) tutto ciò che è andato sul sito:
per ogni notizia una cartellina con la scheda (titolo, sintesi, fonti con i link) e le slide del carosello
in qualità bassa, più un registro unico "registro.csv". Serve solo come archivio: non pubblica niente.

    python3 engine/traccia.py                    salva in ~/Desktop/Adolos
    python3 engine/traccia.py /percorso/cartella salva altrove

Prima aggiorna la copia locale del progetto (git pull), poi legge site/data/archivio.json e notizie.json.
Quello che è già stato salvato non viene toccato: le notizie tolte dal sito restano nella traccia.
"""

import csv
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
DATI = RADICE / "site" / "data"
LATO, QUALITA = 432, 30            # slide rimpicciolite a 432x540, JPEG molto compresso (circa 15-25 KB l'una)
SITO = "https://tommygoldo0.github.io/adolos"


def _leggi(percorso, default):
    try:
        return json.loads(percorso.read_text(encoding="utf-8"))
    except Exception:
        return default


def _nome_cartella(s):
    t = unicodedata.normalize("NFKD", s.get("titolo", "")).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()[:60]
    data = ((s.get("prima_segnalazione") or {}).get("data") or s.get("aggiornata") or "")[:10] or "senza-data"
    return f"{data} {t or s['id']} [{s['id']}]"


def _scheda(s):
    sint = s.get("sintesi") or {}
    righe = [s.get("titolo", ""), "=" * 60, "",
             f"ID: {s['id']}    Sezione: {s.get('sezione', '')}    Aggiornata: {s.get('aggiornata', '')[:16]}",
             f"Sul sito: {SITO}/storie/{s['id']}.html", "",
             sint.get("sintesi", "(nessuna sintesi)"), ""]
    if sint.get("punti"):
        righe += ["Punti del carosello:"] + [f"  - {p}" for p in sint["punti"]] + [""]
    if (s.get("immagine") or {}).get("credito"):
        righe += ["Foto di copertina: " + s["immagine"]["credito"], ""]
    righe.append(f"Fonti ({s.get('n_fonti', len(s.get('fonti', [])))} testate):")
    for f in s.get("fonti", []):
        righe.append(f"  - {f.get('fonte', '')} ({f.get('paese', '')}) {str(f.get('data', ''))[:10]} {f.get('link', '')}")
    righe += ["", "Testo preparato con l'aiuto dell'AI e verificato dalla redazione."]
    return "\n".join(righe) + "\n"


def salva(cartella):
    cartella = Path(cartella).expanduser()
    cartella.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(["git", "-C", str(RADICE), "pull", "-q", "--rebase"], capture_output=True, text=True, timeout=120)
        if r.returncode:
            print("ATTENZIONE: copia locale non aggiornata (git pull):", r.stderr.strip()[:160])
    except Exception as e:
        print("ATTENZIONE: copia locale non aggiornata (git pull):", str(e)[:160])
    storie = dict(_leggi(DATI / "archivio.json", {}))
    for s in _leggi(DATI / "notizie.json", {}).get("storie", []):
        if s.get("pubblicata"):
            storie[s["id"]] = s
    registro = cartella / "registro.csv"
    gia = set()
    if registro.exists():
        with registro.open(encoding="utf-8", newline="") as f:
            gia = {r["id"] for r in csv.DictReader(f, delimiter=";")}
    nuove = 0
    with registro.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        if not gia:
            w.writerow(["id", "data", "sezione", "titolo", "testate", "paesi", "slide", "link_sito", "cartella"])
        for sid, s in sorted(storie.items(), key=lambda kv: kv[1].get("aggiornata", "")):
            if sid in gia:
                continue
            dove = cartella / _nome_cartella(s)
            dove.mkdir(exist_ok=True)
            (dove / "scheda.txt").write_text(_scheda(s), encoding="utf-8")
            n_slide = 0
            for i, rel in enumerate(s.get("carosello") or [], 1):
                try:
                    from PIL import Image
                    img = Image.open(RADICE / "site" / rel).convert("RGB")
                    img.thumbnail((LATO, LATO * 2))
                    img.save(dove / f"slide-{i}.jpg", "JPEG", quality=QUALITA, optimize=True)
                    n_slide += 1
                except Exception as e:
                    print(f"Slide non salvata ({sid}, {rel}):", str(e)[:100])
            w.writerow([sid, (s.get("aggiornata") or "")[:10], s.get("sezione", ""), s.get("titolo", ""),
                        s.get("n_fonti", ""), " ".join(s.get("paesi", [])), n_slide, f"{SITO}/storie/{sid}.html", dove.name])
            nuove += 1
    print(f"Traccia in {cartella}: {nuove} notizie nuove salvate, {len(gia)} già presenti, {len(storie)} pubblicate in tutto")
    return nuove


if __name__ == "__main__":
    salva(sys.argv[1] if len(sys.argv) > 1 else "~/Desktop/Adolos")
