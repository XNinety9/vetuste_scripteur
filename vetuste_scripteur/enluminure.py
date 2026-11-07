"""L'enluminure : le texte transmogrifié, dessiné comme une page de manuscrit, en SVG.

Aucune dépendance : les lettres sont des tracés (voir `glyphes.json`), le SVG obtenu s'affiche ou
se convertit partout sans fonte installée. Pour un PNG, n'importe quel outil SVG convient :

    vetuste-scripteur --svg "Je mange une pomme" | rsvg-convert -o page.png
"""

import json
import math
import random
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from xml.sax.saxutils import escape

from .moteur import NIVEAU_PAR_DEFAUT, translate

LARGEUR_PAR_DEFAUT = 1200
LARGEUR_MIN = 200
LARGEUR_MAX = 4000
HAUTEUR_MAX = 16000  # au-delà, bien des outils refusent de produire une image

# Toutes les couleurs de la page. Une version pour imprimante noir et blanc n'aurait qu'à en changer.
ENCRE = "#2a1a10"
ROUGE = "#a8201a"
BLEU = "#1d3f8f"
VERT = "#2f6b3a"
OR_SOMBRE = "#8a6414"
VELIN = "#f4e8cb"
OR = "url(#or)"

_DEFS = (
    '<linearGradient id="or" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#f6dd80"/><stop offset=".45" stop-color="#d4a72c"/>'
    '<stop offset=".7" stop-color="#fbe9a0"/><stop offset="1" stop-color="#a87c18"/></linearGradient>'
    '<radialGradient id="vignette" cx=".5" cy=".5" r=".72">'
    '<stop offset=".45" stop-color="#a06e32" stop-opacity="0"/>'
    '<stop offset="1" stop-color="#825523" stop-opacity=".38"/></radialGradient>'
)


def _n(valeur: float) -> str:
    """Un nombre court pour le SVG : une décimale suffit, et le fichier reste léger."""
    return f"{valeur:.1f}".removesuffix(".0")


# ─── Le texte ────────────────────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _fonte() -> dict:
    fichier = resources.files(__package__).joinpath("glyphes.json")
    return json.loads(fichier.read_text(encoding="utf-8"))


def formes(texte: str) -> list[str | None]:
    """Les glyphes d'un mot, ligatures comprises. None pour un caractère absent de la fonte."""
    fonte = _fonte()
    glyphes = [fonte["caracteres"].get(c) for c in unicodedata.normalize("NFC", texte)]
    for table in fonte["ligatures"]:
        resultat: list[str | None] = []
        i = 0
        while i < len(glyphes):
            for composants, ligature in table.get(glyphes[i], ()):
                n = len(composants)
                if glyphes[i + 1:i + 1 + n] == composants:
                    resultat.append(ligature)
                    i += n + 1
                    break
            else:
                resultat.append(glyphes[i])
                i += 1
        glyphes = resultat
    return glyphes


def _avance(glyphe: str | None) -> int:
    fonte = _fonte()
    # Un caractère inconnu (emoji, idéogramme) laisse un blanc plutôt que de tout faire échouer.
    return fonte["glyphes"][glyphe]["a"] if glyphe else fonte["unites"] // 2


@dataclass
class _Mot:
    glyphes: list[str | None]
    couleur: str = ENCRE
    capitale: str | None = None  # la couleur de la première lettre, en tête de phrase
    retour: bool = False

    @property
    def unites(self) -> int:
        return sum(_avance(g) for g in self.glyphes)


def _mots(texte: str) -> list[_Mot]:
    """Découpe le texte. Les interjections courtes sont des rubriques, à l'encre rouge."""
    rubriques = [
        phrase.span() for phrase in re.finditer(r"[^.!?…\n]+[.!?…]*", texte)
        if phrase.group().rstrip().endswith(" !") and len(phrase.group().split()) <= 5 and len(phrase.group().strip()) <= 32
    ]
    mots: list[_Mot] = []
    debut_de_phrase = True
    capitales = 0
    for trouve in re.finditer(r"\n|\S+", texte):
        if trouve.group() == "\n":
            mots.append(_Mot([], retour=True))
            debut_de_phrase = True
            continue
        mot = _Mot(formes(trouve.group()))
        if any(a <= trouve.start() < b for a, b in rubriques):
            mot.couleur = ROUGE
        elif debut_de_phrase and trouve.group()[0].isupper():
            mot.capitale = BLEU if capitales % 2 else ROUGE
            capitales += 1
        mots.append(mot)
        debut_de_phrase = trouve.group()[-1] in ".!?…"
    return mots


