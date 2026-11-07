"""Le moteur de transmogrification, sans aucune dépendance.

Quatre passes sur la phrase découpée en mots :

1. les expressions figées (« tout de suite ») ;
2. les mots : verbes reconnus d'après leur contexte et re-conjugués, puis lexique ;
3. les accords : élisions et contractions à refaire quand un mot a changé (« l'ami » → « le
   compagnon », « je chante » → « j'entonnoy », « de l'argent » → « du denier ») ;
4. l'orthographe ancienne et les interjections, qui ne doivent pas influencer les accords.
"""

import random
import re
from dataclasses import dataclass, field

from .conjugaison import Analyse, conjuguer, formes
from .lexique import (
    APOSTROPHES,
    ETRE,
    ETRE_PARTICIPE,
    EXCLAMATIONS,
    EXPRESSIONS,
    LEXIQUE,
    VERBES_SUBSTITUTS,
)


@dataclass(frozen=True)
class Niveau:
    """Probabilités des fioritures d'un niveau de vieillissement."""

    s_caduc: float = 0.0  # voyelle + t → voyelle + st
    s_en_z: float = 0.0  # s entre deux voyelles → z
    j_en_i: float = 0.0
    i_en_y: float = 0.0
    u_en_v: float = 0.0
    le_en_li: float = 0.0
    exclamation: float = 0.0
    apostrophe: float = 0.0
    possessif: float = 0.0  # « mon ami » → « le mien ami »


NIVEAUX: dict[int, Niveau] = {
    0: Niveau(),  # vocabulaire et grammaire seuls, sans orthographe ancienne ni hasard décoratif
    1: Niveau(0.25, 0.20, 0.20, 0.15, 0.10, 0.20, 0.10, 0.05, 0.0),  # léger accent
    2: Niveau(1.00, 0.70, 0.80, 0.40, 0.30, 0.60, 0.25, 0.10, 0.0),  # Les Visiteurs
    3: Niveau(1.00, 1.00, 1.00, 0.70, 0.55, 1.00, 0.50, 0.30, 0.70),  # grimoire illisible
}
NIVEAU_PAR_DEFAUT = 2


@dataclass
class Jeton:
    """Un mot de la phrase, et ce qui le suit (espaces, ponctuation, chiffres)."""

    texte: str
    sep: str = ""
    sortie: str = ""
    change: bool = False
    genre: str | None = None
    fige: bool = False  # issu d'une expression : ne plus y toucher
    sujet_inverse: int | None = None  # « mange-t-il » : le rang du pronom accolé
    bas: str = field(init=False)

    def __post_init__(self) -> None:
        self.bas = self.texte.lower().replace("’", "'")
        self.sortie = self.sortie or self.texte


# ─── Découpage ───────────────────────────────────────────────────────────────────────────

