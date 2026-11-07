#!/usr/bin/env python3
"""Génère `vetuste_scripteur/glyphes.json` à partir de la fonte UnifrakturMaguntia.

Le fichier contient les tracés des lettres, leurs largeurs et les ligatures : de quoi écrire en
gothique dans un SVG, sans fonte installée et sans dépendance. fontTools n'est utile qu'ici.

    uv run scripts/generer_glyphes.py
"""

import json
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

RACINE = Path(__file__).resolve().parent.parent
FONTE = RACINE / "vetuste_scripteur" / "fonts" / "UnifrakturMaguntia-Book.ttf"
SORTIE = RACINE / "vetuste_scripteur" / "glyphes.json"
# Les ligatures qu'un moteur de texte applique par défaut. « hlig » (historiques) est facultative.
FONCTIONS_ACTIVES = ("rlig", "liga")


def _ligatures(fonte: TTFont) -> list[dict[str, list]]:
    """Les tables de ligatures actives, dans l'ordre où elles s'appliquent."""
    gsub = fonte["GSUB"].table
    indices = sorted({
        indice
        for fonction in gsub.FeatureList.FeatureRecord if fonction.FeatureTag in FONCTIONS_ACTIVES
        for indice in fonction.Feature.LookupListIndex
    })
    tables = []
    for indice in indices:
        recherche = gsub.LookupList.Lookup[indice]
        table: dict[str, list] = {}
        for sous_table in recherche.SubTable:
            if recherche.LookupType != 4:
                raise SystemExit(f"Type de substitution non géré : {recherche.LookupType}")
            for premier, ligatures in sous_table.ligatures.items():
                table.setdefault(premier, []).extend([l.Component, l.LigGlyph] for l in ligatures)
        tables.append(table)
    return tables


def main() -> None:
    fonte = TTFont(FONTE)
    if fonte["GPOS"].table.FeatureList and fonte["GPOS"].table.FeatureList.FeatureRecord:
        raise SystemExit("Cette fonte a du crénage : le moteur de scripts/… ne le gère pas.")
    jeu = fonte.getGlyphSet()
    glyphes = {}
    for nom in fonte.getGlyphOrder():
        trace = SVGPathPen(jeu, ntos=lambda v: str(round(v)))
        # L'axe vertical d'une fonte monte, celui d'un SVG descend.
        jeu[nom].draw(TransformPen(trace, (1, 0, 0, -1, 0, 0)))
        bornes = BoundsPen(jeu)
        jeu[nom].draw(TransformPen(bornes, (1, 0, 0, -1, 0, 0)))
        glyphes[nom] = {"a": fonte["hmtx"][nom][0], "d": trace.getCommands()}
        if bornes.bounds:
            glyphes[nom]["b"] = [round(v) for v in bornes.bounds]
    donnees = {
        "unites": fonte["head"].unitsPerEm,
        "caracteres": {chr(code): nom for code, nom in sorted(fonte.getBestCmap().items())},
        "ligatures": _ligatures(fonte),
        "glyphes": glyphes,
    }
    SORTIE.write_text(json.dumps(donnees, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(glyphes)} glyphes écrits dans {SORTIE.relative_to(RACINE)} ({SORTIE.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    main()
