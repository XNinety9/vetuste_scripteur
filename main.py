#!/usr/bin/env python3
"""Vetuste Scripteur — transforme le français moderne en vieux français façon Les Visiteurs."""

import json
import logging
import random
import re
import sys
import warnings

import spacy
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from verbecc import CompleteConjugator

logging.getLogger("verbecc").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

# ─── MODÈLES ──────────────────────────────────────────────────────────────────

nlp = spacy.load("fr_core_news_sm")

_conj = CompleteConjugator(lang="fr")
_conj_cache: dict[str, dict | None] = {}

app = FastAPI(
    title="Vetuste Scripteur",
    description="Transforme le français moderne en vieux français façon Les Visiteurs",
)

# ─── DICTIONNAIRES ────────────────────────────────────────────────────────────

WORD_SUBSTITUTIONS: dict[str, str | list[str]] = {
    # ── Pronoms & déterminants ──────────────────────────────────────────────
    "ce": "cestui",
    "cette": "ceste",
    "ces": "iceux",
    "celui": "ycelui",
    "celle": "ycelle",
    "ceux": "iceux",
    "celles": "icelles",
    # ── Adverbes ───────────────────────────────────────────────────────────
    "très": "fort",
    "beaucoup": "moult",
    "assez": "prou",
    "peu": "guère",
    "alors": "lors",
    "aussi": "pareillement",
    "peut-être": "par aventure",
    "souvent": "maintes fois",
    "jamais": "oneques",
    "maintenant": "à présent",
    "aujourd'hui": "hui",
    "vite": "incontinent",
    "soudain": "tout soudain",
    "vraiment": "en vérité",
    "oui": "voui",
    "non": "que nenni",
    "ensemble": "de compagnie",
    "encore": "encor",
    "déjà": "des ores",
    "toujours": "de tout temps",
    "autrefois": "jadis",
    "pourquoi": "pour quelle cause",
    "comment": "de quelle manière",
    # ── Négation ───────────────────────────────────────────────────────────
    "pas": "point",
    "rien": "néant",
    "jamais": "oneques",
    # ── Prépositions & conjonctions ─────────────────────────────────────────
    "dans": "en",
    "sur": "sus",
    "sous": "dessouz",
    "vers": "devers",
    "et": "y",
    "mais": "ains",
    "donc": "partant",
    # ── Possessifs ─────────────────────────────────────────────────────────
    "mon": "mien",
    "ma": "mienne",
    "ton": "tien",
    "ta": "tienne",
    "son": "sien",
    "sa": "sienne",
    "mes": "miens",
    "tes": "tiens",
    "ses": "siens",
    # ── Civilités ──────────────────────────────────────────────────────────
    "monsieur": ["sieur", "messire", "seigneur", "monseigneur"],
    "madame": ["dame", "damoiselle", "ma gente dame"],
    "mademoiselle": "damoiselle",
    "maître": "maistre",
    # ── Noms communs ───────────────────────────────────────────────────────
    "argent": "denier",
    "permission": "octroi",
    "autorisation": "octroi",
    "chanson": "ritournelle",
    "musique": "mélodie",
    "porte": "huis",
    "fenêtre": "croisée",
    "bateau": "nef",
    "navire": "nef",
    "cheval": "destrier",
    "épée": "flamberge",
    "roi": "suzerain",
    "reine": "suzeraine",
    "château": "manoir",
    "forêt": "sylve",
    "chemin": "sente",
    "route": "grand-chemin",
    "ami": "compagnon",
    "amie": "compagne",
    "ennemi": "félon",
    "voleur": ["larron", "brigand"],
    "menteur": "fourbe",
    "fou": "insensé",
    "idiot": ["manant", "goujat", "maraud"],
    "imbécile": ["manant", "goujat", "ribaud"],
    "paysan": "vilain",
    "soldat": "homme d'armes",
    "cuisinier": "queux",
    "médecin": "physicien",
    "miroir": "mire",
    "repas": "pitance",
    "festin": "ripaille",
    "fête": "liesse",
    "guerre": "mêlée",
    "bataille": "mêlée",
    "victoire": "triomphe",
    "défaite": "déconfiture",
    "travail": "labeur",
    "maison": "demeure",
    "appartement": "logis",
    "lit": "couche",
    "vin": "piquette",
    "bière": "cervoise",
    "nourriture": "victuailles",
    "vêtements": "atours",
    "vêtement": "accoutrement",
    "problème": "tracas",
    "situation": "conjoncture",
    "raison": "motif",
    "chance": "fortune",
    "malheur": "infortune",
    "bonheur": "félicité",
    "mort": "trépas",
    "danger": "péril",
    "peur": "épouvante",
    "courage": "vaillance",
    "lâcheté": "couardise",
    "trahison": "félonie",
    "rumeur": "ouï-dire",
    "secret": "mystère",
    "mensonge": "fourbe",
    "vérité": "vérité",
    "justice": "justice",
    "loi": "édit",
    # ── Adjectifs ──────────────────────────────────────────────────────────
    "grand": "gran",
    "grande": "gran",
    "mauvais": "meschant",
    "mauvaise": "meschante",
    "beau": "beau",
    "belle": "belle",
    "rouge": "vermeil",
    "bleu": "azur",
    "violet": "pourpre",
    "marron": "brun",
    "gauche": "senestre",
    "droite": "dextre",
    "drôle": "drolatique",
    "bizarre": "étrange",
    "rapide": "preste",
    "fort": "puissant",
    "lourd": "pesant",
    "léger": "léger",
    "chaud": "ardent",
    "froid": "glacial",
    "riche": "opulent",
    "pauvre": "misérable",
    # ── Objets modernes → anachronismes pittoresques ────────────────────────
    "voiture": ["carriole", "charriotte"],
    "automobile": "carriole",
    "camion": "charroi",
    "avion": "engin volant",
    "train": "attelage de fer",
    "vélo": "draisienne",
    "téléphone": "parchemin volant",
    "portable": "parchemin volant",
    "smartphone": "parchemin volant",
    "ordinateur": "grimoire lumineux",
    "internet": "réseau des savants",
    "télévision": "lanterne magique",
    "radio": "boîte à voix",
    "kilo": "livre",
    "kilomètre": "lieue",
    "restaurant": "taverne",
    "café": "taverne",
    "hôpital": "hôtel-Dieu",
    "pharmacie": "apothicairerie",
    "université": "sorbonne",
    # ── Directions ─────────────────────────────────────────────────────────
    "centre": "mitan",
    "nord": "septentrion",
    "sud": "midi",
    "ouest": "occident",
}

