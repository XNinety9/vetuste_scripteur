"""Le lexique : mots modernes et leurs substituts archaïques.

Règle de la maison : un substitut garde le genre du mot d'origine (d'où un seul genre déclaré par
nom, contrôlé sur un échantillon par `tests/test_lexique.py`). Articles, adjectifs et participes de la phrase restent ainsi accordés sans qu'il faille
les réécrire : « la route est longue » devient « la chaussée estoy longue ».

Une entrée indique le genre du substitut, ce qui permet de refaire les élisions : « l'ami » donne
« le compagnon », et « l'amie » donne « la compagne ».
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Entree:
    """Ce par quoi remplacer un mot : un ou plusieurs choix, et leur genre s'il est connu."""

    choix: tuple[str, ...]
    genre: str | None = None  # "M", "F", ou None pour les mots sans genre


def _pluriel(mot: str) -> str:
    """Pluriel régulier d'un mot ou d'un groupe nom + adjectif (« engin volant »)."""
    if " " in mot:
        return " ".join(_pluriel(m) for m in mot.split(" "))
    if mot.endswith(("s", "x", "z")):
        return mot
    if mot.endswith(("au", "eau", "eu")):
        return mot + "x"
    return mot + "s"


LEXIQUE: dict[str, Entree] = {}


def _nom(source: str, cible: str | list[str], genre: str, *, pl: str | None = None,
         cible_pl: str | list[str] | None = None) -> None:
    """Déclare un nom, singulier et pluriel. `pl` et `cible_pl` pour les pluriels irréguliers."""
    choix = (cible,) if isinstance(cible, str) else tuple(cible)
    LEXIQUE[source] = Entree(choix, genre)
    if cible_pl is None:
        choix_pl = tuple(_pluriel(c) for c in choix)
    else:
        choix_pl = (cible_pl,) if isinstance(cible_pl, str) else tuple(cible_pl)
    pluriel = pl or _pluriel(source)
    if pluriel != source:  # « repas », « bras » : le singulier sert aussi de pluriel
        LEXIQUE[pluriel] = Entree(choix_pl, genre)


def _adj(source: str, cible: str | list[str], *, f: str | None = None,
         cible_f: str | list[str] | None = None, mp: str | None = None,
         cible_mp: str | None = None) -> None:
    """Déclare un adjectif et ses quatre formes. Sans `f`, le féminin s'obtient avec un -e."""
    choix = (cible,) if isinstance(cible, str) else tuple(cible)
    if cible_f is None:
        choix_f = tuple(c if c.endswith("e") else c + "e" for c in choix)
    else:
        choix_f = (cible_f,) if isinstance(cible_f, str) else tuple(cible_f)
    feminin = f or (source if source.endswith("e") else source + "e")
    LEXIQUE[source] = Entree(choix)
    LEXIQUE[feminin] = Entree(choix_f)
    pluriel = mp or _pluriel(source)
    if pluriel != source:  # « mauvais » : le singulier sert aussi de pluriel
        LEXIQUE[pluriel] = Entree((cible_mp,) if cible_mp else tuple(_pluriel(c) for c in choix))
    LEXIQUE[_pluriel(feminin)] = Entree(tuple(_pluriel(c) for c in choix_f))


def _mot(source: str, cible: str | list[str]) -> None:
    """Déclare un mot invariable (adverbe, préposition…)."""
    LEXIQUE[source] = Entree((cible,) if isinstance(cible, str) else tuple(cible))


