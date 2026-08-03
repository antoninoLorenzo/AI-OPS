# syntax=docker/dockerfile:1

# docker build -f docker/Dockerfile -t ai-ops:api-dev .
# 
# docker run --rm -p 8000:8000 --env-file .env \
#     --volume ai-ops-data:/home/aiops/.local/share/ai_ops \
#     --cap-add=NET_RAW --cap-add=NET_ADMIN \
#     ai-ops:api-dev
# 
# Adding user-provided configs:
# --mount type=bind,source=/path/to/agent_config.json,target=/home/aiops/.local/share/ai_ops/agent_config.json,readonly
# --mount type=bind,source=/path/to/user_skills,target=/home/aiops/.local/share/ai_ops/user_skills,readonly
# notes: 
# * the files need to be word readable (644 and 755)
# * with SELinux it needs also `...,relabel=shared|private`
# 
FROM docker.io/kalilinux/kali-rolling:latest
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv ca-certificates git wget curl \
        kali-linux-headless seclists iputils-ping \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT="/opt/venv"
# `UV_COMPILE_BYTECODE=1` or `--compile-bytecode` compiles python source files to bytecode

WORKDIR /opt/ai-ops
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --group api --no-install-project --no-dev --frozen
COPY . .

RUN useradd --create-home --home-dir /home/aiops --shell /bin/bash aiops \
    && mkdir -p /home/aiops/.local/share/ai_ops \
    && chown -R aiops:aiops /home/aiops/.local/share/ai_ops /opt/ai-ops
ENV HOME=/home/aiops
USER aiops

EXPOSE 8000
CMD ["uvicorn", "ai_ops.api.api:app", "--host", "0.0.0.0", "--port", "8000"]