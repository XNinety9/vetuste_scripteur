"""Vetuste Scripteur : transforme le français moderne en vieux français façon Les Visiteurs.

    from vetuste_scripteur import translate

    translate("Je mange une pomme")                  # une version au hasard
    translate("Je mange une pomme", seed=42)         # toujours la même
    translate("Je mange une pomme", level=3)         # façon grimoire illisible
    enluminure("Je mange une pomme", seed=42)        # une page de manuscrit, en SVG
    gravure("Je mange une pomme", largeur=512)       # le texte seul, en PNG noir et blanc

Aucune dépendance : seule la bibliothèque standard est utilisée.
"""

from .enluminure import enluminure
from .gravure import gravure
from .moteur import NIVEAU_PAR_DEFAUT, NIVEAUX, translate

__version__ = "1.1.1"
__all__ = ["NIVEAUX", "NIVEAU_PAR_DEFAUT", "__version__", "enluminure", "gravure", "translate"]