@dataclass
class _Ligne:
    mots: list[_Mot]
    largeur: float
    derniere: bool


def _composer(mots: list[_Mot], echelle: float, espace: float, largeur: float,
              retrait: float, lignes_retrait: int) -> list[_Ligne]:
    """Répartit les mots en lignes ; les premières laissent la place à la lettrine."""
    lignes: list[_Ligne] = []
    courants: list[_Mot] = []
    occupe = 0.0

    def clore(derniere: bool) -> None:
        nonlocal courants, occupe
        lignes.append(_Ligne(courants, occupe, derniere))
        courants, occupe = [], 0.0

    def disponible() -> float:
        return largeur - (retrait if len(lignes) < lignes_retrait else 0)

    def placer(mot: _Mot) -> None:
        nonlocal occupe
        occupe += (espace if courants else 0) + mot.unites * echelle
        courants.append(mot)

    for mot in mots:
        if mot.retour:
            clore(True)
            continue
        if courants and occupe + espace + mot.unites * echelle > disponible():
            clore(False)
        # Un mot plus large que la page se coupe, plutôt que de déborder.
        while mot.unites * echelle > disponible() and len(mot.glyphes) > 1:
            debut = 1
            while debut < len(mot.glyphes) and sum(map(_avance, mot.glyphes[:debut + 1])) * echelle <= disponible():
                debut += 1
            placer(_Mot(mot.glyphes[:debut], mot.couleur, mot.capitale))
            clore(False)
            mot = _Mot(mot.glyphes[debut:], mot.couleur)
        placer(mot)
    clore(True)
    return lignes


# ─── Les ornements ───────────────────────────────────────────────────────────────────────


def _feuille(x: float, y: float, taille: float, angle: float, couleur: str) -> str:
    s = taille
    trait = _n(max(0.6, s * 0.05))
    return (
        f'<g transform="translate({_n(x)} {_n(y)}) rotate({_n(math.degrees(angle))})">'
        f'<path d="M0 0H{_n(s * .32)}" stroke="{VERT}" stroke-width="{_n(max(.7, s * .08))}"/>'
        f'<path d="M{_n(s * .3)} 0C{_n(s * .25)} {_n(-s * .42)} {_n(s * .62)} {_n(-s * .42)} {_n(s * 1.2)} 0'
        f'C{_n(s * .62)} {_n(s * .42)} {_n(s * .25)} {_n(s * .42)} {_n(s * .3)} 0Z" fill="{couleur}" '
        f'stroke="{ENCRE}" stroke-opacity=".55" stroke-width="{trait}"/>'
        f'<path d="M{_n(s * .38)} 0H{_n(s * .95)}" stroke="#fff5d7" stroke-opacity=".7" stroke-width="{trait}"/>'
        "</g>"
    )


def _besant(x: float, y: float, r: float) -> str:
    return (f'<circle cx="{_n(x)}" cy="{_n(y)}" r="{_n(r)}" fill="{OR}" stroke="{OR_SOMBRE}" '
            f'stroke-width="{_n(max(.5, r * .15))}"/>')


def _lierre(x1: float, y1: float, x2: float, y2: float, bande: float, alea: random.Random) -> str:
    """Une tige de lierre ondulante, qui tient dans la largeur de sa marge."""
    longueur = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / longueur, (y2 - y1) / longueur
    periodes = max(1, round(longueur / (bande * 1.5)))
    periode = longueur / periodes
    amplitude = bande * 0.14

    def point(d: float) -> tuple[float, float]:
        onde = math.sin(d / periode * 2 * math.pi) * amplitude
        return x1 + ux * d - uy * onde, y1 + uy * d + ux * onde

    pas = max(2.0, bande / 16)
    points = [point(i * pas) for i in range(int(longueur / pas) + 1)]
    trace = "M" + "L".join(f"{_n(x)} {_n(y)}" for x, y in points)
    morceaux = [f'<path d="{trace}" fill="none" stroke="{VERT}" stroke-width="{_n(max(.9, bande * .03))}"/>']

    base = math.atan2(uy, ux)
    couleurs = (BLEU, ROUGE, VERT, VERT)
    for i in range(periodes * 2):
        d = periode * (i / 2 + 0.25)
        cote = -1 if i % 2 else 1
        # La feuille part en biais, dans le sens de la tige, comme sur une vraie branche.
        angle = base + cote * (math.pi * 0.32 + (alea.random() - 0.5) * 0.35)
        morceaux.append(_feuille(*point(d), bande * 0.27, angle, alea.choice(couleurs)))
        if i % 2:
            morceaux.append(_besant(*point(d + periode / 4), max(1.2, bande * 0.045)))
    return "".join(morceaux)


