"""Les façons d'utiliser le composant : CLI, archive .pyz sans dépendance, API web."""

import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

import vetuste_scripteur

RACINE = Path(__file__).resolve().parent.parent


def cli(*args: str, entree: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "vetuste_scripteur", *args],
        input=entree, capture_output=True, text=True, encoding="utf-8", cwd=RACINE, check=True,
    )


def test_cli_phrase():
    assert cli("--niveau", "0", "--seed", "1", "Je", "chante").stdout == "J'entonnoy\n"


def test_cli_entree_standard():
    assert cli("--niveau", "0", "--seed", "1", "-", entree="Je chante\n").stdout == "J'entonnoy\n"
    assert cli("--niveau", "0", "--seed", "1", entree="Je chante").stdout == "J'entonnoy\n"


def test_cli_json():
    donnees = json.loads(cli("--json", "--seed", "7", "--niveau", "1", "Je chante").stdout)
    assert donnees["original"] == "Je chante"
    assert donnees["seed"] == 7
    assert donnees["level"] == 1
    assert donnees["version"] == vetuste_scripteur.__version__
    assert donnees["result"] == vetuste_scripteur.translate("Je chante", seed=7, level=1)


def test_cli_json_seed_rejouable():
    premiere = json.loads(cli("--json", "Madame, vous êtes très belle").stdout)
    rejouee = cli("--json", "--seed", str(premiere["seed"]), "Madame, vous êtes très belle").stdout
    assert json.loads(rejouee)["result"] == premiere["result"]


def test_cli_locale_c():
    # Le cas de systemd sur un Raspberry Pi : les accents doivent passer quand même.
    sortie = subprocess.run(
        [sys.executable, "-m", "vetuste_scripteur", "--json", "--seed", "1", "--niveau", "0", "Il a été là"],
        capture_output=True, cwd=RACINE, check=True, env={"LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"},
    ).stdout
    assert json.loads(sortie.decode("utf-8"))["result"] == "Il a esté là"


def test_cli_niveau_invalide():
    resultat = subprocess.run([sys.executable, "-m", "vetuste_scripteur", "--niveau", "9", "x"],
                              capture_output=True, cwd=RACINE)
    assert resultat.returncode == 2


def test_import_sans_dependance():
    # -I : sans le dossier courant ni les paquets installés, seulement la bibliothèque standard.
    code = (
        f"import sys; sys.path.insert(0, {str(RACINE)!r}); import vetuste_scripteur as v;"
        "print(v.translate('Je chante', seed=1, level=0));"
        "print(sorted(m for m in sys.modules if m.split('.')[0] in ('spacy', 'verbecc', 'fastapi')))"
    )
    sortie = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, encoding="utf-8", check=True)
    assert sortie.stdout.splitlines() == ["J'entonnoy", "[]"]


def test_archive_pyz(tmp_path):
    construction = subprocess.run([sys.executable, str(RACINE / "scripts" / "construire_pyz.py")],
                                  capture_output=True, text=True, encoding="utf-8", check=True)
    assert "dist/vetuste-scripteur.pyz" in construction.stdout
    archive = tmp_path / "v.pyz"
    archive.write_bytes((RACINE / "dist" / "vetuste-scripteur.pyz").read_bytes())
    sortie = subprocess.run(
        [sys.executable, "-I", str(archive), "--json", "--seed", "1", "--niveau", "0", "Je chante"],
        capture_output=True, text=True, encoding="utf-8", check=True, cwd=tmp_path,
    )
    assert json.loads(sortie.stdout)["result"] == "J'entonnoy"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from vetuste_scripteur.web import app

    return TestClient(app)


def test_web_page(client):
    reponse = client.get("/")
    assert reponse.status_code == 200
    assert "Vetuste Scripteur" in reponse.text
    assert vetuste_scripteur.__version__ in reponse.text
    assert "%%" not in reponse.text
    assert 'id="illuminate"' in reponse.text
    assert 'id="illumination"' in reponse.text


def test_web_sans_ressource_externe(client):
    page = client.get("/").text
    # Seule URL tolérée : l'espace de noms SVG, qui n'est jamais téléchargé.
    assert set(re.findall(r"https?://[^\s\"')]+", page.replace("%3A", ":"))) <= {"http://www.w3.org/2000/svg"}
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


