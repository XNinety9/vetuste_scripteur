"""La gravure : un PNG 1 bit de la largeur demandée, net, sans décor, et lisible par de vrais outils."""

import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

from vetuste_scripteur import gravure, translate
from vetuste_scripteur.gravure import HAUTEUR_MAX, graver

RACINE = Path(__file__).resolve().parent.parent
PHRASE = "Madame, vous êtes très belle. Je cherchais mon portable dans la voiture !"


def lire_png(donnees: bytes) -> tuple[int, int, int, int, list[bytes]]:
    """Largeur, hauteur, profondeur, type de couleur et lignes d'un PNG simple."""
    assert donnees[:8] == b"\x89PNG\r\n\x1a\n"
    position = 8
    idat = b""
    while position < len(donnees):
        taille, nom = struct.unpack(">I4s", donnees[position:position + 8])
        contenu = donnees[position + 8:position + 8 + taille]
        controle = struct.unpack(">I", donnees[position + 8 + taille:position + 12 + taille])[0]
        assert controle == zlib.crc32(nom + contenu)
        if nom == b"IHDR":
            largeur, hauteur, profondeur, couleur = struct.unpack(">IIBB", contenu[:10])
        elif nom == b"IDAT":
            idat += contenu
        position += 12 + taille
    brut = zlib.decompress(idat)
    pas = (largeur + 7) // 8 + 1
    assert len(brut) == pas * hauteur
    return largeur, hauteur, profondeur, couleur, [brut[i + 1:i + pas] for i in range(0, len(brut), pas)]


def encre(lignes: list[bytes], largeur: int) -> int:
    """Le nombre de pixels noirs, sans compter le bourrage des fins de ligne."""
    return sum(largeur - bin(int.from_bytes(l, "big") >> (len(l) * 8 - largeur)).count("1") for l in lignes)


@pytest.mark.parametrize("largeur", [200, 384, 512, 513, 576, 1000])
def test_largeur_exacte_et_noir_et_blanc(largeur):
    l, h, profondeur, couleur, lignes = lire_png(graver(PHRASE, largeur=largeur))
    assert l == largeur
    assert (profondeur, couleur) == (1, 0)  # 1 bit, niveaux de gris : aucune nuance possible
    assert encre(lignes, largeur) > 0
    assert h > 0


def test_largeur_obligatoire():
    with pytest.raises(TypeError):
        gravure(PHRASE)


@pytest.mark.parametrize("largeur", [100, 9000])
def test_largeur_refusee(largeur):
    with pytest.raises(ValueError, match="largeur"):
        graver(PHRASE, largeur=largeur)


def test_reproductible_et_coherent_avec_translate():
    assert gravure(PHRASE, largeur=512, seed=4) == gravure(PHRASE, largeur=512, seed=4)
    assert gravure(PHRASE, largeur=512, seed=4) == graver(translate(PHRASE, seed=4), largeur=512)


def test_l_encre_reste_dans_la_largeur():
    # Le bourrage ne compte pas, et aucun bit ne doit sortir de l'image, même sur un mot immense.
    largeur, _, _, _, lignes = lire_png(graver("m" * 300, largeur=250))
    assert largeur == 250
    assert encre(lignes, largeur) > 0


def test_plus_de_texte_plus_de_hauteur():
    courte = lire_png(graver("Je chante", largeur=512))[1]
    longue = lire_png(graver(PHRASE * 3, largeur=512))[1]
    assert longue > courte


def test_hauteur_bornee_pour_printr():
    assert lire_png(graver("a\n" * 5000, largeur=512))[1] <= HAUTEUR_MAX


@pytest.mark.parametrize("texte", ["", "   ", "\n\n", "12 + 3 !", "é", "日本語 🐌", "Je"])
def test_cas_limites(texte):
    largeur, hauteur, *_ = lire_png(graver(texte, largeur=512))
    assert largeur == 512
    assert hauteur > 0


def test_inconnu_ne_laisse_que_du_blanc():
    _, _, _, _, lignes = lire_png(graver("日本語", largeur=512))
    assert encre(lignes, 512) == 0


