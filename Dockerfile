FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system lakehouse \
    && useradd --system --gid lakehouse --create-home lakehouse

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

USER lakehouse

ENTRYPOINT ["retail-lakehouse"]
CMD ["--help"]