# Verbes modernes → substituts archaïques (doivent exister dans verbecc)
VERB_SUBSTITUTIONS: dict[str, str] = {
    "manger": "ripailler",
    "boire": "chopiner",
    "parler": "haranguer",
    "voir": "mirer",
    "dormir": "sommeiller",
    "travailler": "besogner",
    "donner": "octroyer",
    "courir": "galoper",
    "applaudir": "acclamer",
    "raconter": "narrer",
    "aimer": "chérir",
    "tromper": "duper",
    "crier": "brailler",
    "chercher": "guetter",
    "tomber": "choir",
    "tuer": "trucider",
    "voler": "dérober",
    "chanter": "entonner",
    "danser": "gambader",
    "pleurer": "geindre",
    "rire": "pouffer",
    "attendre": "patienter",
    "partir": "décamper",
    "arriver": "survenir",
    "entrer": "pénétrer",
    "sortir": "s'échapper",
    "diner": "mangeailler"
}

EXCLAMATIONS: list[str] = [
    "Passepoil !",
    "Corbleu !",
    "Ventrebleu !",
    "Morbleu !",
    "Palsambleu !",
    "Sacrebleu !",
    "Tudieu !",
    "Jarnicoton !",
    "Par ma foi !",
    "Par saint Gilles !",
    "Dieu me pardonne !",
    "Sus, manant !",
    "Mille sabords !",
    "Que diable !",
    "Ciel et terre !",
    "Fientrecul !"
]

# ─── CONJUGAISON ──────────────────────────────────────────────────────────────

# Le modèle spaCy fr_core_news_sm confond fréquemment l'imparfait avec le
# présent et se trompe sur le nombre. On détecte les formes directement par
# les terminaisons — bien plus fiable pour le français.
_IMP_ENDINGS = [
    (re.compile(r"aient$"), "3", "Plur"),
    (re.compile(r"iez$"),   "2", "Plur"),
    (re.compile(r"ions$"),  "1", "Plur"),
    (re.compile(r"ait$"),   "3", "Sing"),
    (re.compile(r"ais$"),   None, "Sing"),   # personne 1 ou 2, on garde spaCy
]

_FUT_ENDINGS = {
    "ront": ("3", "Plur"), "rez": ("2", "Plur"), "rons": ("1", "Plur"),
    "ra":   ("3", "Sing"), "ras": ("2", "Sing"), "rai":  ("1", "Sing"),
}

