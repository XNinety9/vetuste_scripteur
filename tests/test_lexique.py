"""La cohérence des données."""

import pytest

from vetuste_scripteur import translate
from vetuste_scripteur.conjugaison import formes, table
from vetuste_scripteur.lexique import ETRE, LEXIQUE, VERBES_SUBSTITUTS


@pytest.mark.parametrize("verbe", sorted({*VERBES_SUBSTITUTS, *VERBES_SUBSTITUTS.values()}))
def test_tous_les_verbes_sont_generes(verbe):
    # Sinon : relancer scripts/generer_verbes.py.
    assert verbe in table()


def test_les_substituts_ne_sont_pas_pronominaux():
    # Le moteur ne sait pas accorder « se » à la personne : « je veux s'échapper ».
    assert not [v for v in VERBES_SUBSTITUTS.values() if v.startswith(("s'", "se "))]


def test_table_complete():
    temps = {"ip", "ii", "if", "is", "cp", "sp", "si"}
    for verbe, conj in table().items():
        assert temps <= conj.keys(), verbe
        assert all(len(conj[t]) == 6 for t in temps), verbe
        assert len(conj["pp"]) == 4, verbe


def test_aucun_pronom_dans_les_formes():
    assert not [f for f in formes() if " " in f or "'" in f]


def test_etre_complet():
    assert all(len(formes_etre) == 6 for formes_etre in ETRE.values())


def test_aucune_entree_identique():
    identiques = [mot for mot, entree in LEXIQUE.items() if mot in entree.choix]
    assert not identiques


def test_singulier_et_pluriel_distincts_quand_le_mot_est_invariable():
    assert LEXIQUE["repas"].choix == ("banquet",)
    assert LEXIQUE["chevaux"].choix == ("destriers",)
    assert LEXIQUE["vêtements"].choix == ("accoutrements",)


# Le genre du mot moderne, à comparer à celui du substitut : l'article doit rester juste.
_FEMININS = (
    "route porte raison mort maison ville fête guerre bataille victoire défaite bière nourriture chance "
    "peur rumeur loi faute voiture télévision radio série photo imprimante facture douche forêt épée "
    "chanson musique fenêtre permission situation trahison lâcheté université pharmacie reine fille"
).split()
_MASCULINS = (
    "café restaurant lit vin problème malheur bonheur danger courage secret mensonge camion avion train "
    "vélo téléphone ordinateur internet wifi mail film ticket frigo kilomètre kilo cheval chat chien "
    "château chemin appartement argent bateau navire miroir repas festin travail vêtement hôpital"
).split()


@pytest.mark.parametrize("nom", _FEMININS)
def test_substitut_feminin(nom):
    assert LEXIQUE[nom].genre == "F"


@pytest.mark.parametrize("nom", _MASCULINS)
def test_substitut_masculin(nom):
    assert LEXIQUE[nom].genre == "M"


@pytest.mark.parametrize("nom", _FEMININS)
def test_article_feminin_conserve(nom):
    sortie = translate(f"une {nom}", seed=1, level=0)
    assert sortie.startswith("une ") and nom not in sortie.split()


@pytest.mark.parametrize("nom", _MASCULINS)
def test_article_masculin_conserve(nom):
    sortie = translate(f"un {nom}", seed=1, level=0)
    assert sortie.startswith("un ") and nom not in sortie.split()