_MOT = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*['’]?")
_ELISION = re.compile(r"^(l|d|j|m|t|s|c|n|qu|jusqu|lorsqu|puisqu|quoiqu)['’](.+)$", re.IGNORECASE)
_INSECABLES = {"presqu'île"}
_SUJETS_INVERSES = {
    "je": 0, "tu": 1, "il": 2, "elle": 2, "on": 2, "nous": 3, "vous": 4, "ils": 5, "elles": 5,
}
_INVERSION = re.compile(
    r"^(.+?)(-t-(il|elle|on)|-(je|tu|il|elle|on|nous|vous|ils|elles)|-(?:moi|toi|ce|en|y|le|la|les|lui|leur))$",
    re.IGNORECASE,
)


def _decouper(texte: str) -> tuple[str, list[Jeton]]:
    """Le texte devient ce qui précède le premier mot, et la liste des mots."""
    jetons: list[Jeton] = []
    debut = None
    fin = 0
    for correspondance in _MOT.finditer(texte):
        if jetons:
            jetons[-1].sep += texte[fin:correspondance.start()]
        else:
            debut = texte[:correspondance.start()]
        fin = correspondance.end()
        jetons.extend(_decouper_mot(correspondance.group()))
    if not jetons:
        return texte, []
    jetons[-1].sep += texte[fin:]
    return debut or "", jetons


def _decouper_mot(mot: str) -> list[Jeton]:
    normal = mot.lower().replace("’", "'")
    if normal in LEXIQUE or normal in _INSECABLES:
        return [Jeton(mot)]
    elision = _ELISION.match(mot)
    if elision:
        prefixe = mot[: elision.end(1) + 1]
        return [Jeton(prefixe), *_decouper_mot(elision.group(2))]
    inversion = _INVERSION.match(mot)
    if inversion and inversion.group(1).lower() in formes():
        pronom = (inversion.group(3) or inversion.group(4) or "").lower()
        return [Jeton(inversion.group(1), sep=inversion.group(2),
                      sujet_inverse=_SUJETS_INVERSES.get(pronom))]
    return [Jeton(mot)]


def _appliquer_expressions(jetons: list[Jeton]) -> list[Jeton]:
    """Remplace les expressions figées, en commençant par les plus longues."""
    longueurs = sorted({len(cle) for cle in EXPRESSIONS}, reverse=True)
    sortie: list[Jeton] = []
    i = 0
    while i < len(jetons):
        for n in longueurs:
            morceau = jetons[i:i + n]
            cle = tuple(j.bas for j in morceau)
            if cle in EXPRESSIONS and all(_lie(j.sep) for j in morceau[:-1]):
                fige = Jeton(morceau[0].texte, sep=morceau[-1].sep, change=True, fige=True)
                fige.sortie = _casse(morceau[0].texte, EXPRESSIONS[cle])
                sortie.append(fige)
                i += n
                break
        else:
            sortie.append(jetons[i])
            i += 1
    return sortie


def _lie(sep: str) -> bool:
    """Vrai si seuls des espaces séparent deux mots : ils sont dans le même groupe."""
    return not sep.strip()


def _casse(modele: str, mot: str) -> str:
    """Reporte la casse du mot d'origine (Initiale ou TOUT EN CAPITALES)."""
    if not mot or not modele:
        return mot
    lettres = re.sub(r"\W", "", modele)
    if len(lettres) > 1 and lettres.isupper():
        return mot.upper()
    if modele[0].isupper():
        return mot[0].upper() + mot[1:]
    return mot


# ─── Contexte grammatical ────────────────────────────────────────────────────────────────

_SUJETS = {"je": 0, "j'": 0, "tu": 1, "il": 2, "elle": 2, "on": 2, "ils": 5, "elles": 5}
_SUJETS_AMBIGUS = {"nous": 3, "vous": 4}  # sujets, ou compléments : « il vous aime »
_CLITIQUES = {
    "ne", "n'", "me", "m'", "te", "t'", "se", "s'", "le", "la", "les", "l'", "lui", "leur", "y", "en",
    "nous", "vous",
}
_ARTICLES_OU_CLITIQUES = {"le", "la", "les", "l'", "leur"}
_DETERMINANTS = {
    "un", "une", "des", "du", "au", "aux", "mon", "ton", "son", "ma", "ta", "sa", "mes", "tes", "ses",
    "notre", "votre", "nos", "vos", "leurs", "ce", "cet", "cette", "ces", "quel", "quelle", "quels",
    "quelles", "chaque", "plusieurs", "quelques", "certains", "certaines", "aucun", "aucune",
}
_ADJECTIFS_ANTEPOSES = {
    "petit", "petite", "petits", "petites", "grand", "grande", "grands", "grandes", "bon", "bonne",
    "bons", "bonnes", "beau", "belle", "beaux", "belles", "vieux", "vieille", "vieilles", "jeune",
    "jeunes", "gros", "grosse", "grosses", "long", "longue", "longs", "longues", "nouveau", "nouvelle",
    "nouveaux", "nouvelles", "joli", "jolie", "jolis", "jolies", "mauvais", "mauvaise", "mauvaises",
    "premier", "première", "premiers", "premières", "dernier", "dernière", "derniers", "dernières",
}
_PREPOSITIONS = {
    "de", "d'", "à", "sans", "avec", "pour", "par", "en", "dans", "sur", "sous", "chez", "vers", "contre",
    "entre", "pendant", "depuis", "avant", "après", "devant", "derrière",
}
_CONJONCTIONS = {"et", "ou", "mais", "qui", "que", "qu'", "quand", "si", "car", "lorsque", "lorsqu'", "puisque"}
# Sans pronom devant, ces mots sont des adjectifs ou des prépositions, pas des verbes.
_PAS_VERBE_SANS_PRONOM = {
    "entre", "contre", "vide", "vides", "calme", "calmes", "fixe", "fixes", "sèche", "sèches",
    "trouble", "troubles", "comme", "pendant", "devant", "suivant", "ferme", "fermes", "bien",
    "place", "places", "droite", "reste", "montre", "montres",
}
# Sans pronom devant, ces mots ne se remplacent pas quand un déterminant les précède.
_GARDER_APRES_DETERMINANT = {"pas", "son", "vers", "sur", "sous", "fort", "peu", "non", "aussi", "droite"}
_PAS_VERBE_INCONNU = {"même", "mêmes", "toute", "toutes", "quelque", "seule", "seules", "aussi"}
_MOTS_FONCTION = (
    set(_SUJETS) | set(_SUJETS_AMBIGUS) | _CLITIQUES | _DETERMINANTS | _PREPOSITIONS | _CONJONCTIONS
    | {"c'", "cela", "ça", "ceci", "tout", "tous", "toute", "toutes", "il", "voici", "voilà", "ici", "là"}
)


_IMPERATIF_ACCOLE = re.compile(r"-(moi|toi|en|y|le|la|les|lui|leur)\b", re.IGNORECASE)


def _sujet(jetons: list[Jeton], i: int) -> int | None:
    """Le rang du pronom sujet du mot i, en remontant par-dessus « ne » et les compléments."""
    if jetons[i].sujet_inverse is not None:
        return jetons[i].sujet_inverse
    ambigu = None
    for j in range(i - 1, -1, -1):
        if not _lie(jetons[j].sep):
            break
        bas = jetons[j].bas
        if bas in _SUJETS:
            return _SUJETS[bas]
        if bas in _SUJETS_AMBIGUS and ambigu is None:
            ambigu = _SUJETS_AMBIGUS[bas]
        if bas not in _CLITIQUES:
            break
    return ambigu


def _est_nominal(jetons: list[Jeton], i: int) -> bool:
    """Vrai si le mot i suit un déterminant : c'est alors un nom, pas un verbe (« la porte »)."""
    if i == 0 or not _lie(jetons[i - 1].sep):
        return False
    avant = jetons[i - 1].bas
    if avant in _ARTICLES_OU_CLITIQUES:
        if _sujet(jetons, i - 1) is not None:
            return False  # « il la porte »
        return not (i >= 2 and jetons[i - 2].bas in {"qui", "que", "qu'", "ne", "n'"})
    if avant == "ce" and any(a.verbe == "être" for a in formes().get(jetons[i].bas, ())):
        return False  # « ce sont »
    if avant in _DETERMINANTS:
        return True
    return avant in _ADJECTIFS_ANTEPOSES and _est_nominal(jetons, i - 1)


def _analyser(jetons: list[Jeton], i: int, verbe_vu: bool) -> Analyse | None:
    """Reconnaît un verbe d'après sa forme et son contexte, ou renvoie None."""
    jeton = jetons[i]
    analyses = formes().get(jeton.bas)
    if not analyses or _est_nominal(jetons, i):
        return None
    par_temps = lambda *temps: [a for a in analyses if a.temps in temps]  # noqa: E731

    # « donne-moi » : un pronom complément accolé signe l'impératif.
    if _IMPERATIF_ACCOLE.match(jeton.sep) and par_temps("im"):
        return par_temps("im")[0]

    # Un pronom sujet décide de tout : « nous courons » n'est pas un futur en -rons.
    rang = _sujet(jetons, i)
    if rang is not None:
        finies = [a for a in par_temps("ip", "ii", "if", "cp", "is", "sp", "si") if a.rang == rang]
        if finies:
            return finies[0]

    avant = jetons[i - 1] if i and _lie(jetons[i - 1].sep) else None

    # Après une préposition, seuls l'infinitif et le gérondif restent possibles.
    if avant is not None and avant.bas in _PREPOSITIONS:
        retenues = par_temps("inf") + (par_temps("pr") if avant.bas == "en" else [])
        return retenues[0] if retenues else None

    # Après un auxiliaire, le participe passe avant tout : « il a fait », « il est mort ».
    if avant is not None and any(a.verbe in ("avoir", "être") for a in formes().get(avant.bas, ())):
        if par_temps("pp"):
            return par_temps("pp")[0]

    if par_temps("inf"):
        return par_temps("inf")[0]

    debut_de_phrase = i == 0 or not _lie(jetons[i - 1].sep)
    if jeton.bas not in _PAS_VERBE_SANS_PRONOM and not verbe_vu:
        # Un nom connu du lexique en tête de phrase reste un nom : « Fête de la musique ».
        if not (debut_de_phrase and _est_nom_du_lexique(jeton.bas)):
            finies = [a for a in par_temps("ip", "ii", "if", "cp", "is", "sp", "si") if a.rang in (2, 5)]
            if finies:
                return finies[0]
            if debut_de_phrase and par_temps("im"):
                return par_temps("im")[0]

    retenues = par_temps("pp", "pr")
    return retenues[0] if retenues else None


def _est_nom_du_lexique(mot: str) -> bool:
    entree = LEXIQUE.get(mot)
    return entree is not None and entree.genre is not None


# ─── Formes verbales ─────────────────────────────────────────────────────────────────────


def _finales_anciennes(forme: str, temps: str, rang: int) -> str:
    """Imparfait et conditionnel en -ois, -oit, -oient ; présent en -oy."""
    if temps in ("ii", "cp"):
        return re.sub(r"a(is|it|ient)$", r"o\1", forme)
    if temps == "ip" and rang in (0, 2) and len(forme) > 2 and forme.endswith("e"):
        if forme.endswith("oie"):  # « octroie » donne « octroyoy », pas « octroioy »
            return forme[:-2] + "yoy"
        return forme[:-1] + "oy"
    return forme


def _forme_verbale(analyse: Analyse, forme_source: str) -> str:
    verbe, temps, rang = analyse
    if verbe == "être":
        if temps == "pp":
            return ETRE_PARTICIPE
        return ETRE[temps][rang] if temps in ETRE else forme_source
    cible = VERBES_SUBSTITUTS.get(verbe)
    forme = (conjuguer(cible, temps, rang) if cible else None) or forme_source
    return _finales_anciennes(forme, temps, rang)


def _forme_verbe_inconnu(mot: str, rang: int) -> str:
    """Un mot juste après un pronom sujet, absent des tables : sans doute un verbe, on l'archaïse."""
    if len(mot) <= 3 or mot in _PAS_VERBE_INCONNU or mot in _MOTS_FONCTION:
        return mot
    if (rang in (0, 1) and mot.endswith("ais")) or (rang == 2 and mot.endswith("ait")) \
            or (rang == 5 and mot.endswith("aient")):
        return _finales_anciennes(mot, "ii", rang)
    return _finales_anciennes(mot, "ip", rang)


# ─── Les mots ────────────────────────────────────────────────────────────────────────────


def _remplacer(jeton: Jeton, nouveau: str, genre: str | None = None) -> None:
    jeton.sortie = _casse(jeton.texte, nouveau)
    jeton.change = nouveau != jeton.bas
    jeton.genre = genre


def _transformer_mots(jetons: list[Jeton], alea: random.Random) -> None:
    verbe_vu = False  # dans le groupe en cours : un seul verbe conjugué sans pronom
    for i, jeton in enumerate(jetons):
        if i and not _lie(jetons[i - 1].sep):
            verbe_vu = False
        if jeton.fige:
            continue
        if jeton.bas in _CONJONCTIONS:
            verbe_vu = False

        analyse = _analyser(jetons, i, verbe_vu)
        if analyse is not None:
            _remplacer(jeton, _forme_verbale(analyse, jeton.bas))
            verbe_vu = verbe_vu or analyse.temps not in ("inf", "pp", "pr")
            continue

        rang = _sujet(jetons, i)
        if rang is not None and jeton.bas not in LEXIQUE and jeton.bas not in formes():
            _remplacer(jeton, _forme_verbe_inconnu(jeton.bas, rang))
            continue

        entree = LEXIQUE.get(jeton.bas)
        if entree is None:
            continue
        if jeton.bas in _GARDER_APRES_DETERMINANT and _est_nominal(jetons, i):
            continue
        if jeton.bas == "ce" and _est_pronom_ce(jetons, i):
            continue
        _remplacer(jeton, alea.choice(entree.choix), entree.genre)


def _est_pronom_ce(jetons: list[Jeton], i: int) -> bool:
    """Vrai pour « ce que », « ce sont » : on ne veut pas de « cestui que »."""
    if i + 1 >= len(jetons) or not _lie(jetons[i].sep):
        return True
    suivant = jetons[i + 1].bas
    return suivant in {"que", "qui", "qu'", "dont", "à", "de"} or \
        any(a.verbe == "être" for a in formes().get(suivant, ()))


# ─── Les accords ─────────────────────────────────────────────────────────────────────────

_VOYELLES = "aeiouyàâäéèêëîïôöùûüæœ"
_H_ASPIRES = ("harangu",)
_REELIDES = {"j'": "je", "m'": "me", "t'": "te", "s'": "se", "n'": "ne", "c'": "ce", "d'": "de", "qu'": "que"}
_ELIDES = {"je": "j'", "me": "m'", "te": "t'", "se": "s'", "ne": "n'", "ce": "c'", "de": "d'", "que": "qu'", "le": "l'", "la": "l'"}
_POSSESSIFS_F = {"mon": "ma", "ton": "ta", "son": "sa"}
_POSSESSIFS_M = {"ma": "mon", "ta": "ton", "sa": "son"}
_CONTRACTIONS = {"de": "du", "d'": "du", "à": "au"}
_DECONTRACTIONS = {"du": "de l'", "au": "à l'"}


def _commence_par_voyelle(mot: str) -> bool:
    mot = mot.lower()
    if mot.startswith("h"):
        return not mot.startswith(_H_ASPIRES)
    return mot[:1] in _VOYELLES


def _accorder(jetons: list[Jeton]) -> list[Jeton]:
    """Refait les élisions et les contractions autour des mots qui ont changé."""
    supprimes: set[int] = set()
    for i in range(len(jetons) - 1):
        mot, suivant = jetons[i], jetons[i + 1]
        if not suivant.change or mot.fige or not _lie(mot.sep) or mot.sortie.lower().replace("’", "'") != mot.bas:
            continue
        voyelle = _commence_par_voyelle(suivant.sortie)
        bas = mot.bas

        if bas == "l'" and not voyelle:
            precedent = jetons[i - 1] if i and _lie(jetons[i - 1].sep) else None
            if suivant.genre != "F" and precedent is not None and precedent.bas in _CONTRACTIONS \
                    and precedent.sortie.lower().replace("’", "'") == precedent.bas:
                precedent.sortie = _casse(precedent.texte, _CONTRACTIONS[precedent.bas])
                precedent.sep = " "
                supprimes.add(i)
            else:
                mot.sortie = _casse(mot.texte, "la" if suivant.genre == "F" else "le")
                mot.sep = " "
        elif bas in _REELIDES and not voyelle:
            mot.sortie = _casse(mot.texte, _REELIDES[bas])
            mot.sep = " "
        elif bas in _ELIDES and voyelle:
            mot.sortie = _casse(mot.texte, _ELIDES[bas])
            mot.sep = ""
        elif bas in _DECONTRACTIONS and voyelle:
            mot.sortie = _casse(mot.texte, _DECONTRACTIONS[bas])
            mot.sep = ""
        elif bas in _POSSESSIFS_F and suivant.genre == "F" and not voyelle:
            mot.sortie = _casse(mot.texte, _POSSESSIFS_F[bas])
        elif bas in _POSSESSIFS_M and voyelle:
            mot.sortie = _casse(mot.texte, _POSSESSIFS_M[bas])
    return [j for i, j in enumerate(jetons) if i not in supprimes]


# ─── Fioritures ──────────────────────────────────────────────────────────────────────────

_VOYELLE_T = re.compile(r"([aeiouàâéèêëîïôùûüæœAEIOUÀÂÉÈÊËÎÏÔÙÛÜ])t(?![tr])")
_VOYELLES_CASSE = "aeiouàâéèêëîïôùûüæœAEIOUÀÂÉÈÊËÎÏÔÙÛÜÆŒ"
_S_ENTRE_VOYELLES = re.compile(rf"(?<=[{_VOYELLES_CASSE}])s(?=[{_VOYELLES_CASSE}])")
_E_ACCENTUES = {"é": "e", "è": "e", "ê": "e", "É": "E", "È": "E", "Ê": "E"}
_LETTRES = {"j": "i", "J": "I", "i": "y", "I": "Y", "u": "v", "U": "V"}
_POSSESSIFS_TONIQUES = {
    "mon": "le mien", "ton": "le tien", "son": "le sien", "ma": "la mienne", "ta": "la tienne",
    "sa": "la sienne", "mes": "les miens", "tes": "les tiens", "ses": "les siens",
}


def _s_caduc(trouve: re.Match) -> str:
    # « été » donne « esté » : le s fait tomber l'accent de la voyelle qui le précède.
    voyelle = trouve.group(1)
    return _E_ACCENTUES.get(voyelle, voyelle) + "st"


def _orthographe(mot: str, niveau: Niveau, alea: random.Random) -> str:
    if alea.random() < niveau.s_caduc:
        mot = _VOYELLE_T.sub(_s_caduc, mot)
    if alea.random() < niveau.s_en_z:
        mot = _S_ENTRE_VOYELLES.sub("z", mot)
    taux = {"j": niveau.j_en_i, "i": niveau.i_en_y, "u": niveau.u_en_v}
    return "".join(
        _LETTRES[lettre] if lettre in _LETTRES and alea.random() < taux[lettre.lower()] else lettre
        for lettre in mot
    )


def _fioritures_mots(jetons: list[Jeton], niveau: Niveau, alea: random.Random) -> None:
    for i, jeton in enumerate(jetons):
        suivant = jetons[i + 1] if i + 1 < len(jetons) and _lie(jeton.sep) else None
        bas = jeton.sortie.lower()
        if bas == "le" and jeton.bas == "le" and suivant is not None and _sujet(jetons, i) is None \
                and alea.random() < niveau.le_en_li:
            jeton.sortie = _casse(jeton.sortie, "li")
        elif bas in _POSSESSIFS_TONIQUES and suivant is not None and not _est_nominal(jetons, i) \
                and alea.random() < niveau.possessif:
            jeton.sortie = _casse(jeton.sortie, _POSSESSIFS_TONIQUES[bas])
        jeton.sortie = _orthographe(jeton.sortie, niveau, alea)


_FIN_DE_PHRASE = re.compile(r"[.!?…\n]")
_PONCTUATION_FINALE = re.compile(r"^(\s*)([.!?…]+)")


def _nom_propre_probable(jeton: Jeton) -> bool:
    """Un mot capitalisé qu'on ne connaît pas garde sa majuscule après une exclamation."""
    return not (jeton.change or jeton.bas in _MOTS_FONCTION or jeton.bas in LEXIQUE or jeton.bas in formes())


def _fioritures_phrases(jetons: list[Jeton], niveau: Niveau, alea: random.Random) -> None:
    debut = True
    for i, jeton in enumerate(jetons):
        if debut and alea.random() < niveau.exclamation:
            if not _nom_propre_probable(jeton):
                jeton.sortie = jeton.sortie[0].lower() + jeton.sortie[1:]
            jeton.sortie = f"{alea.choice(EXCLAMATIONS)} {jeton.sortie}"
        debut = bool(_FIN_DE_PHRASE.search(jeton.sep))
        fin_de_texte = i == len(jetons) - 1
        if (debut or fin_de_texte) and alea.random() < niveau.apostrophe:
            jeton.sortie += f", {alea.choice(APOSTROPHES)}"


# ─── Point d'entrée ──────────────────────────────────────────────────────────────────────


def translate(phrase: str, *, seed: int | None = None, level: int = NIVEAU_PAR_DEFAUT) -> str:
    """Transmogrifie un texte français en vieux parler.

    `seed` rend le résultat reproductible (même texte + même seed + même niveau = même sortie).
    `level` règle les fioritures : 0 vocabulaire seul, 1 léger accent, 2 Les Visiteurs (par
    défaut), 3 grimoire illisible.
    """
    if level not in NIVEAUX:
        raise ValueError(f"niveau inconnu : {level!r} (attendu : {sorted(NIVEAUX)})")
    niveau = NIVEAUX[level]
    alea = random.Random(seed)

    prefixe, jetons = _decouper(phrase)
    if not jetons:
        return phrase.strip()

    jetons = _appliquer_expressions(jetons)
    _transformer_mots(jetons, alea)
    jetons = _accorder(jetons)
    _fioritures_mots(jetons, niveau, alea)
    _fioritures_phrases(jetons, niveau, alea)

    return (prefixe + "".join(j.sortie + j.sep for j in jetons)).strip()
