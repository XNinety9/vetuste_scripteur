"""Ligne de commande : pour un humain, ou pour un autre programme avec `--json`."""

import argparse
import json
import os
import random
import sys

from . import NIVEAU_PAR_DEFAUT, NIVEAUX, __version__, enluminure, gravure, translate
from .enluminure import LARGEUR_MAX, LARGEUR_MIN, LARGEUR_PAR_DEFAUT

_EXEMPLES = (
    "Je mange une pomme dans le jardin",
    "Mon ami travaille beaucoup et ne dort pas assez",
    "Il ne buvait pas assez d'eau",
    "Tu regardais la télévision",
    "Madame, vous êtes très belle",
    "Je cherchais mon portable",
    "Nous courions vers la voiture",
    "Elle chantait une belle chanson",
)
_LARGEUR = 60


def _arguments(args: list[str] | None) -> argparse.Namespace:
    parseur = argparse.ArgumentParser(
        prog="vetuste-scripteur",
        description="Transforme le français moderne en vieux français façon Les Visiteurs.",
        epilog="Sans texte ni entrée standard, affiche quelques exemples.",
    )
    parseur.add_argument("texte", nargs="*", help="le texte à transformer ; « - » pour lire l'entrée standard")
    sortie = parseur.add_mutually_exclusive_group()
    sortie.add_argument("--json", action="store_true", help="sortie JSON, pour une intégration")
    sortie.add_argument("--svg", action="store_true", help="enluminure : une page de manuscrit au format SVG")
    sortie.add_argument(
        "--png", action="store_true",
        help="gravure : le texte seul, sans décor, en PNG noir et blanc (demande --largeur)",
    )
    parseur.add_argument(
        "--largeur", type=int, metavar="PIXELS",
        help=f"largeur de l'image, de {LARGEUR_MIN} à {LARGEUR_MAX} (avec --svg, {LARGEUR_PAR_DEFAUT} par défaut)",
    )
    parseur.add_argument("--seed", type=int, help="même texte + même seed + même niveau = même résultat")
    parseur.add_argument(
        "--niveau", type=int, choices=sorted(NIVEAUX), default=NIVEAU_PAR_DEFAUT,
        help="0 vocabulaire seul, 1 léger accent, 2 Les Visiteurs (défaut), 3 grimoire illisible",
    )
    parseur.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    options = parseur.parse_args(args)
    if options.png and options.largeur is None:
        parseur.error("--png demande --largeur")
    if options.largeur is not None and not LARGEUR_MIN <= options.largeur <= LARGEUR_MAX:
        parseur.error(f"--largeur : de {LARGEUR_MIN} à {LARGEUR_MAX}")
    return options


def _texte_demande(mots: list[str]) -> str | None:
    """Le texte à traiter, ou None s'il faut montrer les exemples."""
    if mots == ["-"] or (not mots and not sys.stdin.isatty()):
        return sys.stdin.read()
    return " ".join(mots) if mots else None


def main(args: list[str] | None = None) -> int:
    # Sur un Raspberry Pi ou sous systemd, la locale peut être « C » : le français doit passer.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

    if args is None:
        # En locale « C », Python décode mal les accents des arguments : on les relit en UTF-8.
        args = [os.fsencode(arg).decode("utf-8", "replace") for arg in sys.argv[1:]]
    options = _arguments(args)
    texte = _texte_demande(options.texte)

    if options.svg:
        if texte is None:
            print("vetuste-scripteur : --svg demande un texte", file=sys.stderr)
            return 2
        largeur = options.largeur if options.largeur is not None else LARGEUR_PAR_DEFAUT
        sys.stdout.write(enluminure(texte, seed=options.seed, level=options.niveau, largeur=largeur))
        return 0

    if options.png:
        if texte is None:
            print("vetuste-scripteur : --png demande un texte", file=sys.stderr)
            return 2
        if sys.stdout.isatty():
            print("vetuste-scripteur : --png écrit une image, redirige-la vers un fichier", file=sys.stderr)
            return 2
        sys.stdout.flush()
        sys.stdout.buffer.write(gravure(texte, largeur=options.largeur, seed=options.seed, level=options.niveau))
        return 0

    if options.json:
        seed = options.seed if options.seed is not None else random.randrange(2**32)
        original = texte if texte is not None else ""
        print(json.dumps({
            "original": original,
            "result": translate(original, seed=seed, level=options.niveau),
            "seed": seed,
            "level": options.niveau,
            "version": __version__,
        }, ensure_ascii=False))
        return 0

    if texte is not None:
        print(translate(texte, seed=options.seed, level=options.niveau))
        return 0

    print("\n" + "═" * _LARGEUR)
    print("Vetuste Scripteur".center(_LARGEUR))
    print("═" * _LARGEUR)
    for exemple in _EXEMPLES:
        print(f"\n  Moderne  : {exemple}")
        print(f"  Archaïque: {translate(exemple, seed=options.seed, level=options.niveau)}")
    print("\n" + "═" * _LARGEUR + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
