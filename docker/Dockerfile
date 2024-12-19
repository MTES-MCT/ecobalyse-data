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

# allow to update the image if the source repo is updated
# ADD https://api.github.com/repos/ccomb/brightway2-io/git/refs/tags/ccomb-6 bw2-io.json
# ADD https://api.github.com/repos/brightway-lca/brightway2-parameters/git/refs/tags/1.1.0 bw2-parameters.json
# ADD https://api.github.com/repos/brightway-lca/brightway2-data/git/refs/tags/4.0.dev42 bw2-data.json
# ADD https://api.github.com/repos/brightway-lca/brightway2-calc/git/refs/tags/2.0.dev17 bw2-calc.json
# ADD https://api.github.com/repos/brightway-lca/brightway2-analyzer/git/refs/tags/0.11.7 bw2-analyzer.json
# ADD https://api.github.com/repos/brightway-lca/bw_projects/git/refs/tags/v2.1.0 bw_projects.json


COPY package.json .
COPY package-lock.json .


ENV VIRTUAL_ENV=/home/ecobalyse/ecobalyse-data/.docker/uv/venv
ENV UV_PROJECT_ENVIRONMENT=/home/ecobalyse/ecobalyse-data/.docker/uv/venv
RUN npm ci


USER root

COPY docker/simapro-biosphere.json /opt/conda/lib/python3.11/site-packages/bw2io/data/
COPY docker/entrypoint.sh /

# VOLUME .
ENTRYPOINT ["/entrypoint.sh"]
