# Changelog

## 1.1.0

### Reusable component

- The engine is now a dependency-free Python package: `from vetuste_scripteur import translate`.
- spaCy and verbecc are gone at runtime. Verbs are recognised from their context, and conjugations
  are read from a generated table. The installed size goes from about 486 MB to about 320 KB.
- New `vetuste-scripteur` command with `--json`, `--seed`, `--niveau` and standard input.
- New single-file build: `scripts/construire_pyz.py` produces `dist/vetuste-scripteur.pyz`.
- The single-file build is reproducible and comes with its checksum. A tag publishes it as a GitHub
  release, and `integration/printr/` explains how to plug it into Printr.
- FastAPI is now optional, behind the `web` extra.
- Python 3.11 or later is enough (3.14 was required).
- Now licensed under Apache 2.0, with a NOTICE file for third-party fonts and data.

### New features

- `seed` makes a result reproducible.
- `level` sets how aged the text looks, from 0 (vocabulary only) to 3 (unreadable grimoire).
- Web page: aging slider, new draw button, share link replaying the same result, parchment image.
- Illuminated manuscript page, with a gilded drop cap, an ivy border and rubrics: `enluminure()` in
  Python, `--svg` on the command line, `GET /enluminure.svg` on the API, and an option on the web
  page. The result is a self-contained SVG with no dependency, and the drawing follows the seed.
- Thermal printer output: the text alone in blackletter, as a 1-bit black and white PNG of a given
  width, with no dependency: `gravure()` in Python, `--png --largeur` on the command line and
  `GET /enluminure.png` on the API.
- Interjections can now end a sentence, and each sentence can get its own.
- Larger vocabulary, with plurals and feminine forms, and 14 more verbs.

### Fixes

- Conjugation: no more `Je j'haranguoy`. Present tense is no longer mistaken for the future
  (`vous entrez`) or the imperfect (`je vais`), and the conditional stays conditional.
- Past participles are now replaced (`j'ai mangé` → `j'ai ripaillé`).
- Elisions and contractions are redone around replaced words (`l'ami` → `le compagnon`,
  `de l'argent` → `du denier`).
- Replacements keep the original gender (`la route` → `la chaussée`, no more `la grand-chemin`).
- Homographs are told apart by context (`le son`, `un pas`, `il est mort`, `ce que`).
- The web page now works fully offline: its fonts ship with the package instead of coming from
  Google Fonts.
- Empty input no longer crashes one time in four.
- An interjection no longer lowercases a proper noun.
- The web API limits input to 5,000 characters and no longer blocks the server while translating.
- The Docker image now installs the exact versions from `uv.lock`.

### Breaking changes

- `main.py` is gone. Use `uvicorn vetuste_scripteur.web:app` and `vetuste-scripteur`.
- `/docs` and `/redoc` are gone, as they load their scripts from a CDN. The schema is still at
  `/openapi.json`.
- `mon`, `ton`, `son` stay as they are, except at level 3 (`le mien compagnon`).

## 1.0.0

First release.