_VERBECC_MOOD_TENSE = {
    ("Ind", "Pres"): ("indicatif",    "présent"),
    ("Ind", "Imp"):  ("indicatif",    "imparfait"),
    ("Ind", "Fut"):  ("indicatif",    "futur-simple"),
    ("Ind", "Past"): ("indicatif",    "passé-simple"),
    ("Cnd", "Pres"): ("conditionnel", "présent"),
    ("Sub", "Pres"): ("subjonctif",   "présent"),
    ("Sub", "Imp"):  ("subjonctif",   "imparfait"),
}

# Formes archaïques d'être (pas dans verbecc, on gère à la main)
_ÊTRE_ARCHAIC: dict[tuple, str] = {
    ("1", "Sing", "Pres"): "estoy",
    ("2", "Sing", "Pres"): "estes",
    ("3", "Sing", "Pres"): "estoy",
    ("1", "Plur", "Pres"): "estons",
    ("2", "Plur", "Pres"): "estez",
    ("3", "Plur", "Pres"): "estoient",
    ("1", "Sing", "Imp"):  "estois",
    ("2", "Sing", "Imp"):  "estois",
    ("3", "Sing", "Imp"):  "estoit",
    ("1", "Plur", "Imp"):  "estions",
    ("2", "Plur", "Imp"):  "estiez",
    ("3", "Plur", "Imp"):  "estoient",
    ("1", "Sing", "Fut"):  "estray",
    ("3", "Sing", "Fut"):  "estra",
    ("3", "Plur", "Fut"):  "estront",
}

# Regex pour insérer un 's' avant un 't' solitaire précédé d'une voyelle
_VOWEL_T_RE = re.compile(
    r"([aeiouàâéèêëîïôùûüæœAEIOUÀÂÉÈÊËÎÏÔÙÛÜ])t(?![tr])"
)


def _apply_oy_pres(form: str) -> str:
    """Suffixe -oy pour les finales verbales du présent (style Les Visiteurs)."""
    if len(form) > 2 and form.endswith("e"):
        return form[:-1] + "oy"
    return form


def _archaic_chars(word: str) -> str:
    """Transformations orthographiques aléatoires : i→y, u→v, voyelle+t → voyelle+st."""
    # Insertion du 's' avant tout 't' solitaire précédé d'une voyelle
    word = _VOWEL_T_RE.sub(r"\1st", word)
    # Remplacement aléatoire lettre par lettre
    out = []
    for ch in word:
        if   ch == 'i' and random.random() < 0.40: out.append('y')
        elif ch == 'I' and random.random() < 0.40: out.append('Y')
        elif ch == 'u' and random.random() < 0.30: out.append('v')
        elif ch == 'U' and random.random() < 0.30: out.append('V')
        else: out.append(ch)
    return ''.join(out)


def _detect_features(token) -> dict:
    """Détecte temps/personne/nombre d'un verbe par ses terminaisons."""
    text  = token.text.lower()
    morph = token.morph

    verb_form = (morph.get("VerbForm") or ["Fin"])[0]

    if verb_form == "Inf":
        return {"kind": "inf"}

    # ── Imparfait détecté par terminaison (priorité sur le tag spaCy) ────────
    # spaCy confond parfois l'imparfait avec un participe passé (ex: "regardais")
    for pattern, person, number in _IMP_ENDINGS:
        if pattern.search(text):
            if person is None:
                person = (morph.get("Person") or ["1"])[0]
            return {"kind": "fin", "mood": "Ind", "tense": "Imp",
                    "person": person, "number": number}

    # ── Futur simple détecté par terminaison ─────────────────────────────────
    for suffix, (person, number) in _FUT_ENDINGS.items():
        if text.endswith(suffix) and len(text) > len(suffix) + 1:
            return {"kind": "fin", "mood": "Ind", "tense": "Fut",
                    "person": person, "number": number}

    # ── Participe (après les tests de terminaison, pour éviter les faux tags) ─
    if verb_form == "Part":
        past = (morph.get("Tense") or ["Pres"])[0] == "Past"
        return {"kind": "part", "past": past}

    # ── Présent et autres : spaCy + corrections heuristiques ─────────────────
    mood   = (morph.get("Mood")   or ["Ind"])[0]
    tense  = (morph.get("Tense")  or ["Pres"])[0]
    person = (morph.get("Person") or ["3"])[0]
    number = (morph.get("Number") or ["Sing"])[0]

    # Heuristique : verbe se terminant en -nt (mais pas -ient/-aient) → 3p
    if text.endswith("nt") and not text.endswith(("aient", "ient")):
        person, number = "3", "Plur"
    # Heuristique : verbe se terminant en consonne unique non-s → 3s
    elif text.endswith("t") and not text.endswith(("nt", "ait")):
        person, number = "3", "Sing"

    return {"kind": "fin", "mood": mood, "tense": tense,
            "person": person, "number": number}


