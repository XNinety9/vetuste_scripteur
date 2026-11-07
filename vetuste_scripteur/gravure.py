"""La gravure : le texte seul en gothique, sans décor, dans un PNG noir et blanc de largeur donnée.

Elle est faite pour une imprimante thermique. Le PNG est en 1 bit : aucune nuance de gris à tramer,
donc le texte reste net. Aucune dépendance non plus : les lettres sont rastérisées ici même.
"""

import math
import random
import re
import struct
import unicodedata
import zlib
from functools import lru_cache

from .enluminure import LARGEUR_MAX, LARGEUR_MIN, _avance, _composer, _fonte, _mots
from .moteur import NIVEAU_PAR_DEFAUT, translate

HAUTEUR_MAX = 10000  # Printr refuse de décoder une image plus haute
_CORPS_PAR_LARGEUR = 1 / 14  # 36 px sur les 512 points d'un ticket de 80 mm, soit 4,5 mm
_SOUS_LIGNES = 4  # échantillons verticaux par ligne de pixels
_SEUIL = 0.42  # un peu sous la moitié, pour que les déliés fins de la gothique ne disparaissent pas
_SEGMENTS_PAR_COURBE = 6
_COMMANDE = re.compile(r"([MLHVQZ])|(-?\d+)")


@lru_cache(maxsize=None)
def _contours(glyphe: str) -> tuple[tuple[float, float, float, float], ...]:
    """Le tracé d'un glyphe, aplati en segments, en unités de la fonte."""
    jetons = [c or int(n) for c, n in _COMMANDE.findall(_fonte()["glyphes"][glyphe]["d"])]
    segments = []
    x = y = depart_x = depart_y = 0
    commande = ""
    i = 0
    while i < len(jetons):
        # Le format omet la lettre quand une commande se répète (après M, c'est un L implicite).
        if isinstance(jetons[i], str):
            commande = jetons[i]
            i += 1
        if commande == "M":
            x, y = depart_x, depart_y = jetons[i], jetons[i + 1]
            i += 2
            commande = "L"
        elif commande in ("L", "H", "V"):
            if commande == "L":
                nx, ny = jetons[i], jetons[i + 1]
                i += 2
            elif commande == "H":
                nx, ny = jetons[i], y
                i += 1
            else:
                nx, ny = x, jetons[i]
                i += 1
            segments.append((x, y, nx, ny))
            x, y = nx, ny
        elif commande == "Q":
            cx, cy, nx, ny = jetons[i:i + 4]
            i += 4
            ax, ay = x, y
            for pas in range(1, _SEGMENTS_PAR_COURBE + 1):
                t = pas / _SEGMENTS_PAR_COURBE
                bx = (1 - t) ** 2 * x + 2 * t * (1 - t) * cx + t * t * nx
                by = (1 - t) ** 2 * y + 2 * t * (1 - t) * cy + t * t * ny
                segments.append((ax, ay, bx, by))
                ax, ay = bx, by
            x, y = nx, ny
        else:  # Z
            if (x, y) != (depart_x, depart_y):
                segments.append((x, y, depart_x, depart_y))
            x, y = depart_x, depart_y
    return tuple(segments)


def _rasteriser(glyphe: str, echelle: float) -> tuple[int, int, int, list[int]]:
    """Un glyphe en pixels : décalage x et y, largeur, et une ligne de bits par ligne de pixels."""
    segments = [(a * echelle, b * echelle, c * echelle, d * echelle) for a, b, c, d in _contours(glyphe)]
    if not segments:
        return 0, 0, 0, []
    x0 = math.floor(min(min(s[0], s[2]) for s in segments))
    x1 = math.ceil(max(max(s[0], s[2]) for s in segments))
    y0 = math.floor(min(min(s[1], s[3]) for s in segments))
    y1 = math.ceil(max(max(s[1], s[3]) for s in segments))
    largeur, hauteur = x1 - x0, y1 - y0
    if largeur <= 0 or hauteur <= 0:
        return 0, 0, 0, []

    # Pour chaque sous-ligne, là où les contours la croisent, et dans quel sens.
    croisements: list[list[tuple[float, int]]] = [[] for _ in range(hauteur * _SOUS_LIGNES)]
    for ax, ay, bx, by in segments:
        if ay == by:
            continue
        sens = 1 if by > ay else -1
        haut, bas = (ay, by) if by > ay else (by, ay)
        pente = (bx - ax) / (by - ay)
        premiere = max(0, math.ceil((haut - y0) * _SOUS_LIGNES - 0.5))
        derniere = min(len(croisements) - 1, math.ceil((bas - y0) * _SOUS_LIGNES - 0.5) - 1)
        for sous_ligne in range(premiere, derniere + 1):
            y = y0 + (sous_ligne + 0.5) / _SOUS_LIGNES
            croisements[sous_ligne].append((ax + (y - ay) * pente - x0, sens))

    lignes = []
    for ligne in range(hauteur):
        couverture = [0.0] * largeur
        for sous_ligne in range(ligne * _SOUS_LIGNES, (ligne + 1) * _SOUS_LIGNES):
            enroulement = 0
            debut = 0.0
            # Règle de remplissage « non nulle », celle des fontes TrueType.
            for x, sens in sorted(croisements[sous_ligne]):
                avant = enroulement
                enroulement += sens
                if avant == 0:
                    debut = x
                elif enroulement == 0:
                    premier, dernier = int(debut), min(largeur - 1, int(x))
                    if premier == dernier:
                        couverture[premier] += x - debut
                    else:
                        couverture[premier] += premier + 1 - debut
                        for case in range(premier + 1, dernier):
                            couverture[case] += 1.0
                        couverture[dernier] += x - dernier
        limite = _SEUIL * _SOUS_LIGNES
        bits = 0
        for valeur in couverture:
            bits = bits << 1 | (valeur >= limite)
        lignes.append(bits)
    return x0, y0, largeur, lignes


