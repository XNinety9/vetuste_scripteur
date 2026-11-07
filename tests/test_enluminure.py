"""Le dessin SVG : document valide, reproductible, autonome, et lisible par de vrais outils."""

import json
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from vetuste_scripteur import enluminure, translate
from vetuste_scripteur.enluminure import dessiner, formes

RACINE = Path(__file__).resolve().parent.parent
FONTE = RACINE / "vetuste_scripteur" / "fonts" / "UnifrakturMaguntia-Book.ttf"
SVG = "{http://www.w3.org/2000/svg}"
PHRASE = "Madame, vous êtes très belle. Je cherchais mon portable dans la voiture !"


def racine(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def test_document_valide_et_dimensionne():
    document = racine(enluminure(PHRASE, seed=4))
    assert document.tag == f"{SVG}svg"
    assert document.get("width") == "1200"
    assert float(document.get("height")) > 300


def test_reproductible():
    assert enluminure(PHRASE, seed=4) == enluminure(PHRASE, seed=4)
    assert enluminure(PHRASE, seed=4) != enluminure(PHRASE, seed=5)


def test_sans_seed_varie():
    assert len({enluminure(PHRASE) for _ in range(5)}) > 1


def test_le_titre_porte_le_texte_transmogrifie():
    document = racine(enluminure(PHRASE, seed=4))
    assert document.find(f"{SVG}title").text == translate(PHRASE, seed=4)


def test_autonome():
    # Ni texte à rendre avec une fonte, ni ressource à télécharger.
    svg = enluminure(PHRASE, seed=4)
    document = racine(svg)
    assert not document.findall(f".//{SVG}text")
    assert not document.findall(f".//{SVG}image")
    assert "font-family" not in svg
    assert "http" not in svg.replace("http://www.w3.org/2000/svg", "").replace("http://www.w3.org/1999/xlink", "")


@pytest.mark.parametrize("hostile", ['<script>alert(1)</script> & "x"', "]]>", "a\x00b\x1fc", "\ud800x", "￾"])
def test_texte_hostile_reste_du_xml_valide(hostile):
    svg = dessiner(hostile, seed=1)
    document = racine(svg)
    assert not document.findall(f".//{SVG}script")


@pytest.mark.parametrize("texte", ["", "   ", "\n\n", "12 + 3 !", "é", "日本語 🐌", "Je", "a\n" * 300])
def test_cas_limites(texte):
    assert racine(dessiner(texte, seed=1)).tag == f"{SVG}svg"


def test_mot_immense_coupe_dans_la_page():
    # Chaque lettre doit rester dans la largeur de la page.
    svg = dessiner("a" * 400, seed=1, largeur=360)
    groupe = [g for g in racine(svg).findall(f"{SVG}g") if (g.get("transform") or "").startswith("scale")][0]
    echelle = float(groupe.get("transform")[6:-1])
    positions = [float(u.get("x")) * echelle for u in groupe.iter(f"{SVG}use")]
    assert positions and max(positions) < 360


def test_hauteur_bornee():
    assert float(racine(dessiner("a\n" * 5000, seed=1)).get("height")) <= 16000


def test_largeur_change_la_mise_en_page():
    etroit, large = (float(racine(enluminure(PHRASE, seed=4, largeur=w)).get("height")) / w for w in (360, 1200))
    assert etroit > large


@pytest.mark.parametrize("largeur", [100, 9000])
def test_largeur_refusee(largeur):
    with pytest.raises(ValueError, match="largeur"):
        enluminure(PHRASE, largeur=largeur)


def test_bete_par_defaut_escargot_et_chat_disponible():
    defaut = dessiner("Bonjour", seed=1)
    chat = dessiner("Bonjour", seed=1, bete="chat")
    assert "#7f94ab" not in defaut
    assert "#7f94ab" in chat
    racine(chat)
    with pytest.raises(ValueError, match="bête"):
        dessiner("Bonjour", bete="licorne")


def test_le_francais_est_couvert():
    assert None not in formes("àâäçéèêëîïôöùûüÿœæÀÂÄÇÉÈÊËÎÏÔÖÙÛÜŒÆ«»'’…!?.,;:-—0123456789")


@pytest.mark.parametrize(
    "mot",
    ["parchemin", "chopinoist", "cherchais", "ch", "ck", "tz", "st", "fi", "ff", "ffi", "ffl", "Esté", "œuvre",
     "gvettoys", "estez", "bezognoy", "sommeylloy", "qu'il", "l'ami", "tt", "ss", "ll", "sch", "ct", "à", "Ça"],
)
def test_memes_glyphes_que_harfbuzz(mot):
    harfbuzz = pytest.importorskip("uharfbuzz")
    face = harfbuzz.Face(FONTE.read_bytes())
    fonte = harfbuzz.Font(face)
    tampon = harfbuzz.Buffer()
    tampon.add_str(mot)
    tampon.guess_segment_properties()
    harfbuzz.shape(fonte, tampon)
    attendu = [fonte.glyph_to_string(info.codepoint) for info in tampon.glyph_infos]
    assert formes(mot) == attendu


def test_memes_largeurs_que_harfbuzz():
    harfbuzz = pytest.importorskip("uharfbuzz")
    from vetuste_scripteur.enluminure import _avance

    fonte = harfbuzz.Font(harfbuzz.Face(FONTE.read_bytes()))
    tampon = harfbuzz.Buffer()
    tampon.add_str(PHRASE)
    tampon.guess_segment_properties()
    harfbuzz.shape(fonte, tampon)
    attendu = sum(p.x_advance for p in tampon.glyph_positions)
    assert sum(_avance(g) for g in formes(PHRASE)) == attendu


def test_rsvg_convert_produit_un_png(tmp_path):
    outil = shutil.which("rsvg-convert")
    if outil is None:
        pytest.skip("rsvg-convert absent")
    fichier = tmp_path / "page.svg"
    fichier.write_text(enluminure(PHRASE, seed=4), encoding="utf-8")
    png = subprocess.run([outil, str(fichier)], capture_output=True, check=True).stdout
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def cli(*args: str) -> str:
    return subprocess.run([sys.executable, "-m", "vetuste_scripteur", *args], capture_output=True, text=True,
                          encoding="utf-8", cwd=RACINE, check=True).stdout


def test_cli_svg():
    sortie = cli("--svg", "--seed", "4", "--largeur", "800", "--niveau", "1", PHRASE)
    assert sortie == enluminure(PHRASE, seed=4, level=1, largeur=800)


def test_cli_svg_entree_standard():
    sortie = subprocess.run([sys.executable, "-m", "vetuste_scripteur", "--svg", "--seed", "4", "-"], input=PHRASE,
                            capture_output=True, text=True, encoding="utf-8", cwd=RACINE, check=True).stdout
    assert sortie == enluminure(PHRASE, seed=4)


def test_cli_svg_sans_texte_refuse(monkeypatch, capsys):
    from vetuste_scripteur import cli as module

    monkeypatch.setattr(module, "_texte_demande", lambda mots: None)
    monkeypatch.setattr(module.sys, "stdin", open(RACINE / "README.md", encoding="utf-8"))
    assert module.main(["--svg"]) == 2
    assert "demande un texte" in capsys.readouterr().err


def test_cli_svg_et_json_incompatibles():
    resultat = subprocess.run([sys.executable, "-m", "vetuste_scripteur", "--svg", "--json", "x"],
                              capture_output=True, cwd=RACINE)
    assert resultat.returncode == 2


def test_archive_pyz_dessine_sans_rien(tmp_path):
    subprocess.run([sys.executable, str(RACINE / "scripts" / "construire_pyz.py")], capture_output=True, check=True)
    archive = tmp_path / "v.pyz"
    archive.write_bytes((RACINE / "dist" / "vetuste-scripteur.pyz").read_bytes())
    sortie = subprocess.run([sys.executable, "-I", str(archive), "--svg", "--seed", "4", PHRASE],
                            capture_output=True, text=True, encoding="utf-8", check=True, cwd=tmp_path).stdout
    assert sortie == enluminure(PHRASE, seed=4)
    # La licence de la fonte accompagne ses tracés ; ni les fontes ni la page web ne sont embarquées.
    contenu = subprocess.run([sys.executable, "-m", "zipfile", "-l", str(archive)], capture_output=True, text=True).stdout
    assert "OFL-UnifrakturMaguntia.txt" in contenu
    assert ".ttf" not in contenu
    assert "page.html" not in contenu


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from vetuste_scripteur.web import app

    return TestClient(app)


def test_web_svg(client):
    reponse = client.get("/enluminure.svg", params={"phrase": PHRASE, "seed": 4, "level": 1, "largeur": 800})
    assert reponse.status_code == 200
    assert reponse.headers["content-type"].startswith("image/svg+xml")
    assert reponse.headers["x-seed"] == "4"
    assert reponse.text == enluminure(PHRASE, seed=4, level=1, largeur=800)


def test_web_svg_seed_rejouable(client):
    premiere = client.get("/enluminure.svg", params={"phrase": PHRASE})
    rejouee = client.get("/enluminure.svg", params={"phrase": PHRASE, "seed": premiere.headers["x-seed"]})
    assert rejouee.text == premiere.text


def test_web_svg_coherent_avec_translate(client):
    texte = client.get("/translate", params={"phrase": PHRASE, "seed": 9}).json()["result"]
    svg = client.get("/enluminure.svg", params={"phrase": PHRASE, "seed": 9}).text
    assert racine(svg).find(f"{SVG}title").text == texte


@pytest.mark.parametrize(
    "params",
    [{"phrase": "x" * 5001}, {"phrase": "x", "level": 9}, {"phrase": "x", "seed": -1},
     {"phrase": "x", "largeur": 100}, {"phrase": "x", "largeur": 9000}, {}],
)
def test_web_svg_requetes_refusees(client, params):
    assert client.get("/enluminure.svg", params=params).status_code == 422


def test_json_toujours_stable():
    assert set(json.loads(cli("--json", "--seed", "1", "Je chante"))) == {"original", "result", "seed", "level", "version"}