def _get_conjugated(infinitive: str) -> dict | None:
    if infinitive in _conj_cache:
        return _conj_cache[infinitive]
    try:
        result = _conj.conjugate(infinitive)
        data = json.loads(result.to_json())
        _conj_cache[infinitive] = data
    except Exception:
        _conj_cache[infinitive] = None
    return _conj_cache[infinitive]


def _find_form(entries: list, person: str, number: str) -> str | None:
    n = "s" if number == "Sing" else "p"
    for entry in entries:
        if entry["p"] == person and entry["n"] == n:
            conjugated = entry["c"][0]
            parts = conjugated.split(" ", 1)
            return parts[1] if len(parts) > 1 else parts[0]
    return None


def _archaize_imparfait(form: str) -> str:
    form = re.sub(r"aient$", "oient", form)
    form = re.sub(r"ait$",   "oit",   form)
    form = re.sub(r"ais$",   "ois",   form)
    return form


def _conjugate_verb(token) -> str | None:
    """Conjugue le substitut archaïque au même temps/personne, avec finales archaïques."""
    feat  = _detect_features(token)
    lemma = token.lemma_
    text  = token.text

    # ── Infinitif ────────────────────────────────────────────────────────────
    if feat["kind"] == "inf":
        return VERB_SUBSTITUTIONS.get(lemma)

    # ── Participe ────────────────────────────────────────────────────────────
    if feat["kind"] == "part":
        target = VERB_SUBSTITUTIONS.get(lemma)
        if target:
            data = _get_conjugated(target)
            if data:
                key = "passé" if feat["past"] else "présent"
                entries = data["moods"].get("participe", {}).get(key, [])
                if entries:
                    return entries[0]["c"][0].split()[-1]
        return None

    # ── Forme finie ──────────────────────────────────────────────────────────
    mood, tense    = feat["mood"], feat["tense"]
    person, number = feat["person"], feat["number"]
    is_imp  = (mood == "Ind" and tense == "Imp")
    is_pres = (mood == "Ind" and tense == "Pres")

    # Être : table manuelle (verbecc ne connaît pas "estoir")
    if lemma == "être":
        form = _ÊTRE_ARCHAIC.get((person, number, tense))
        return form if form else text

    target = VERB_SUBSTITUTIONS.get(lemma)
    if target:
        data = _get_conjugated(target)
        if data:
            mood_key, tense_key = _VERBECC_MOOD_TENSE.get(
                (mood, tense), ("indicatif", "présent")
            )
            try:
                entries  = data["moods"][mood_key][tense_key]
                new_form = _find_form(entries, person, number)
                if new_form:
                    if is_imp:
                        return _archaize_imparfait(new_form)
                    if is_pres:
                        return _apply_oy_pres(new_form)
                    return new_form
            except KeyError:
                pass

    # Pas de substitut : archaïser les finales selon le temps
    if is_imp:
        return _archaize_imparfait(text)
    if is_pres:
        return _apply_oy_pres(text)

    return None


# ─── PIPELINE ─────────────────────────────────────────────────────────────────

def _preserve_case(original: str, replacement: str) -> str:
    if not replacement:
        return replacement
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def _transform_token(token) -> str:
    text = token.text
    lower = text.lower()

    if token.is_space or token.is_punct:
        return text

    # Verbes en premier
    if token.pos_ in ("VERB", "AUX"):
        new = _conjugate_verb(token)
        if new:
            return _archaic_chars(_preserve_case(text, new))

    # Substitution lexicale
    if lower in WORD_SUBSTITUTIONS:
        replacement = WORD_SUBSTITUTIONS[lower]
        if isinstance(replacement, list):
            replacement = random.choice(replacement)
        text = _preserve_case(text, replacement)
        return _archaic_chars(text)

    return _archaic_chars(text)


def _maybe_exclaim(text: str) -> str:
    """Ajoute une exclamation archaïque en début de phrase aléatoirement."""
    if random.random() < 0.25:
        excl = random.choice(EXCLAMATIONS)
        return excl + " " + text[0].lower() + text[1:]
    return text