def _coin(x: float, y: float, taille: float, alea: random.Random) -> str:
    marge = taille * 0.12
    interieur = taille - 2 * marge
    cx, cy, r = x + taille / 2, y + taille / 2, taille * 0.13
    lobes = "".join(
        f'<circle cx="{_n(cx + dx * r)}" cy="{_n(cy + dy * r)}" r="{_n(r)}" fill="{OR}"/>'
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
    )
    return (
        f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(taille)}" height="{_n(taille)}" fill="{OR}"/>'
        f'<rect x="{_n(x + marge)}" y="{_n(y + marge)}" width="{_n(interieur)}" height="{_n(interieur)}" '
        f'fill="{alea.choice((BLEU, ROUGE))}"/>{lobes}'
    )


def _lettrine(lettre: str, x: float, y: float, taille: float, ids: "_Glyphes", alea: random.Random) -> str:
    bord = taille * 0.06
    interieur = taille - 2 * bord
    fond, accent = (BLEU, ROUGE) if alea.random() < 0.5 else (ROUGE, BLEU)
    morceaux = [
        f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(taille)}" height="{_n(taille)}" fill="{OR}"/>',
        f'<rect x="{_n(x + bord)}" y="{_n(y + bord)}" width="{_n(interieur)}" height="{_n(interieur)}" fill="{fond}"/>',
    ]
    # Filigrane blanc : des volutes dans les quatre coins du fond.
    for fx, fy in ((.18, .18), (.82, .18), (.18, .82), (.82, .82)):
        cx, cy = x + bord + interieur * fx, y + bord + interieur * fy
        points = []
        for i in range(70):
            t = i * 0.2
            r = taille * 0.0095 * t
            points.append(f"{_n(cx + math.cos(t) * r)} {_n(cy + math.sin(t) * r)}")
        morceaux.append(f'<path d="M{"L".join(points)}" fill="none" stroke="#fff8e1" stroke-opacity=".8" '
                        f'stroke-width="{_n(max(.7, taille * .012))}"/>')
    for dx, dy in ((.5, .1), (.5, .9), (.1, .5), (.9, .5)):
        morceaux.append(f'<circle cx="{_n(x + bord + interieur * dx)}" cy="{_n(y + bord + interieur * dy)}" '
                        f'r="{_n(taille * .03)}" fill="{accent}"/>')

    # La lettre, centrée sur son dessin réel : d'abord son contour sombre, puis l'or.
    glyphe = formes(lettre)[0]
    fonte = _fonte()
    x0, y0, x1, y1 = fonte["glyphes"][glyphe].get("b", (0, 0, 0, 0))
    echelle = taille * 0.8 / fonte["unites"]
    px = x + taille / 2 - (x0 + x1) / 2 * echelle
    py = y + taille / 2 - (y0 + y1) / 2 * echelle
    placement = f'transform="translate({_n(px)} {_n(py)}) scale({echelle:.5f})"'
    reference = f'xlink:href="#{ids.id(glyphe)}"'
    morceaux.append(f'<use {reference} {placement} fill="none" stroke="#1e0f05" stroke-opacity=".9" '
                    f'stroke-linejoin="round" stroke-width="{_n(taille * .035 / echelle)}"/>')
    morceaux.append(f'<use {reference} {placement} fill="{OR}"/>')
    return "".join(morceaux)


