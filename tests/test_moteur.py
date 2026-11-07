"""Le comportement du moteur, au niveau 0 pour les phrases : vocabulaire et grammaire sans hasard
décoratif. Chaque cas vient d'un bug constaté ou d'une ambiguïté qu'il faut continuer à trancher.
"""

import pytest

from vetuste_scripteur import NIVEAUX, translate


def clair(phrase: str) -> str:
    return translate(phrase, seed=1, level=0)


@pytest.mark.parametrize(
    ("moderne", "attendu"),
    [
        # Le pronom élidé de la conjugaison ne doit pas se retrouver dans la forme
        ("Je parle", "Je haranguoy"),
        ("Je chante", "J'entonnoy"),
        ("J'aime le pain", "Je chéris le pain"),
        ("Je donne du pain", "J'octroyoy du pain"),
        # Le présent n'est pas un futur, malgré ses terminaisons
        ("Vous entrez", "Vous pénétrez"),
        ("Nous courons", "Nous galopons"),
        ("Vous courez", "Vous galopez"),
        # Ni un imparfait
        ("Je vais au marché", "Je vais au marché"),
        ("Je fais la cuisine", "Je fais la cuisine"),
        ("Il sait tout", "Il sait tout"),
        # Les autres temps
        ("Je mangerais une pomme", "Je ripaillerois une pomme"),
        ("Il chanterait bien", "Il entonneroit bien"),
        ("Tu regardais la télévision", "Tu lorgnois la lanterne magique"),
        ("Il entra", "Il pénétra"),
        ("Il fallait partir", "Il falloit décamper"),
        # Les participes
        ("J'ai mangé une pomme", "J'ai ripaillé une pomme"),
        ("Il est tombé", "Il estoy chu"),
        ("Elle est tombée", "Elle estoy chue"),
        ("Il a été là", "Il a esté là"),
        ("En mangeant, il chante", "En ripaillant, il entonnoy"),
        # Verbes sans pronom, que le modèle statistique manquait
        ("Mes amis boivent", "Mes compagnons chopinent"),
        ("Les chevaux courent", "Les destriers galopent"),
        ("Pour manger, il faut travailler", "Pour ripailler, il faut besogner"),
        # Inversions et impératifs
        ("Mange-t-il une pomme ?", "Ripailloy-t-il une pomme ?"),
        ("Bois ton lait !", "Chopine ton lait !"),
        ("Donne-moi ça", "Octroie-moi ça"),
        # Les pronoms entre le sujet et le verbe
        ("Je ne te parle pas", "Je ne te haranguoy point"),
        ("Il m'aime", "Il me chérit"),
        ("Je vous aime", "Je vous chéris"),
        ("Les enfants vous aiment", "Les marmots vous chérissent"),
        # Un verbe inconnu des tables, reconnu grâce au pronom
        ("Je zappe", "Je zappoy"),
    ],
)
def test_verbes(moderne, attendu):
    assert clair(moderne) == attendu