def translate(phrase: str) -> str:
    doc = nlp(phrase)

    parts: list[str] = []
    for token in doc:
        parts.append(_transform_token(token) + token.whitespace_)

    result = "".join(parts).strip()
    result = _maybe_exclaim(result)
    return result


# ─── INTERFACE WEB ────────────────────────────────────────────────────────────

_HTML = """\
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vetuste Scripteur</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=UnifrakturMaguntia&family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background-color: #e8d5a3;
      background-image:
        radial-gradient(ellipse at 20% 10%, rgba(180,130,60,0.15) 0%, transparent 60%),
        radial-gradient(ellipse at 80% 90%, rgba(120,60,20,0.12) 0%, transparent 60%),
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='300' height='300' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
      font-family: 'Crimson Text', Georgia, serif;
      color: #2c1a0e;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2rem 1rem 4rem;
    }

    .parchment {
      width: 100%;
      max-width: 760px;
      background: linear-gradient(160deg, #fdf3d7 0%, #f5e6b8 50%, #ecdaa0 100%);
      border-radius: 4px;
      padding: 3rem 3.5rem;
      box-shadow:
        0 2px 4px rgba(0,0,0,0.25),
        0 8px 24px rgba(80,40,10,0.20),
        inset 0 0 60px rgba(180,130,60,0.08);
      border: 1px solid #c9a84c;
      position: relative;
    }

    /* Coins décoratifs */
    .parchment::before, .parchment::after {
      content: '✦';
      position: absolute;
      font-size: 1.2rem;
      color: #8b4513;
      opacity: 0.4;
    }
    .parchment::before { top: 1rem; left: 1.2rem; }
    .parchment::after  { bottom: 1rem; right: 1.2rem; }

    h1 {
      font-family: 'UnifrakturMaguntia', 'Palatino Linotype', serif;
      font-size: clamp(2.2rem, 6vw, 3.6rem);
      text-align: center;
      color: #5c1a0a;
      margin: 0 0 0.25rem;
      letter-spacing: 0.02em;
      text-shadow: 1px 2px 4px rgba(0,0,0,0.18);
    }

    .subtitle {
      text-align: center;
      font-style: italic;
      color: #7a4a20;
      font-size: 1.05rem;
      margin: 0 0 2rem;
    }

    .divider {
      text-align: center;
      color: #8b4513;
      font-size: 1.1rem;
      letter-spacing: 0.6em;
      margin: 1.5rem 0;
      opacity: 0.5;
    }

    label {
      display: block;
      font-weight: 600;
      font-size: 0.95rem;
      color: #5c2e0a;
      margin-bottom: 0.4rem;
      letter-spacing: 0.03em;
      text-transform: uppercase;
    }

    textarea {
      width: 100%;
      min-height: 110px;
      padding: 0.85rem 1rem;
      border: 1.5px solid #b8924a;
      border-radius: 3px;
      background: rgba(255,248,220,0.7);
      font-family: 'Crimson Text', Georgia, serif;
      font-size: 1.15rem;
      color: #2c1a0e;
      resize: vertical;
      transition: border-color 0.2s, box-shadow 0.2s;
      outline: none;
    }
    textarea:focus {
      border-color: #7a3a10;
      box-shadow: 0 0 0 2px rgba(122,58,16,0.15);
    }
    textarea::placeholder { color: #b09060; font-style: italic; }

    .btn-wrap { text-align: center; margin: 1.2rem 0 0; }

    button {
      padding: 0.7rem 2.4rem;
      background: linear-gradient(180deg, #7a2a0a 0%, #5c1a05 100%);
      color: #f5e6b8;
      border: 1px solid #3c0f02;
      border-radius: 3px;
      font-family: 'Crimson Text', Georgia, serif;
      font-size: 1.1rem;
      font-weight: 600;
      letter-spacing: 0.08em;
      cursor: pointer;
      transition: background 0.2s, transform 0.1s;
      box-shadow: 0 2px 6px rgba(0,0,0,0.25);
    }
    button:hover  { background: linear-gradient(180deg, #9a3a10 0%, #7a2a05 100%); }
    button:active { transform: translateY(1px); box-shadow: 0 1px 3px rgba(0,0,0,0.2); }

    .result-box {
      margin-top: 1.5rem;
      padding: 1.2rem 1.4rem;
      background: rgba(255,248,215,0.5);
      border: 1.5px solid #b8924a;
      border-radius: 3px;
      min-height: 80px;
    }
    .result-label {
      font-size: 0.85rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: #7a4a20;
      margin-bottom: 0.6rem;
    }
    .result-text {
      font-size: 1.25rem;
      font-style: italic;
      line-height: 1.6;
      color: #2c1a0e;
    }
    .result-placeholder { color: #b09060; font-style: italic; font-size: 1rem; }

    .spinner {
      display: none;
      width: 20px; height: 20px;
      border: 2px solid #c9a84c;
      border-top-color: #7a2a0a;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
      margin: 0.5rem auto;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    .examples {
      margin-top: 2rem;
      font-size: 0.9rem;
      color: #7a5030;
    }
    .examples strong { display: block; margin-bottom: 0.4rem; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; }
    .example-pill {
      display: inline-block;
      background: rgba(139,69,19,0.10);
      border: 1px solid rgba(139,69,19,0.25);
      border-radius: 2px;
      padding: 0.2rem 0.6rem;
      margin: 0.2rem;
      cursor: pointer;
      font-style: italic;
      transition: background 0.15s;
    }
    .example-pill:hover { background: rgba(139,69,19,0.20); }
  </style>
</head>
<body>
  <div class="parchment">
    <h1>Vetuste Scripteur</h1>
    <p class="subtitle">Transformez votre langue vulgaire en vieux parler d'antan !</p>
    <div class="divider">⚜ ⚜ ⚜</div>

    <form id="form">
      <label for="input">Français moderne</label>
      <textarea id="input" placeholder="Saisissez votre phrase ici…" autocomplete="off"></textarea>
      <div class="btn-wrap">
        <button type="submit">✦ Transmogrifier ✦</button>
      </div>
    </form>

    <div class="spinner" id="spinner"></div>

    <div class="result-box" id="result-box">
      <div class="result-label">Vieux parler</div>
      <div class="result-text" id="result-text">
        <span class="result-placeholder">Votre texte transformé apparaîtra ici…</span>
      </div>
    </div>

    <div class="divider" style="margin-top:2rem">· · ·</div>

    <div class="examples">
      <strong>Exemples à essayer</strong>
      <span class="example-pill">Je mange une pomme dans le jardin</span>
      <span class="example-pill">Mon ami travaille beaucoup</span>
      <span class="example-pill">Il ne buvait pas assez d'eau</span>
      <span class="example-pill">Tu regardais la télévision</span>
      <span class="example-pill">Madame, vous êtes très belle</span>
      <span class="example-pill">Je cherchais mon portable</span>
    </div>
  </div>

  <script>
    const form    = document.getElementById('form');
    const input   = document.getElementById('input');
    const result  = document.getElementById('result-text');
    const spinner = document.getElementById('spinner');

    // Clic sur un exemple
    document.querySelectorAll('.example-pill').forEach(pill => {
      pill.addEventListener('click', () => {
        input.value = pill.textContent;
        form.dispatchEvent(new Event('submit'));
      });
    });

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const phrase = input.value.trim();
      if (!phrase) return;

      spinner.style.display = 'block';
      result.innerHTML = '';

      try {
        const res  = await fetch('/translate?phrase=' + encodeURIComponent(phrase));
        const data = await res.json();
        result.textContent = data.result;
      } catch (err) {
        result.textContent = 'Erreur de transmogrification, messire.';
      } finally {
        spinner.style.display = 'none';
      }
    });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def ui():
    return _HTML


@app.get("/translate")
async def api_translate(phrase: str):
    return {"original": phrase, "result": translate(phrase)}


# ─── CLI ──────────────────────────────────────────────────────────────────────

_EXAMPLES = [
    "Je mange une pomme dans le jardin",
    "Mon ami travaille beaucoup et ne dort pas assez",
    "Il ne buvait pas assez d'eau",
    "Tu regardais la télévision",
    "Madame, vous êtes très belle",
    "Je cherchais mon portable",
    "Nous courions vers la voiture",
    "Elle chantait une belle chanson",
]

if __name__ == "__main__":
    if len(sys.argv) > 1:
        phrases = [" ".join(sys.argv[1:])]
    else:
        phrases = _EXAMPLES

    width = 60
    print("\n" + "═" * width)
    print("  Vetuste Scripteur".center(width))
    print("═" * width)

    for phrase in phrases:
        result = translate(phrase)
        print(f"\n  Moderne  : {phrase}")
        print(f"  Archaïque: {result}")

    print("\n" + "═" * width + "\n")
