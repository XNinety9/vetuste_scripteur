"""Conjugaisons pré-générées : d'une forme vers son analyse, et d'une analyse vers une forme.

Les codes de temps sont ceux de `verbes.json` :
    ip présent, ii imparfait, if futur, is passé simple, cp conditionnel, sp subjonctif présent,
    si subjonctif imparfait, im impératif, pp participe passé, pr participe présent, inf infinitif.

Le rang va de 0 à 5 (je, tu, il, nous, vous, ils). Pour le participe passé, il va de 0 à 3
(masculin, masculin pluriel, féminin, féminin pluriel).
"""

import json
from functools import lru_cache
from importlib import resources
from typing import NamedTuple

# Ordre de préférence quand une forme a plusieurs analyses : « finit » est un présent avant
# d'être un passé simple, « aime » un indicatif avant d'être un subjonctif.
_TEMPS_FINIS = ("ip", "ii", "if", "cp", "is", "sp", "si")
_RANGS_IMPERATIF = (1, 3, 4)

# En cas d'homographes, ces verbes passent en premier : « suis » est le verbe être avant d'être
# suivre, « vis » le verbe voir ou vivre, « été » le verbe être.
_VERBES_PRIORITAIRES = ("être", "avoir", "aller", "faire", "dire", "voir", "pouvoir", "vouloir")


class Analyse(NamedTuple):
    verbe: str
    temps: str
    rang: int


@lru_cache(maxsize=1)
def table() -> dict:
    """La table des conjugaisons, lue une seule fois. Fonctionne aussi depuis une archive .pyz."""
    fichier = resources.files(__package__).joinpath("verbes.json")
    return json.loads(fichier.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def formes() -> dict[str, tuple[Analyse, ...]]:
    """L'index inverse : pour chaque forme, ses analyses possibles, de la plus probable à la moins."""
    verbes = table()
    ordre = [*_VERBES_PRIORITAIRES, *(v for v in verbes if v not in _VERBES_PRIORITAIRES)]
    index: dict[str, list[Analyse]] = {}

    def noter(forme: str | None, analyse: Analyse) -> None:
        if forme:
            index.setdefault(forme, []).append(analyse)

    for verbe in ordre:
        conj = verbes[verbe]
        for temps in _TEMPS_FINIS:
            for rang, forme in enumerate(conj[temps]):
                noter(forme, Analyse(verbe, temps, rang))
        for rang, forme in zip(_RANGS_IMPERATIF, conj["im"]):
            noter(forme, Analyse(verbe, "im", rang))
        for rang, forme in enumerate(conj["pp"]):
            noter(forme, Analyse(verbe, "pp", rang))
        noter(conj["pr"], Analyse(verbe, "pr", 0))
        noter(verbe, Analyse(verbe, "inf", 0))
    return {forme: tuple(analyses) for forme, analyses in index.items()}


def conjuguer(verbe: str, temps: str, rang: int) -> str | None:
    """La forme demandée, ou None si le verbe ne l'a pas (« choir » n'a pas d'imparfait)."""
    conj = table().get(verbe)
    if conj is None:
        return None
    if temps == "inf":
        return verbe
    if temps == "pr":
        return conj["pr"]
    if temps == "im":
        return conj["im"][_RANGS_IMPERATIF.index(rang)]
    return conj[temps][rang]
