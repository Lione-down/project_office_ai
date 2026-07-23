FROM python:3.12.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/tmp

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        fonts-dejavu-core \
        fonts-noto-cjk \
        libreoffice-common \
        libreoffice-impress \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --chown=10001:10001 pyproject.toml ./
COPY --chown=10001:10001 app ./app
RUN pip install --no-cache-dir .

USER 10001:10001

CMD ["python", "-m", "app.services.quality.presentation.server"]