@pytest.mark.parametrize(
    "fonte",
    ["UnifrakturMaguntia-Book", "CrimsonText-Regular", "CrimsonText-Italic", "CrimsonText-SemiBold"],
)
def test_web_fontes_servies(client, fonte):
    reponse = client.get(f"/fonts/{fonte}.ttf")
    assert reponse.status_code == 200
    assert reponse.content[:4] == b"\x00\x01\x00\x00"  # l'en-tête d'une fonte TrueType
    assert f"/fonts/{fonte}.ttf" in client.get("/").text


def test_licences_des_fontes_presentes():
    fontes = RACINE / "vetuste_scripteur" / "fonts"
    for licence in ("OFL-UnifrakturMaguntia.txt", "OFL-CrimsonText.txt"):
        assert "SIL Open Font License" in (fontes / licence).read_text(encoding="utf-8")


def test_web_translate(client):
    donnees = client.get("/translate", params={"phrase": "Je chante", "seed": 3, "level": 0}).json()
    assert donnees == {"original": "Je chante", "result": "J'entonnoy", "seed": 3, "level": 0}


def test_web_seed_rendue_et_rejouable(client):
    premiere = client.get("/translate", params={"phrase": "Madame, vous êtes très belle"}).json()
    rejouee = client.get("/translate", params={"phrase": "Madame, vous êtes très belle", "seed": premiere["seed"]}).json()
    assert rejouee["result"] == premiere["result"]


@pytest.mark.parametrize("phrase", ["", "   "])
def test_web_texte_vide(client, phrase):
    for seed in range(20):
        reponse = client.get("/translate", params={"phrase": phrase, "seed": seed})
        assert reponse.status_code == 200
        assert reponse.json()["result"] == ""


@pytest.mark.parametrize(
    "params",
    [
        {"phrase": "x" * 5001},
        {"phrase": "x", "level": 9},
        {"phrase": "x", "level": -1},
        {"phrase": "x", "seed": -1},
        {"phrase": "x", "seed": 2**60},
        {},
    ],
)
def test_web_requetes_refusees(client, params):
    assert client.get("/translate", params=params).status_code == 422


def test_version_unique():
    import tomllib

    projet = tomllib.loads((RACINE / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert projet["version"] == vetuste_scripteur.__version__


def test_archive_reproductible_et_complete(tmp_path):
    construire = [sys.executable, str(RACINE / "scripts" / "construire_pyz.py")]
    subprocess.run(construire, capture_output=True, check=True)
    sortie = RACINE / "dist"
    premiere = (sortie / "vetuste-scripteur.pyz").read_bytes()
    # Toucher un fichier source ne doit pas changer l'archive : seul le contenu compte.
    source = RACINE / "vetuste_scripteur" / "__main__.py"
    dates = source.stat()
    os.utime(source, (dates.st_atime + 1000, dates.st_mtime + 1000))
    try:
        subprocess.run(construire, capture_output=True, check=True)
    finally:
        os.utime(source, (dates.st_atime, dates.st_mtime))
    assert (sortie / "vetuste-scripteur.pyz").read_bytes() == premiere

    somme = (sortie / "vetuste-scripteur.pyz.sha256").read_text(encoding="utf-8").split()
    assert somme == [hashlib.sha256(premiere).hexdigest(), "vetuste-scripteur.pyz"]

    with zipfile.ZipFile(sortie / "vetuste-scripteur.pyz") as archive:
        noms = archive.namelist()
    for present in ("vetuste_scripteur/NOTICE", "vetuste_scripteur/LICENSE", "vetuste_scripteur/verbes.json", "vetuste_scripteur/glyphes.json",
                    "vetuste_scripteur/fonts/OFL-UnifrakturMaguntia.txt"):
        assert present in noms


def test_contrat_de_la_cli_pour_printr(tmp_path):
    # Les options exactes du module Rust : les changer casserait Printr.
    sortie = subprocess.run(
        [sys.executable, "-m", "vetuste_scripteur", "--png", "--largeur=512", "--seed=42", "--niveau=2", "--",
         "--texte qui ressemble à une option"],
        capture_output=True, cwd=RACINE, check=True, stdin=subprocess.DEVNULL,
    )
    assert sortie.stdout.startswith(b"\x89PNG")
    assert sortie.stderr == b""
