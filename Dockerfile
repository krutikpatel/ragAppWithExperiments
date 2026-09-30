# P3-13 (DEC-097): the answer API. Local only — `docker compose up`.
# The frozen corpus, the dense index and the results caches are MOUNTED (gitignored, large,
# rebuilt from pinned inputs); the image holds code, configs, prompts and the golden slice.
FROM python:3.11-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /bin/uv
COPY pyproject.toml README.md ./
COPY rag ./rag
COPY configs ./configs
COPY prompts ./prompts
COPY eval ./eval
COPY data/authored ./data/authored
# Editable, so `rag.paths` resolves data/, indexes/ and results/ under /app, where they are mounted.
RUN uv pip install --system --no-cache -e ".[api]"
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "rag.api:app", "--host", "0.0.0.0", "--port", "8000"]
