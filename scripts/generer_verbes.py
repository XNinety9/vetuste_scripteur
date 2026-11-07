#!/usr/bin/env python3
"""Génère `vetuste_scripteur/verbes.json` à partir de verbecc.

verbecc n'est utile qu'ici, au développement : à l'exécution, le paquet lit le fichier généré et
n'a besoin d'aucune dépendance. À relancer après toute modification de la liste des verbes :

    uv run scripts/generer_verbes.py
"""

import json
import logging
import sys
import warnings
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from vetuste_scripteur.lexique import VERBES_SUBSTITUTS  # noqa: E402

SORTIE = RACINE / "vetuste_scripteur" / "verbes.json"

# Les verbes courants du français : ceux que le moteur reconnaît sans pronom devant
# (« mon ami travaille »). Les substituts et leurs cibles sont ajoutés automatiquement.
COURANTS = """
être avoir aller faire dire pouvoir vouloir savoir devoir venir prendre mettre croire
tenir sembler laisser rester passer porter entendre comprendre rendre connaître paraître vivre
mourir naître suivre écrire lire ouvrir fermer offrir couvrir recevoir apprendre appeler jeter
acheter vendre commencer finir choisir réussir réfléchir grandir vieillir nourrir remplir
obéir punir guérir agir bâtir saisir rougir pâlir répondre descendre monter perdre défendre
entendre tendre vendre mordre coudre battre mettre permettre promettre rompre vaincre conduire
construire détruire produire traduire cuire plaire taire craindre peindre joindre éteindre
peindre sentir mentir servir ressentir revenir devenir tenir retenir obtenir appartenir
contenir maintenir souvenir prévenir tourner retourner rentrer retrouver garder montrer
jouer gagner aider lever laver habiller coucher réveiller lever asseoir essayer employer
ennuyer appuyer espérer préférer répéter acheter mener amener emmener promener oublier
étudier apprécier remercier prier expliquer pratiquer compter conter écouter regarder
toucher sauter nager voyager changer ranger bouger mélanger arranger partager nager
placer lancer avancer annoncer prononcer effacer tracer pousser casser passer laisser
baisser dresser presser glisser fatiguer conseiller surveiller réparer préparer comparer
séparer décider inviter visiter quitter ajouter goûter coûter douter habiter hésiter
éviter noter présenter inventer ressembler rassembler trembler brûler couler rouler
appeler sourire conclure pleuvoir valoir voler fumer allumer aimer semer cacher attacher
marcher accepter accorder admirer adorer amuser arrêter assurer attraper augmenter
balayer bavarder blesser boucher bricoler calmer chauffer colorier commander composer
continuer corriger couper créer décorer déjeuner demeurer dépenser déranger désirer
dessiner deviner discuter disparaître apparaître reconnaître disposer dominer durer
échanger éclairer économiser embrasser emporter encourager enlever enseigner envier
épouser exister expliquer exprimer fabriquer féliciter fêter fixer former frotter
gaspiller gêner goûter gronder guider ignorer imaginer indiquer informer installer
intéresser jurer juger libérer livrer louer manquer mériter mesurer mouiller nommer
observer occuper organiser oser pardonner partager patiner pêcher peser planter
plier poser posséder pratiquer prêter profiter protéger proposer protester publier
raconter ramasser rappeler rater recommencer refuser regretter rejoindre remarquer
remplacer rencontrer renverser réparer repasser reposer respecter résoudre retirer
rêver saluer sauver sécher signer soigner sonner souffrir souhaiter soutenir tâcher
téléphoner tirer tricher troubler utiliser varier vérifier verser vider viser
vieillir zapper télécharger cliquer coder
"""


def _sans_pronom(conjugue: str) -> str:
    """« que j'aime » → « aime », « il a » → « a ». Tout ce qui précède le verbe disparaît."""
    return conjugue.split(" ")[-1].split("'")[-1]


def _temps(entrees: list[dict]) -> list[str | None]:
    """Les six formes d'un temps, dans l'ordre je, tu, il, nous, vous, ils."""
    formes: list[str | None] = [None] * 6
    for entree in entrees:
        rang = int(entree["p"]) - 1 + (3 if entree["n"] == "p" else 0)
        if formes[rang] is None and entree["c"]:
            formes[rang] = _sans_pronom(entree["c"][0])
    return formes


def _imperatif(entrees: list[dict]) -> list[str | None]:
    """L'impératif, dans l'ordre tu, nous, vous."""
    return [_sans_pronom(e["c"][0]) if e["c"] else None for e in entrees[:3]] + [None] * (3 - len(entrees[:3]))


def _participe_passe(entrees: list[dict]) -> list[str]:
    """Le participe passé, dans l'ordre masculin, masculin pluriel, féminin, féminin pluriel."""
    formes = {(e.get("g"), e.get("n")): e["c"][0] for e in entrees if e["c"]}
    base = formes.get(("m", "s")) or next(iter(formes.values()))
    return [
        base,
        formes.get(("m", "p"), base),
        formes.get(("f", "s"), base),
        formes.get(("f", "p"), base),
    ]


def conjuguer(conjugueur, verbe: str) -> dict:
    modes = json.loads(conjugueur.conjugate(verbe).to_json())["moods"]
    indicatif, subjonctif = modes["indicatif"], modes["subjonctif"]
    return {
        "ip": _temps(indicatif["présent"]),
        "ii": _temps(indicatif["imparfait"]),
        "if": _temps(indicatif["futur-simple"]),
        "is": _temps(indicatif["passé-simple"]),
        "cp": _temps(modes["conditionnel"]["présent"]),
        "sp": _temps(subjonctif["présent"]),
        "si": _temps(subjonctif["imparfait"]),
        "im": _imperatif(modes["imperatif"]["imperatif-présent"]),
        "pp": _participe_passe(modes["participe"]["participe-passé"]),
        "pr": modes["participe"]["participe-présent"][0]["c"][0],
    }


def main() -> int:
    logging.disable(logging.CRITICAL)
    warnings.filterwarnings("ignore")
    from verbecc import CompleteConjugator

    conjugueur = CompleteConjugator(lang="fr")
    verbes = set(COURANTS.split()) | set(VERBES_SUBSTITUTS) | set(VERBES_SUBSTITUTS.values())

    table, echecs = {}, []
    for verbe in sorted(verbes):
        try:
            table[verbe] = conjuguer(conjugueur, verbe)
        except Exception as erreur:  # verbecc lève des exceptions variées sur les verbes inconnus
            echecs.append(f"{verbe} ({erreur})")

    SORTIE.write_text(json.dumps(table, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                      encoding="utf-8")
    print(f"{len(table)} verbes écrits dans {SORTIE.relative_to(RACINE)} ({SORTIE.stat().st_size // 1024} Ko)")
    if echecs:
        print("Échecs :", *echecs, sep="\n  ", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
