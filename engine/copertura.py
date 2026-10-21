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


ETICHETTE = {"italia": "Punto cieco italiano", "solo_italia": "Solo in Italia"}
