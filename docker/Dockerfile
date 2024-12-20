FROM ubuntu:latest

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV BRIGHTWAY2_DOCKER=1

ENV BRIGHTWAY2_DIR=/home/ecobalyse/ecobalyse-data/.docker/brightway
ENV BRIGHTWAY2_OUTPUT_DIR=/home/ecobalyse/ecobalyse-data/.docker/brightway/output
ENV XDG_CACHE_HOME=/home/ecobalyse/ecobalyse-data/.docker/xdg_cache
ENV UV_CACHE_DIR=/home/ecobalyse/ecobalyse-data/.docker/uv/cache

RUN apt update \
    && apt install -y build-essential gosu vim curl git \
    && git config --global --add safe.directory /home/ecobalyse/ecobalyse-data \
    && ldconfig


RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash -

RUN apt update \
    && apt install -y nodejs


USER ubuntu
WORKDIR /home/ubuntu

COPY package.json .
COPY package-lock.json .


ENV VIRTUAL_ENV=/home/ecobalyse/ecobalyse-data/.docker/uv/venv
ENV UV_PROJECT_ENVIRONMENT=/home/ecobalyse/ecobalyse-data/.docker/uv/venv
RUN npm ci


USER root

COPY docker/entrypoint.sh /

# VOLUME .
ENTRYPOINT ["/entrypoint.sh"]
