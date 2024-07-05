# ----------- Agent API Docker File
# --build-arg arg1=v1 arg2=v2
ARG ollama-model=llama3
ARG ollama-endpoint=http://localhost:11434

# Kali Setup
FROM kalilinux/kali-rolling

RUN apt-get update && apt-get install -y \
    python3-pip ca-certificates python3 python3-wheel \
    nmap \
    gobuster \
    hashcat \
    exploitdb \
    sqlmap

# Setup API
RUN mkdir "api"
WORKDIR /api
COPY src ./src
COPY tools_settings ./tools_settings
COPY requirements.txt .

RUN pip3 install -r requirements.txt
RUN python3 -m spacy download en_core_web_lg   && \
    mkdir -p $HOME/.aiops/tools                && \
    mv tools_settings/* ~/.aiops/tools/

# Run API
ENV MODEL=${ollama-model}
ENV ENDPOINT=${ollama-endpoint}
EXPOSE 8000
CMD ["fastapi", "dev", "--host", "0.0.0.0", "./src/api.py"]

# docker build -t ai-ops:api-dev --build-arg ollama-endpoint=ENDPOINT .
# docker run -p 8000:8000 ai-ops:api-dev
