#!/usr/bin/env python3
"""Construit `dist/vetuste-scripteur.pyz` : tout le moteur et sa CLI dans un seul fichier.

Il suffit de Python 3.11 ou plus pour l'exécuter, sans rien installer :

    python3 vetuste-scripteur.pyz --json "Je mange une pomme"
"""

import hashlib
import os
import shutil
import tempfile
import zipapp
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DATE_FIXE = 1577836800  # 2020-01-01
SORTIE = RACINE / "dist" / "vetuste-scripteur.pyz"
# La page web demande FastAPI : ni elle ni ses fontes n'ont leur place dans l'archive sans dépendance.
# Reste la licence d'UnifrakturMaguntia, qui doit accompagner les tracés de glyphes.json.
EXCLUS = shutil.ignore_patterns("__pycache__", "web.py", "page.html", "*.ttf", "OFL-CrimsonText.txt")


def main() -> None:
    with tempfile.TemporaryDirectory() as dossier:
        racine = Path(dossier)
        shutil.copytree(RACINE / "vetuste_scripteur", racine / "vetuste_scripteur", ignore=EXCLUS)
        # La licence et le NOTICE accompagnent l'archive, comme l'exige la licence Apache.
        for fichier in ("LICENSE", "NOTICE"):
            shutil.copy(RACINE / fichier, racine / "vetuste_scripteur" / fichier)
        # Une date et des droits fixes : le même code donne la même archive, sur n'importe quel clone.
        for chemin in racine.rglob("*"):
            chemin.chmod(0o755 if chemin.is_dir() else 0o644)
            os.utime(chemin, (DATE_FIXE, DATE_FIXE))
        SORTIE.parent.mkdir(exist_ok=True)
        zipapp.create_archive(racine, SORTIE, interpreter="/usr/bin/env python3",
                              main="vetuste_scripteur.cli:main", compressed=True)
    somme = hashlib.sha256(SORTIE.read_bytes()).hexdigest()
    SORTIE.with_name(SORTIE.name + ".sha256").write_text(f"{somme}  {SORTIE.name}\n", encoding="utf-8")
    print(f"{SORTIE.relative_to(RACINE)} ({SORTIE.stat().st_size // 1024} Ko)  sha256 {somme}")


if __name__ == "__main__":
    main()
