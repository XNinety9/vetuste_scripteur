"""La page web et l'API JSON. Nécessite l'option `web` : `pip install "vetuste-scripteur[web]"`.

    uvicorn vetuste_scripteur.web:app
"""

import random
from importlib import resources
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from . import NIVEAU_PAR_DEFAUT, NIVEAUX, __version__, enluminure, gravure, translate
from .enluminure import LARGEUR_MAX, LARGEUR_MIN, LARGEUR_PAR_DEFAUT

LONGUEUR_MAX = 5000
SEED_MAX = 2**53 - 1  # le plus grand entier qu'un navigateur manipule sans perte

app = FastAPI(
    title="Vetuste Scripteur",
    description="Transforme le français moderne en vieux français façon Les Visiteurs",
    version=__version__,
    # Les pages /docs et /redoc de FastAPI chargent leurs scripts depuis un CDN : tout doit
    # fonctionner hors ligne. Le schéma reste disponible sur /openapi.json.
    docs_url=None,
    redoc_url=None,
)
app.mount("/fonts", StaticFiles(directory=Path(__file__).parent / "fonts"), name="fonts")

_PAGE = (
    resources.files(__package__)
    .joinpath("page.html")
    .read_text(encoding="utf-8")
    .replace("%%VERSION%%", __version__)
    .replace("%%LONGUEUR_MAX%%", str(LONGUEUR_MAX))
)


@app.get("/", response_class=HTMLResponse)
def page() -> str:
    return _PAGE


# Une route synchrone : FastAPI la confie à un fil d'exécution, et le serveur continue de répondre
# aux autres pendant le calcul.
@app.get("/translate")
def api_translate(
    phrase: Annotated[str, Query(max_length=LONGUEUR_MAX)],
    seed: Annotated[int | None, Query(ge=0, le=SEED_MAX)] = None,
    level: Annotated[int, Query(ge=min(NIVEAUX), le=max(NIVEAUX))] = NIVEAU_PAR_DEFAUT,
) -> dict:
    if seed is None:
        seed = random.randrange(2**32)
    return {
        "original": phrase,
        "result": translate(phrase, seed=seed, level=level),
        "seed": seed,
        "level": level,
    }


@app.get("/enluminure.svg")
def api_enluminure(
    phrase: Annotated[str, Query(max_length=LONGUEUR_MAX)],
    seed: Annotated[int | None, Query(ge=0, le=SEED_MAX)] = None,
    level: Annotated[int, Query(ge=min(NIVEAUX), le=max(NIVEAUX))] = NIVEAU_PAR_DEFAUT,
    largeur: Annotated[int, Query(ge=LARGEUR_MIN, le=LARGEUR_MAX)] = LARGEUR_PAR_DEFAUT,
) -> Response:
    if seed is None:
        seed = random.randrange(2**32)
    return Response(
        enluminure(phrase, seed=seed, level=level, largeur=largeur),
        media_type="image/svg+xml",
        headers={"X-Seed": str(seed)},
    )


@app.get("/enluminure.png")
def api_gravure(
    phrase: Annotated[str, Query(max_length=LONGUEUR_MAX)],
    largeur: Annotated[int, Query(ge=LARGEUR_MIN, le=LARGEUR_MAX)],
    seed: Annotated[int | None, Query(ge=0, le=SEED_MAX)] = None,
    level: Annotated[int, Query(ge=min(NIVEAUX), le=max(NIVEAUX))] = NIVEAU_PAR_DEFAUT,
) -> Response:
    """Le texte seul, sans décor, en noir et blanc : pour une imprimante thermique."""
    if seed is None:
        seed = random.randrange(2**32)
    return Response(
        gravure(phrase, largeur=largeur, seed=seed, level=level),
        media_type="image/png",
        headers={"X-Seed": str(seed)},
    )
