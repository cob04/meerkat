FROM alpine:3.21 AS css

RUN apk add --no-cache curl libstdc++ libgcc \
    && curl -sLO https://github.com/tailwindlabs/tailwindcss/releases/download/v4.1.3/tailwindcss-linux-x64-musl \
    && chmod +x tailwindcss-linux-x64-musl \
    && mv tailwindcss-linux-x64-musl /usr/local/bin/tailwindcss

WORKDIR /app
COPY src/ /app/
RUN tailwindcss -i ./assets/css/input.css -o ./assets/css/tailwind.out.css --minify


FROM python:3.14-slim AS development

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    APP_DIR=/opt/meerkat

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev librdkafka-dev gcc

RUN groupadd --gid 1000 meerkat \
    && useradd --uid 1000 --gid meerkat --shell /bin/bash --create-home meerkat

WORKDIR $APP_DIR

COPY src/pyproject.toml src/uv.lock* ./src/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --project src --frozen --extra dev \
    && chown -R meerkat:meerkat /opt/venv

COPY src/ ./src/
RUN chown -R meerkat:meerkat $APP_DIR

ENV PATH="/opt/venv/bin:$PATH"

USER meerkat
WORKDIR ${APP_DIR}/src

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]


FROM development AS production

USER root

COPY src/pyproject.toml src/uv.lock* /opt/meerkat/src/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --project src --frozen --no-dev \
    && chown -R meerkat:meerkat /opt/venv

COPY src/ /opt/meerkat/src/
COPY --from=css /app/assets/css/tailwind.out.css /opt/meerkat/src/assets/css/tailwind.out.css

RUN DJANGO_SETTINGS_MODULE=conf.settings.prod \
    DJANGO_SECRET_KEY=build-only \
    POSTGRES_PASSWORD=build-only \
    ALLOWED_HOSTS=localhost \
    python /opt/meerkat/src/manage.py collectstatic --noinput --ignore input.css

RUN chown -R meerkat:meerkat /opt/meerkat

USER meerkat
WORKDIR /opt/meerkat/src

CMD ["gunicorn", "conf.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