# ── Adverbes ─────────────────────────────────────────────────────────────────────────────
_mot("très", "fort")
_mot("beaucoup", "moult")
_mot("assez", "prou")
_mot("peu", "guère")
_mot("alors", "lors")
_mot("aussi", "pareillement")
_mot("peut-être", "par aventure")
_mot("souvent", "maintes fois")
_mot("jamais", "oncques")
_mot("maintenant", "à présent")
_mot("aujourd'hui", "hui")
_mot("vite", "incontinent")
_mot("soudain", "tout soudain")
_mot("vraiment", "en vérité")
_mot("oui", "voui")
_mot("non", "que nenni")
_mot("ensemble", "de compagnie")
_mot("encore", "encor")
_mot("déjà", "des ores")
_mot("toujours", "de tout temps")
_mot("autrefois", "jadis")
_mot("pourquoi", "pour quelle cause")
_mot("comment", "de quelle manière")
_mot("pas", "point")
_mot("rien", "néant")

# ── Prépositions et conjonctions ─────────────────────────────────────────────────────────
_mot("dans", ["en", "dedans"])
_mot("sur", "sus")
_mot("sous", "dessouz")
_mot("vers", "devers")
_mot("et", "y")
_mot("mais", "ains")
_mot("donc", "partant")

# ── Démonstratifs ────────────────────────────────────────────────────────────────────────
_mot("ce", "cestui")
_mot("cet", "cestui")
_mot("cette", "ceste")
_mot("ces", "cez")
_mot("celui", "ycelui")
_mot("celle", "ycelle")
_mot("ceux", "iceux")
_mot("celles", "icelles")

# ── Politesse ────────────────────────────────────────────────────────────────────────────
_mot("bonjour", "le bon jour")
_mot("merci", "grand merci")

# ── Civilités ────────────────────────────────────────────────────────────────────────────
_nom("monsieur", ["sieur", "messire", "seigneur", "monseigneur"], "M", pl="messieurs",
     cible_pl=["sieurs", "messires", "seigneurs", "monseigneurs"])
_nom("madame", ["dame", "damoiselle", "gente dame"], "F", pl="mesdames",
     cible_pl=["dames", "damoiselles", "gentes dames"])
_nom("mademoiselle", "damoiselle", "F", pl="mesdemoiselles", cible_pl="damoiselles")
_nom("maître", "maistre", "M")

# ── Personnes ────────────────────────────────────────────────────────────────────────────
_nom("roi", "suzerain", "M")
_nom("reine", "suzeraine", "F")
_nom("ami", "compagnon", "M")
_nom("amie", "compagne", "F")
_nom("ennemi", "félon", "M")
_nom("voleur", ["larron", "brigand"], "M")
_nom("menteur", "fourbe", "M")
_nom("idiot", ["manant", "goujat", "maraud"], "M")
_nom("imbécile", ["manant", "goujat", "ribaud"], "M")
_nom("paysan", "vilain", "M")
_nom("soldat", "homme d'armes", "M", cible_pl="hommes d'armes")
_nom("cuisinier", "queux", "M")
_nom("médecin", "physicien", "M")
_nom("fille", "pucelle", "F")
_nom("enfant", "marmot", "M")
_nom("voisin", "manant d'à côté", "M", cible_pl="manants d'à côté")

# ── Animaux et lieux ─────────────────────────────────────────────────────────────────────
_nom("cheval", "destrier", "M", pl="chevaux")
_nom("chat", "matou", "M")
_nom("chien", "cabot", "M")
_nom("château", "manoir", "M")
_nom("forêt", "sylve", "F")
_nom("chemin", "sentier", "M")
_nom("route", "chaussée", "F")
_nom("maison", "demeure", "F")
_nom("appartement", "logis", "M")
_nom("ville", "cité", "F")
_nom("restaurant", "estaminet", "M")
_nom("café", "estaminet", "M")
_nom("bar", "bouge", "M")
_nom("hôpital", "hospice", "M", pl="hôpitaux")
_nom("pharmacie", "apothicairerie", "F")
_nom("université", "sorbonne", "F")
_nom("centre", "mitan", "M")
_nom("nord", "septentrion", "M")
_nom("sud", "midi", "M")
_nom("ouest", "occident", "M")