def _escargot(x: float, y: float, taille: float) -> str:
    """L'escargot des marges, habitué des manuscrits."""
    s = taille
    corne = "".join(
        f'<path d="M{_n(x + s * 1.15)} {_n(y - s * .5)}L{_n(x + s * (1.3 + dx))} {_n(y - s * .95)}" '
        f'stroke="{ENCRE}" stroke-width="{_n(s * .06)}" stroke-linecap="round"/>'
        for dx in (.15, -.15)
    )
    cy = y - s * 0.45
    spirale = "L".join(
        f"{_n(x + math.cos(i * .25) * s * .038 * i * .25)} {_n(cy + math.sin(i * .25) * s * .038 * i * .25)}"
        for i in range(60)
    )
    return (
        f'<path d="M{_n(x - s * 1.15)} {_n(y)}Q{_n(x)} {_n(y + s * .28)} {_n(x + s * .95)} {_n(y)}'
        f'Q{_n(x + s * 1.3)} {_n(y - s * .1)} {_n(x + s * 1.15)} {_n(y - s * .5)}" fill="none" stroke="{ENCRE}" '
        f'stroke-width="{_n(s * .26)}" stroke-linecap="round"/>{corne}'
        f'<circle cx="{_n(x)}" cy="{_n(cy)}" r="{_n(s * .62)}" fill="{OR}" stroke="{OR_SOMBRE}" '
        f'stroke-width="{_n(s * .07)}"/>'
        f'<path d="M{spirale}" fill="none" stroke="{ROUGE}" stroke-width="{_n(s * .07)}"/>'
    )


def _chat(x: float, y: float, hauteur: float) -> str:
    """Le chat des marges, en pleine toilette. Dessiné dans une boîte de 100 × 100."""
    poil, rayure, clair = "#7f94ab", "#50647b", "#ccd6e0"

    def forme(trace: str, couleur: str = poil) -> str:
        return f'<path d="{trace}" fill="{couleur}" stroke="{ENCRE}" stroke-width="2.6"/>'

    def rayures(traces: tuple[str, ...], couleur: str = rayure, epaisseur: float = 3) -> str:
        return "".join(f'<path d="{t}" fill="none" stroke="{couleur}" stroke-width="{epaisseur}"/>' for t in traces)

    croix = "".join(
        f'<path d="M{_n(68 - math.cos(a) * 4.5)} {_n(84 - math.sin(a) * 4.5)}'
        f'L{_n(68 + math.cos(a) * 4.5)} {_n(84 + math.sin(a) * 4.5)}" stroke="{ENCRE}" stroke-width="2.2"/>'
        for a in (i * math.pi / 4 + math.pi / 8 for i in range(4))
    )
    return (
        f'<g transform="translate({_n(x)} {_n(y - hauteur)}) scale({hauteur / 100:.4f})" '
        'stroke-linejoin="round" stroke-linecap="round">'
        # La queue, le long du sol.
        f'<path d="M26 94C5 101-22 100-26 80" fill="none" stroke="{ENCRE}" stroke-width="11"/>'
        f'<path d="M26 94C5 101-22 100-26 80" fill="none" stroke="{poil}" stroke-width="6.5"/>'
        # La patte arrière posée à plat sur le sol.
        + forme("M52 99L60 76C74 80 86 83 97 85Q109 84 110 92Q110 99 100 99Z")
        + rayures(("M82 84Q84 90 81 95", "M93 87Q95 92 92 97"))
        # Le corps, assis et arrondi.
        + forme("M30 99C4 92 2 50 26 30C38 20 54 28 56 44C60 66 66 90 58 99Z")
        + rayures(("M8 62Q18 62 23 69", "M12 44Q20 46 24 53", "M11 80Q21 78 27 84"))
        # La patte avant, qui fait levier.
        + forme("M24 66Q28 82 28 92Q20 93 20 99L42 99Q43 82 40 68Z")
        # La patte arrière dressée à la verticale : 90° avec celle du sol.
        + forme("M54 86C58 62 61 36 65 15Q64 3 75 3Q84 6 81 17C80 40 80 60 76 80Z")
        + rayures(("M63 42Q70 42 75 46", "M66 23Q72 23 77 27"))
        # Le derrière, à la jonction des deux pattes.
        + f'<ellipse cx="66" cy="83" rx="13" ry="12" fill="{clair}" stroke="{ENCRE}" stroke-width="2.6"/>'
        + croix
        # La langue, à l'ouvrage : elle sort de sous le museau.
        + forme("M38 62Q44 76 52 82Q60 86 60 78Q58 71 52 66Q50 62 50 56Z", "#d9413a")
        # La tête, plongée vers le derrière, les yeux fermés de pur contentement.
        + '<g transform="translate(-7 0)">'
        + forme("M23 37L25 18L39 29L50 24L62 12L62 36C66 48 62 62 52 70C42 74 28 62 23 37Z")
        + rayures(("M34 34Q37 41 36 46", "M44 31Q45 37 43 42"))
        + rayures(("M30 49Q34 53 38 49", "M45 47Q49 51 53 46"), ENCRE, 2.4)
        + "</g></g>"
    )


# ─── La page ─────────────────────────────────────────────────────────────────────────────


