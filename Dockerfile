FROM python:3.12-slim

WORKDIR /app

# Les versions exactes de uv.lock : la page déployée est celle qui a été testée.
ENV UV_PYTHON_DOWNLOADS=never
RUN pip install --no-cache-dir "uv>=0.9"

COPY pyproject.toml uv.lock README.md ./
COPY vetuste_scripteur ./vetuste_scripteur

RUN uv sync --frozen --no-dev --extra web

EXPOSE 7860

CMD [".venv/bin/uvicorn", "vetuste_scripteur.web:app", "--host", "0.0.0.0", "--port", "7860"]