# ── Choses de la vie ─────────────────────────────────────────────────────────────────────
_nom("argent", "denier", "M")
_nom("permission", "licence", "F")
_nom("autorisation", "licence", "F")
_nom("chanson", "ritournelle", "F")
_nom("musique", "mélodie", "F")
_nom("porte", "poterne", "F")
_nom("fenêtre", "croisée", "F")
_nom("bateau", "vaisseau", "M")
_nom("navire", "vaisseau", "M")
_nom("épée", "flamberge", "F")
_nom("miroir", "mirouer", "M")
_nom("repas", "banquet", "M")
_nom("festin", "gueuleton", "M")
_nom("fête", "liesse", "F")
_nom("guerre", "mêlée", "F")
_nom("bataille", "mêlée", "F")
_nom("victoire", "gloire", "F")
_nom("défaite", "déconfiture", "F")
_nom("travail", "labeur", "M", pl="travaux")
_nom("lit", "grabat", "M")
_nom("vin", "hypocras", "M")
_nom("bière", "cervoise", "F")
_nom("nourriture", "pitance", "F")
_nom("vêtement", "accoutrement", "M")
_nom("problème", "tracas", "M")
_nom("situation", "conjoncture", "F")
_nom("raison", "cause", "F")
_nom("chance", "fortune", "F")
_nom("malheur", "guignon", "M")
_nom("bonheur", "heur", "M")
_nom("mort", "camarde", "F")
_nom("danger", "péril", "M")
_nom("peur", "épouvante", "F")
_nom("courage", "corage", "M")
_nom("lâcheté", "couardise", "F")
_nom("trahison", "félonie", "F")
_nom("rumeur", "renommée", "F")
_nom("secret", "mystère", "M")
_nom("mensonge", "boniment", "M")
_nom("loi", "ordonnance", "F")
_nom("faute", "faulte", "F")

# ── Objets modernes, anachronismes pittoresques ──────────────────────────────────────────
_nom("voiture", ["carriole", "charrette"], "F")
_nom("automobile", "carriole", "F")
_nom("camion", "charroi", "M")
_nom("avion", "engin volant", "M")
_nom("train", "attelage de fer", "M", cible_pl="attelages de fer")
_nom("vélo", "vélocipède", "M")
_nom("téléphone", "parchemin volant", "M")
_nom("portable", "parchemin volant", "M")
_nom("smartphone", "parchemin volant", "M")
_nom("ordinateur", "grimoire lumineux", "M")
_nom("internet", "réseau des savants", "M", cible_pl="réseaux des savants")
_nom("wifi", "fluide invisible", "M")
_nom("mail", "pli", "M")
_nom("email", "pli", "M")
_nom("courriel", "pli", "M")
_nom("télévision", "lanterne magique", "F")
_nom("radio", "boîte à voix", "F", cible_pl="boîtes à voix")
_nom("film", "mystère animé", "M")
_nom("série", "veillée sans fin", "F", cible_pl="veillées sans fin")
_nom("photo", "enluminure", "F")
_nom("imprimante", "presse de moine", "F", cible_pl="presses de moine")
_nom("ticket", "billet", "M")
_nom("facture", "quittance", "F")
_nom("frigo", "garde-manger", "M", cible_pl="garde-manger")
_nom("douche", "cataracte", "F")
_nom("kilomètre", "arpent", "M")
_nom("kilo", "quintal", "M", cible_pl="quintaux")

# ── Adjectifs ────────────────────────────────────────────────────────────────────────────
_adj("grand", "grant", f="grande", cible_f="grant")
_adj("mauvais", ["meschant", "maulvais"], f="mauvaise", cible_f=["meschante", "maulvaise"])
_adj("rouge", "écarlate")
_adj("bleu", "azur", cible_f="azur")
_adj("violet", "pourpre", f="violette", cible_f="pourpre")
_adj("marron", "brun", f="marron", cible_f="brun")
_adj("gauche", "senestre")
_adj("droite", "dextre")
_adj("drôle", "drolatique")
_adj("bizarre", "étrange")
_adj("rapide", "preste")
_adj("fort", "puissant")
_adj("lourd", "pesant")
_adj("autre", "aultre")
_adj("chaud", "ardent")
_adj("froid", "glacial", cible_mp="glacials")
_adj("riche", "prospère")
_adj("pauvre", "misérable")
_adj("téméraire", "outrecuidant", cible_f="outrecuidante")
_adj("souffrant", "dolent")
_adj("fou", "insensé", f="folle", mp="fous")

