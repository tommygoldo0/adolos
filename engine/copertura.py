"""
ADOLOS – chi ne parla e il "punto cieco" (idea presa da Ground News, adattata all'Italia)
=========================================================================================
Ground News confronta destra e sinistra negli Stati Uniti. Noi confrontiamo l'Italia con il
resto del mondo, con numeri che chiunque può controllare (niente etichette politiche date da noi):

  - copertura per continente: quante testate ne parlano in Europa, Americhe, Asia, Africa, Oceania;
  - Italia contro estero: quante testate italiane e quante straniere;
  - punto cieco:
      "italia"      = il mondo ne parla, in Italia (quasi) nessuno  -> "Il mondo ne parla, l'Italia no"
      "solo_italia" = se ne parla solo in Italia                    -> "Se ne parla solo da noi"
"""

from collections import Counter

# soglie (si possono cambiare in fonti.json > "punto_cieco")
PREDEFINITO = {"min_estero": 5, "min_paesi_esteri": 3, "max_italia": 0, "min_italia_solo": 3}


def _cont_di():
    from sito import CONT_DI
    return CONT_DI


def calcola(gruppo, conf=None):
    """Conta le testate (una volta sola per nome) per paese e continente."""
    c = {**PREDEFINITO, **(conf or {})}
    cont_di = _cont_di()
    viste, per_paese = set(), Counter()
    for x in gruppo:
        if x.get("tipo") == "social" or x.get("correlato"):
            continue
        k = x["fonte"].lower()
        if k in viste:
            continue
        viste.add(k)
        per_paese[x.get("paese") or "?"] += 1
    italia = per_paese.get("IT", 0)
    estero = sum(n for p, n in per_paese.items() if p != "IT")
    paesi_esteri = sum(1 for p in per_paese if p not in ("IT", "?", "WEB"))
    continenti = Counter()
    for p, n in per_paese.items():
        continenti[cont_di.get(p, "Altro")] += n
    if estero >= c["min_estero"] and paesi_esteri >= c["min_paesi_esteri"] and italia <= c["max_italia"]:
        cieco = "italia"
    elif italia >= c["min_italia_solo"] and estero == 0:
        cieco = "solo_italia"
    else:
        cieco = ""
    return {"italia": italia, "estero": estero, "paesi_esteri": paesi_esteri,
            "continenti": dict(continenti.most_common())}, cieco


_PROPRIETA = None


def proprieta(gruppo):
    """Chi possiede le testate che ne parlano (dati di engine/proprieta.json). Serve alla redazione: molte testate
    dello stesso gruppo editoriale non sono voci indipendenti. Dato interno: non va sul sito finché non è verificato."""
    global _PROPRIETA
    if _PROPRIETA is None:
        import json
        from pathlib import Path
        try:
            dati = json.loads((Path(__file__).resolve().parent / "proprieta.json").read_text(encoding="utf-8"))
            _PROPRIETA = {k.lower(): v for k, v in dati.get("testate", {}).items()}
        except Exception as e:
            print("Proprietà delle testate non lette:", e)
            _PROPRIETA = {}
    viste, tipi, gruppi = set(), Counter(), Counter()
    for x in gruppo:
        if x.get("tipo") == "social" or x.get("correlato"):
            continue
        k = x["fonte"].lower()
        if k in viste:
            continue
        viste.add(k)
        p = _PROPRIETA.get(k)
        tipi[p["tipo"] if p else "non nota"] += 1
        gruppi[p["gruppo"] if p else "?" + k] += 1          # testata senza dato: conta come gruppo a sé
    return {"tipi": dict(tipi.most_common()), "gruppi_diversi": len(gruppi),
            "stesso_gruppo": [[g, n] for g, n in gruppi.most_common() if n > 1 and not g.startswith("?")]}


def riga_proprieta(p):
    """Una riga leggibile per Telegram e Notion, es. '5 private, 2 pubbliche · 6 gruppi editoriali diversi (BBC ×2)'."""
    if not p or not p.get("tipi"):
        return ""
    nomi = {"privata": ("privata", "private"), "pubblica": ("pubblica", "pubbliche"), "no profit": ("no profit", "no profit"),
            "non nota": ("non nota", "non note")}
    parti = [f"{n} {nomi.get(t, (t, t))[n > 1]}" for t, n in p["tipi"].items()]
    riga = ", ".join(parti) + f" · {p['gruppi_diversi']} " + ("gruppi editoriali diversi" if p["gruppi_diversi"] != 1 else "gruppo editoriale")
    if p.get("stesso_gruppo"):
        riga += " (" + ", ".join(f"{g} ×{n}" for g, n in p["stesso_gruppo"][:3]) + ")"
    return riga


ETICHETTE = {"italia": "Punto cieco italiano", "solo_italia": "Solo in Italia"}
