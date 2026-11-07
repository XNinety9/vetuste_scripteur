#!/usr/bin/env python3
"""Construit `dist/vetuste-scripteur.pyz` : tout le moteur et sa CLI dans un seul fichier.

Il suffit de Python 3.11 ou plus pour l'exécuter, sans rien installer :

    python3 vetuste-scripteur.pyz --json "Je mange une pomme"

L'archive ne dépend ni de l'heure, ni du fuseau horaire, ni des dates des fichiers : le même code
donne le même fichier avec la même version de Python. D'une version de zlib à l'autre, la
compression peut varier : la somme de contrôle qui fait foi est celle publiée avec la release.
"""

import hashlib
import shutil
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "dist" / "vetuste-scripteur.pyz"
DATE_FIXE = (2020, 1, 1, 0, 0, 0)
# La page web demande FastAPI : ni elle ni ses fontes n'ont leur place dans l'archive sans dépendance.
# Reste la licence d'UnifrakturMaguntia, qui doit accompagner les tracés de glyphes.json.
EXCLUS = ("__pycache__", "web.py", "page.html", "*.ttf", "OFL-CrimsonText.txt")
# La licence et le NOTICE accompagnent l'archive, comme l'exige la licence Apache.
EN_PLUS = ("LICENSE", "NOTICE")
LANCEUR = b"# -*- coding: utf-8 -*-\nimport vetuste_scripteur.cli\nvetuste_scripteur.cli.main()\n"


def _fichiers() -> dict[str, bytes]:
    """Le contenu de l'archive, par nom, sans rien qui dépende de la machine."""
    paquet = RACINE / "vetuste_scripteur"
    fichiers = {"__main__.py": LANCEUR}
    for chemin in sorted(paquet.rglob("*")):
        relatif = chemin.relative_to(paquet)
        if chemin.is_file() and not any(relatif.match(m) or m in relatif.parts for m in EXCLUS):
            fichiers[f"vetuste_scripteur/{relatif.as_posix()}"] = chemin.read_bytes()
    for nom in EN_PLUS:
        fichiers[f"vetuste_scripteur/{nom}"] = (RACINE / nom).read_bytes()
    return dict(sorted(fichiers.items()))


def main() -> None:
    SORTIE.parent.mkdir(exist_ok=True)
    with SORTIE.open("wb") as sortie:
        sortie.write(b"#!/usr/bin/env python3\n")
        with zipfile.ZipFile(sortie, "w") as archive:
            for nom, contenu in _fichiers().items():
                entree = zipfile.ZipInfo(nom, date_time=DATE_FIXE)
                entree.external_attr = 0o100644 << 16
                entree.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entree, contenu, compresslevel=9)
    SORTIE.chmod(0o755)
    somme = hashlib.sha256(SORTIE.read_bytes()).hexdigest()
    SORTIE.with_name(SORTIE.name + ".sha256").write_text(f"{somme}  {SORTIE.name}\n", encoding="utf-8")
    print(f"{SORTIE.relative_to(RACINE)} ({SORTIE.stat().st_size // 1024} Ko)  sha256 {somme}")


if __name__ == "__main__":
    main()