# ── Expressions de plusieurs mots ────────────────────────────────────────────────────────
EXPRESSIONS: dict[tuple[str, ...], str] = {
    ("un", "peu"): "un brin",
    ("parce", "que"): "pour ce que",
    ("parce", "qu'"): "pour ce qu'",
    ("tout", "de", "suite"): "incontinent",
    ("s'", "il", "vous", "plaît"): "de grâce",
    ("s'", "il", "te", "plaît"): "de grâce",
    ("au", "revoir"): "adieu",
}

# ── Verbes ───────────────────────────────────────────────────────────────────────────────
# Les conjugaisons viennent de `verbes.json`, généré par `scripts/generer_verbes.py`.
# Après avoir ajouté un verbe ici, il faut relancer ce script.
VERBES_SUBSTITUTS: dict[str, str] = {
    "manger": "ripailler",
    "boire": "chopiner",
    "parler": "haranguer",
    "voir": "mirer",
    "regarder": "lorgner",
    "écouter": "ouïr",
    "dormir": "sommeiller",
    "travailler": "besogner",
    "donner": "octroyer",
    "courir": "galoper",
    "marcher": "cheminer",
    "applaudir": "acclamer",
    "raconter": "narrer",
    "aimer": "chérir",
    "détester": "abhorrer",
    "tromper": "duper",
    "crier": "brailler",
    "chercher": "guetter",
    "trouver": "dénicher",
    "demander": "quérir",
    "tomber": "choir",
    "tuer": "trucider",
    "frapper": "rosser",
    "voler": "dérober",
    "chanter": "entonner",
    "danser": "gambader",
    "pleurer": "geindre",
    "rire": "pouffer",
    "attendre": "patienter",
    "partir": "décamper",
    "arriver": "survenir",
    "entrer": "pénétrer",
    "sortir": "déguerpir",
    "dîner": "mangeailler",
    "diner": "mangeailler",
    "convoquer": "mander",
    "cuisiner": "mitonner",
    "nettoyer": "récurer",
    "payer": "acquitter",
    "penser": "songer",
    "imprimer": "enluminer",
    "envoyer": "dépêcher",
}

# Formes archaïques d'être, par temps puis par rang (je, tu, il, nous, vous, ils).
ETRE: dict[str, tuple[str, ...]] = {
    "ip": ("estoy", "estes", "estoy", "somes", "estez", "estoient"),
    "ii": ("estois", "estois", "estoit", "estions", "estiez", "estoient"),
    "if": ("estray", "estras", "estra", "estrons", "estrez", "estront"),
    "cp": ("estrois", "estrois", "estroit", "estrions", "estriez", "estroient"),
}
ETRE_PARTICIPE = "esté"

EXCLAMATIONS: tuple[str, ...] = (
    "Passepoil !", "Corbleu !", "Ventrebleu !", "Morbleu !", "Palsambleu !", "Sacrebleu !",
    "Tudieu !", "Jarnicoton !", "Par ma foi !", "Par saint Gilles !", "Dieu me pardonne !",
    "Sus, manant !", "Que diable !", "Ciel et terre !", "Fientrecul !",
)

# Apostrophes ajoutées en fin de phrase : « Je mange une pomme, maraud. »
APOSTROPHES: tuple[str, ...] = (
    "maraud", "gueux", "messire", "ma mie", "foi de moi", "vil manant", "par ma barbe",
    "palsambleu", "pendard", "que diantre",
)
