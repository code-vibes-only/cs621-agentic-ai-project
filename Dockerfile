# The same environment as `uv run`, built from the committed lockfile.
# Build:  docker build -t scheduler .
# Run:    docker run --rm --env-file .env -v "$PWD/results:/app/results" scheduler --arm d --scenarios dev-001
# Keys come in at run time with --env-file; they are never baked into the image.
FROM ghcr.io/astral-sh/uv:0.12.5-python3.12-trixie-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project

COPY scheduler ./scheduler
COPY data ./data

ENTRYPOINT ["uv", "run", "--frozen", "--no-dev", "python", "-m", "scheduler.eval"]