def _png(largeur: int, lignes: list[int]) -> bytes:
    """Un PNG en niveaux de gris sur 1 bit. Une ligne est un entier : le bit de poids fort à gauche."""
    def bloc(nom: bytes, contenu: bytes) -> bytes:
        return struct.pack(">I", len(contenu)) + nom + contenu + struct.pack(">I", zlib.crc32(nom + contenu))

    octets = (largeur + 7) // 8
    bourrage = octets * 8 - largeur
    plein = (1 << largeur) - 1
    # Dans ce format, un bit à 1 est blanc : on inverse, l'encre étant à 1 dans nos lignes.
    donnees = b"".join(b"\0" + ((plein ^ ligne) << bourrage).to_bytes(octets, "big") for ligne in lignes)
    entete = struct.pack(">IIBBBBB", largeur, len(lignes), 1, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", entete)
            + bloc(b"IDAT", zlib.compress(donnees, 9)) + bloc(b"IEND", b""))


def graver(texte: str, *, largeur: int) -> bytes:
    """Grave un texte tel quel, sans le transmogrifier. Voir `gravure`."""
    if not LARGEUR_MIN <= largeur <= LARGEUR_MAX:
        raise ValueError(f"largeur hors limites : {largeur!r} (attendu : {LARGEUR_MIN} à {LARGEUR_MAX})")

    unites = _fonte()["unites"]
    marge = max(4, largeur // 64)  # les lettres gothiques débordent un peu de leur chasse
    largeur_texte = largeur - 2 * marge
    mots = _mots(unicodedata.normalize("NFC", texte).strip())

    # Le corps diminue seulement si le texte dépasserait la hauteur maximale.
    taille = largeur * _CORPS_PAR_LARGEUR
    while True:
        echelle = taille / unites
        interligne = taille * 1.32
        espace = _avance("space") * echelle
        composees = _composer(mots, echelle, espace, largeur_texte, 0, 0)
        hauteur = math.ceil(marge * 2 + taille * 0.45 + len(composees) * interligne)
        if hauteur <= HAUTEUR_MAX:
            break
        taille *= 0.8

    plein = (1 << largeur) - 1
    lignes = [0] * hauteur
    glyphes: dict[str, tuple[int, int, int, list[int]]] = {}
    for rang, ligne in enumerate(composees):
        extra = (largeur_texte - ligne.largeur) / (len(ligne.mots) - 1) if len(ligne.mots) > 1 else 0
        # Une ligne trop creuse reste alignée à gauche plutôt que d'ouvrir des trous.
        if ligne.derniere or extra > espace * 2.2:
            extra = 0
        x = float(marge)
        ligne_de_base = round(marge + taille + rang * interligne)
        for mot in ligne.mots:
            position = x
            for glyphe in mot.glyphes:
                if glyphe is not None:
                    if glyphe not in glyphes:
                        glyphes[glyphe] = _rasteriser(glyphe, echelle)
                    dx, dy, l, rangees = glyphes[glyphe]
                    decalage = largeur - round(position) - dx - l
                    for j, bits in enumerate(rangees):
                        y = ligne_de_base + dy + j
                        if bits and 0 <= y < hauteur:
                            lignes[y] |= (bits << decalage if decalage >= 0 else bits >> -decalage) & plein
                position += _avance(glyphe) * echelle
            x += mot.unites * echelle + espace + extra
    return _png(largeur, lignes)


def gravure(phrase: str, *, largeur: int, seed: int | None = None, level: int = NIVEAU_PAR_DEFAUT) -> bytes:
    """Transmogrifie une phrase et la grave : renvoie un PNG noir et blanc de `largeur` pixels.

    Même phrase + même `seed` + même `level` + même `largeur` = même image.
    """
    if seed is None:
        seed = random.randrange(2**32)
    return graver(translate(phrase, seed=seed, level=level), largeur=largeur)
