# ----------- Agent API Docker File
# BUILD: ~ 0.8 GB
# Note: multistage build could work if api is compiled

FROM python:3.11-slim 

LABEL name="AI-OPS API" \
    src="https://github.com/antoninoLorenzo/AI-OPS" \
    creator="antoninoLorenzo"

ARG ollama_endpoint=http://localhost:11434
ARG ollama_model=mistral

COPY . /AI-OPS
ENV PATH="/AI-OPS/.venv/bin:$PATH"
RUN python3 -m venv /AI-OPS/.venv && \
    pip3 install --no-cache-dir -Ur /AI-OPS/requirements-api.txt && \
    python3 -m spacy download en_core_web_md

ENV MODEL=${ollama_model}
ENV ENDPOINT=${ollama_endpoint}

VOLUME ["/.aiops"]
EXPOSE 8000

CMD ["fastapi", "dev", "--host", "0.0.0.0", "./AI-OPS/src/api.py"]

# docker build -t ai-ops:api-dev --build-arg ollama_endpoint=ENDPOINT .
# docker run -p 8000:8000 ai-ops:api-dev
