# syntax=docker/dockerfile:1
FROM docker.io/kalilinux/kali-rolling:latest
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv ca-certificates \
        # general utils
        git wget curl file unzip jq openssl \
        # network 
        nmap iputils-ping tshark tcpdump ngrep whois dnsutils net-tools \
        # general recon
        nikto whatweb wafw00f theharvester dnsrecon sslscan \
        # fuzzing
        ffuf dirb sqlmap john hashcat hydra wordlists \
        # exploitation
        exploitdb metasploit-framework socat netcat-traditional \
    && rm -rf /usr/share/doc/* /usr/share/man/* /usr/share/locale/* \
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

RUN rm -f /etc/ssh/ssh_host_*_key /etc/ssh/ssh_host_*_key.pub \
    /etc/ssl/private/ssl-cert-snakeoil.key \
    /var/lib/inetsim/certs/default_key.pem

RUN useradd --create-home --home-dir /home/aiops --shell /bin/bash aiops \
    && mkdir -p /home/aiops/.local/share/ai_ops \
    && chown -R aiops:aiops /home/aiops/.local/share/ai_ops /opt/ai-ops
ENV HOME=/home/aiops
USER aiops

CMD ["python", "-m", "ai_ops.api.run"]