@pytest.mark.parametrize(
    ("moderne", "attendu"),
    [
        # Pluriels et féminins
        ("Les voitures sont rouges", "Les carrioles estoient écarlates"),
        ("Des maisons", "Des demeures"),
        ("Les chansons sont belles", "Les ritournelles estoient belles"),
        ("Le repas", "Le banquet"),
        # Élisions et contractions à refaire
        ("L'ami", "Le compagnon"),
        ("L'amie", "La compagne"),
        ("Il a de l'argent", "Il a du denier"),
        ("L'ami de l'ordinateur", "Le compagnon du grimoire lumineux"),
        ("Le vin", "L'hypocras"),
        ("Du vin", "De l'hypocras"),
        ("La peur", "L'épouvante"),
        ("Ma peur", "Mon épouvante"),
        ("Mon amie", "Ma compagne"),
        ("L’ami", "Le compagnon"),
        # Les homographes : le contexte décide
        ("La porte", "La poterne"),
        ("Il porte un chapeau", "Il portoy un chapeau"),
        ("Il la porte", "Il la portoy"),
        ("Le son", "Le son"),
        ("Un pas de plus", "Un pas de plus"),
        ("Il ne parle pas", "Il ne haranguoy point"),
        ("Il est mort", "Il estoy mort"),
        ("La mort", "La camarde"),
        ("Ce que je veux", "Ce que je veux"),
        ("Ce sont mes amis", "C'estoient mes compagnons"),
        ("Ce chat", "Cestui matou"),
        ("La maison est vide", "La demeure estoy vide"),
        ("Fête de la musique", "Liesse de la mélodie"),
        # Expressions et casse
        ("Un peu", "Un brin"),
        ("Tout de suite", "Incontinent"),
        ("JE MANGE", "JE RIPAILLOY"),
        # Une phrase courante de bout en bout
        (
            "Mon ami travaille beaucoup et ne dort pas assez",
            "Mon compagnon besognoy moult y ne sommeilloy point prou",
        ),
    ],
)
def test_lexique_et_accords(moderne, attendu):
    assert clair(moderne) == attendu


@pytest.mark.parametrize("vide", ["", "   ", "\n"])
@pytest.mark.parametrize("level", sorted(NIVEAUX))
def test_texte_vide(vide, level):
    # L'exclamation aléatoire faisait planter une fois sur quatre.
    for seed in range(50):
        assert translate(vide, seed=seed, level=level) == ""


def test_sans_mot():
    assert translate("12 + 3 !", seed=1) == "12 + 3 !"


@pytest.mark.parametrize("level", sorted(NIVEAUX))
def test_reproductible(level):
    phrase = "Madame, vous êtes très belle. Mon ami cherche sa voiture !"
    assert translate(phrase, seed=42, level=level) == translate(phrase, seed=42, level=level)


def test_le_hasard_varie_sans_seed():
    phrase = "Le monsieur et la dame cherchent une voiture dans la ville, disait-il souvent"
    assert len({translate(phrase) for _ in range(30)}) > 1


def test_niveau_inconnu():
    with pytest.raises(ValueError, match="niveau inconnu"):
        translate("Bonjour", level=9)


def test_niveau_zero_sans_orthographe_ni_exclamation():
    for seed in range(50):
        assert translate("Paris est petite", seed=seed, level=0) == "Paris estoy petite"


def test_le_niveau_trois_est_plus_vieilli_que_le_niveau_un():
    phrase = "Je suis très content de voir ma petite fille jouer au jardin avec un chat"
    differences = {
        niveau: sum(translate(phrase, seed=s, level=niveau).lower().count(lettre)
                    for s in range(50) for lettre in "yvz")
        for niveau in (1, 3)
    }
    assert differences[3] > differences[1]


def test_niveau_trois_possessif_tonique():
    assert any("mien" in translate("Mon chat", seed=s, level=3).lower().replace("y", "i") for s in range(30))


def test_exclamation_respecte_les_noms_propres():
    sorties = [translate("Marcel arrive", seed=s, level=3) for s in range(50)]
    avec_exclamation = [s for s in sorties if "!" in s]
    assert avec_exclamation
    assert all(s.split("! ")[1][0] in "M" for s in avec_exclamation)


def test_exclamation_abaisse_les_mots_courants():
    sorties = [translate("Je mange", seed=s, level=3) for s in range(50)]
    assert any("! i" in s.lower() and "! I" not in s and "! J" not in s for s in sorties)


def test_plusieurs_phrases_et_lignes():
    assert clair("Je chante.\nTu chantes !  Il chante") == "J'entonnoy.\nTu entonnes !  Il entonnoy"


def test_ponctuation_et_chiffres_conserves():
    assert clair("J'ai 12 chats, (dit-il)…") == "J'ai 12 matous, (dit-il)…"