def test_les_deliés_survivent_et_les_lettres_gardent_leurs_trous():
    # Le « o » doit garder son blanc intérieur : sinon le remplissage est faux.
    largeur, _, _, _, lignes = lire_png(graver("o", largeur=1000))
    milieu = [l for l in lignes if int.from_bytes(l, "big") != (1 << (len(l) * 8)) - 1]
    assert milieu
    tranche = milieu[len(milieu) // 2]
    texte = bin(int.from_bytes(tranche, "big"))[2:].zfill(len(tranche) * 8)[:largeur].strip("1")
    assert "1" in texte  # du noir, puis du blanc, puis du noir


def test_meme_dessin_que_rsvg():
    # Le rastériseur et un outil de référence doivent voir presque les mêmes pixels.
    if shutil.which("rsvg-convert") is None or shutil.which("magick") is None:
        pytest.skip("rsvg-convert ou magick absent")
    from vetuste_scripteur.enluminure import _fonte, formes

    fonte = _fonte()
    glyphes = formes("Mange")
    echelle = 72 / fonte["unites"]
    x = 20.0
    morceaux = []
    for g in glyphes:
        morceaux.append(f'<path transform="translate({x} 90) scale({echelle})" d="{fonte["glyphes"][g]["d"]}"/>')
        x += fonte["glyphes"][g]["a"] * echelle
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="512" height="130"><rect width="512" height="130" fill="#fff"/>'
           f'{"".join(morceaux)}</svg>')
    reference = subprocess.run(
        "rsvg-convert | magick png:- -colorspace Gray -threshold 58% -depth 1 gray:-", shell=True,
        input=svg.encode(), capture_output=True, check=True,
    ).stdout
    from vetuste_scripteur.gravure import _rasteriser

    image = [0] * 130
    x = 20.0
    for g in glyphes:
        dx, dy, l, rangees = _rasteriser(g, echelle)
        for j, bits in enumerate(rangees):
            image[90 + dy + j] |= bits << (512 - round(x) - dx - l)
        x += fonte["glyphes"][g]["a"] * echelle
    pas = 64
    differences = noirs = 0
    for y in range(130):
        ref = (1 << 512) - 1 - int.from_bytes(reference[y * pas:(y + 1) * pas], "big")
        differences += bin(ref ^ image[y]).count("1")
        noirs += bin(ref).count("1")
    assert noirs > 500
    assert differences / noirs < 0.08


def binaire(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "vetuste_scripteur", *args], capture_output=True, cwd=RACINE)


def test_cli_png():
    resultat = binaire("--png", "--largeur", "512", "--seed", "4", "--niveau", "1", PHRASE)
    assert resultat.returncode == 0
    assert resultat.stdout == gravure(PHRASE, largeur=512, seed=4, level=1)


def test_cli_png_demande_une_largeur():
    resultat = binaire("--png", PHRASE)
    assert resultat.returncode == 2
    assert "--largeur" in resultat.stderr.decode()
    assert resultat.stdout == b""


def test_cli_png_exclusif():
    assert binaire("--png", "--svg", "--largeur", "512", "x").returncode == 2
    assert binaire("--png", "--json", "--largeur", "512", "x").returncode == 2


def test_archive_pyz_grave_sans_rien(tmp_path):
    subprocess.run([sys.executable, str(RACINE / "scripts" / "construire_pyz.py")], capture_output=True, check=True)
    archive = tmp_path / "v.pyz"
    archive.write_bytes((RACINE / "dist" / "vetuste-scripteur.pyz").read_bytes())
    sortie = subprocess.run([sys.executable, "-I", str(archive), "--png", "--largeur=512", "--seed=4", "--", PHRASE],
                            capture_output=True, check=True, cwd=tmp_path, env={"LC_ALL": "C"}).stdout
    assert sortie == gravure(PHRASE, largeur=512, seed=4)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from vetuste_scripteur.web import app

    return TestClient(app)


def test_web_png(client):
    reponse = client.get("/enluminure.png", params={"phrase": PHRASE, "largeur": 512, "seed": 4, "level": 1})
    assert reponse.status_code == 200
    assert reponse.headers["content-type"] == "image/png"
    assert reponse.headers["x-seed"] == "4"
    assert reponse.content == gravure(PHRASE, largeur=512, seed=4, level=1)


@pytest.mark.parametrize(
    "params",
    [{"phrase": "x"}, {"largeur": 512}, {"phrase": "x", "largeur": 100}, {"phrase": "x", "largeur": 9000},
     {"phrase": "x" * 5001, "largeur": 512}, {"phrase": "x", "largeur": 512, "level": 9}],
)
def test_web_png_requetes_refusees(client, params):
    assert client.get("/enluminure.png", params=params).status_code == 422
