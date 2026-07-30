# ---- build: install locked deps + project into /app/.venv with uv ----
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app

# Dependencies first — this layer is cached until pyproject.toml / uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Then the package. Tests live beside the modules (foo_test.py); drop them.
COPY src ./src
RUN find src -name '*_test.py' -delete \
    && uv sync --frozen --no-dev

# ---- runtime: slim base, non-root, just the venv ----
FROM python:3.14-slim-bookworm

RUN useradd --create-home --uid 10001 rotato
COPY --from=build --chown=rotato:rotato /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER rotato

ENTRYPOINT ["rotato"]
