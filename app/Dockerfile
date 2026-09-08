FROM python:3.13-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN useradd -u 1000 -m app
WORKDIR /home/app
USER app

EXPOSE 8000
ENTRYPOINT ["uv", "run", "--with", "fastmcp==4.0.0", "--with", "duckdb==1.1.3", "python", "server.py"]
