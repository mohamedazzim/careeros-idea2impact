FROM python:3.12-slim AS test
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/tmp
ENV ENVIRONMENT=test

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-test.txt /tmp/requirements-test.txt
RUN pip install \
    --default-timeout=1000 \
    --retries=20 \
    --no-cache-dir \
    -r /tmp/requirements-test.txt

COPY . /app

CMD ["python", "-m", "pytest", "tests/", "-v", "--tb=short"]

FROM python:3.12-slim AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/tmp
ENV NLTK_DATA=/usr/local/share/nltk_data

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system appgroup && adduser --system --group appuser

RUN pip install poetry poetry-plugin-export
COPY ./pyproject.toml ./poetry.lock* /tmp/
RUN cd /tmp && poetry export -f requirements.txt --output requirements.txt --without-hashes \
    && grep -vE '^(gliner|torch|triton|nvidia|cuda|pytorch|flair|gensim|transformer|tokenizer|safetensor|accelerate|bpemb|sentencepiece|sentence-transformer|huggingface-hub)' requirements.txt > /tmp/runtime-reqs.txt

RUN pip install \
    --default-timeout=1000 \
    --retries=20 \
    --no-cache-dir \
    -r /tmp/runtime-reqs.txt \
    rank-bm25 nltk

RUN mkdir -p /usr/local/share/nltk_data \
    && python -c "import nltk; nltk.download('punkt', download_dir='/usr/local/share/nltk_data'); nltk.download('stopwords', download_dir='/usr/local/share/nltk_data')"

COPY . /app

RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/live || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