class _Glyphes:
    """Chaque lettre n'est décrite qu'une fois dans le SVG, puis réutilisée."""

    def __init__(self) -> None:
        self.ids: dict[str, str] = {}

    def id(self, glyphe: str) -> str:
        return self.ids.setdefault(glyphe, f"g{len(self.ids)}")

    def definitions(self) -> str:
        glyphes = _fonte()["glyphes"]
        return "".join(f'<path id="{i}" d="{glyphes[g]["d"]}"/>' for g, i in self.ids.items())


def _ecrire(glyphes: list[str | None], x: float, y: float, echelle: float, ids: _Glyphes) -> str:
    """Les glyphes d'un mot, à placer dans un groupe déjà mis à l'échelle."""
    morceaux = []
    position = x / echelle
    ligne = y / echelle
    for glyphe in glyphes:
        if glyphe and _fonte()["glyphes"][glyphe]["d"]:
            morceaux.append(f'<use xlink:href="#{ids.id(glyphe)}" x="{position:.0f}" y="{ligne:.0f}"/>')
        position += _avance(glyphe)
    return "".join(morceaux)


def _texte_xml(texte: str) -> str:
    """Le texte pour la balise <title> : échappé, sans les caractères interdits en XML."""
    return escape("".join(c for c in texte if c in "\t\n\r" or (" " <= c <= "퟿") or ("" <= c <= "�") or c > "￿"))


