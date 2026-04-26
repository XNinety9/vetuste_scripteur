FROM python:3.12-slim

WORKDIR /app

# Dépendances Python
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn>=0.30" \
    "spacy>=3.8" \
    "verbecc>=2.0" \
    "https://github.com/explosion/spacy-models/releases/download/fr_core_news_sm-3.8.0/fr_core_news_sm-3.8.0-py3-none-any.whl"

# Pré-entraîne le modèle verbecc pendant le build (évite ~5s au démarrage)
RUN python -c "\
import warnings, logging; \
warnings.filterwarnings('ignore'); \
logging.disable(logging.CRITICAL); \
from verbecc import CompleteConjugator; \
CompleteConjugator(lang='fr')"

COPY main.py .

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