def dessiner(texte: str, *, seed: int | None = None, largeur: int = LARGEUR_PAR_DEFAUT, bete: str = "escargot") -> str:
    """Dessine un texte tel quel, sans le transmogrifier. Voir `enluminure`."""
    if not LARGEUR_MIN <= largeur <= LARGEUR_MAX:
        raise ValueError(f"largeur hors limites : {largeur!r} (attendu : {LARGEUR_MIN} à {LARGEUR_MAX})")
    if bete not in ("escargot", "chat"):
        raise ValueError(f"bête inconnue : {bete!r} (attendu : escargot ou chat)")

    alea = random.Random(seed)
    W = float(largeur)
    marge = max(50.0, W * 0.125)  # du bord de la page au filet rouge
    retrait_page = max(10.0, W * 0.022)  # du filet rouge au texte
    gauche = marge + retrait_page
    largeur_texte = W - 2 * gauche
    haut = marge + retrait_page
    unites = _fonte()["unites"]

    propre = unicodedata.normalize("NFC", texte).strip()
    lettrine = propre[0] if propre and propre[0].isalpha() and formes(propre[0])[0] else ""
    mots = _mots(propre[len(lettrine):])
    lignes_lettrine = 3 if lettrine else 0

    # Le corps diminue seulement si le texte dépasserait la hauteur maximale.
    taille = min(46.0, max(17.0, W * 0.038))
    while True:
        echelle = taille / unites
        interligne = taille * 1.32
        cote_lettrine = 3 * interligne - taille * 0.25
        blanc = taille * 0.3
        espace = _avance("space") * echelle
        retrait = cote_lettrine + blanc if lettrine else 0
        lignes = _composer(mots, echelle, espace, largeur_texte, retrait, lignes_lettrine)
        corps = max(len(lignes) * interligne, cote_lettrine if lettrine else 0)
        H = haut + corps + taille * 1.9 + retrait_page + marge
        if H <= HAUTEUR_MAX:
            break
        taille *= 0.8

    ids = _Glyphes()
    fond = [
        f'<rect width="{_n(W)}" height="{_n(H)}" fill="{VELIN}"/>',
        f'<rect width="{_n(W)}" height="{_n(H)}" fill="url(#vignette)"/>',
    ]
    # Quelques taches sur le vélin.
    for _ in range(int(min(300, W * H / 8000))):
        fond.append(f'<circle cx="{_n(alea.random() * W)}" cy="{_n(alea.random() * H)}" '
                    f'r="{_n(0.4 + alea.random() * 1.6)}" fill="#6e4b23" fill-opacity="{0.03 + alea.random() * 0.07:.2f}"/>')

    # Le cadre : filets, tiges de lierre et coins.
    bord = marge * 0.1
    bande = marge - bord
    coin = bande * 0.7
    c = bord + (bande - coin) / 2
    milieu = bord + bande / 2
    degage = c + coin + bande * 0.08
    cadre = [
        f'<rect x="{_n(bord)}" y="{_n(bord)}" width="{_n(W - 2 * bord)}" height="{_n(H - 2 * bord)}" fill="none" '
        f'stroke="{OR}" stroke-width="{_n(max(1.5, marge * .03))}"/>',
        f'<rect x="{_n(marge)}" y="{_n(marge)}" width="{_n(W - 2 * marge)}" height="{_n(H - 2 * marge)}" fill="none" '
        f'stroke="{ROUGE}" stroke-opacity=".55" stroke-width="{_n(max(1, marge * .012))}"/>',
        _lierre(degage, milieu, W - degage, milieu, bande, alea),
        _lierre(degage, H - milieu, W - degage, H - milieu, bande, alea),
        _lierre(milieu, degage, milieu, H - degage, bande, alea),
        _lierre(W - milieu, degage, W - milieu, H - degage, bande, alea),
    ]
    cadre += [_coin(x, y, coin, alea) for x, y in ((c, c), (W - c - coin, c), (c, H - c - coin), (W - c - coin, H - c - coin))]

    page = list(fond) + cadre
    if lettrine:
        page.append(_lettrine(lettrine, gauche, haut, cote_lettrine, ids, alea))

    # Le texte, justifié, avec une capitale de couleur en tête de phrase.
    ecrit = []
    for i, ligne in enumerate(lignes):
        decale = bool(lettrine) and i < lignes_lettrine
        x = gauche + (retrait if decale else 0)
        disponible = largeur_texte - (retrait if decale else 0)
        # Une ligne trop creuse reste alignée à gauche plutôt que d'ouvrir des trous.
        extra = (disponible - ligne.largeur) / (len(ligne.mots) - 1) if len(ligne.mots) > 1 else 0
        if ligne.derniere or extra > espace * 2.2:
            extra = 0
        y = haut + i * interligne + taille
        for mot in ligne.mots:
            if mot.capitale and mot.glyphes:
                ecrit.append(f'<g fill="{mot.capitale}">{_ecrire(mot.glyphes[:1], x, y, echelle, ids)}</g>')
                suite_x = x + _avance(mot.glyphes[0]) * echelle
                ecrit.append(f'<g fill="{mot.couleur}">{_ecrire(mot.glyphes[1:], suite_x, y, echelle, ids)}</g>')
            else:
                ecrit.append(f'<g fill="{mot.couleur}">{_ecrire(mot.glyphes, x, y, echelle, ids)}</g>')
            x += mot.unites * echelle + espace + extra
    page.append(f'<g transform="scale({echelle:.5f})">{"".join(ecrit)}</g>')

    # La fin de la page : le colophon, à l'encre rouge, et la bête des marges.
    pied = H - marge - retrait_page * 0.8
    taille_colophon = max(13.0, taille * 0.62)
    echelle_colophon = taille_colophon / unites
    colophon = formes("Cy") + ["space"] + formes("finist") + ["space"] + formes("ce") + ["space"] + formes("parchemin")
    x_colophon = W - gauche - sum(_avance(g) for g in colophon) * echelle_colophon
    page.append(f'<g transform="scale({echelle_colophon:.5f})" fill="{ROUGE}">'
                f'{_ecrire(colophon, x_colophon, pied, echelle_colophon, ids)}</g>')
    if bete == "chat":
        hauteur_chat = max(26.0, taille * 1.5)
        page.append(_chat(gauche + hauteur_chat * 0.3, pied + retrait_page * 0.45, hauteur_chat))
    else:
        page.append(_escargot(gauche + taille * 0.5, pied - taille * 0.04, max(8.0, taille * 0.36)))

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" role="img" '
        f'width="{_n(W)}" height="{_n(H)}" viewBox="0 0 {_n(W)} {_n(H)}">'
        f"<title>{_texte_xml(propre)}</title><defs>{_DEFS}{ids.definitions()}</defs>{''.join(page)}</svg>\n"
    )


def enluminure(phrase: str, *, seed: int | None = None, level: int = NIVEAU_PAR_DEFAUT,
               largeur: int = LARGEUR_PAR_DEFAUT) -> str:
    """Transmogrifie une phrase et la dessine en page de manuscrit : renvoie un document SVG.

    Même phrase + même `seed` + même `level` + même `largeur` = même dessin. `largeur` règle la
    mise en page : le texte occupe plus de place sur une page étroite.
    """
    if seed is None:
        seed = random.randrange(2**32)
    return dessiner(translate(phrase, seed=seed, level=level), seed=seed, largeur=largeur)
