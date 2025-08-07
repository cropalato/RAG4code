# Dockerfile
FROM python:3.11-slim

# Metadados
LABEL maintainer="CodeRAG System"
LABEL version="1.0"
LABEL description="Sistema RAG para análise de código usando Ollama + ChromaDB"

# Variáveis de ambiente padrão
ENV PYTHONUNBUFFERED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  PIP_NO_CACHE_DIR=1 \
  PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
  curl \
  git \
  && rm -rf /var/lib/apt/lists/*

# Criar diretórios de trabalho
RUN mkdir -p /app /data /projects /chroma_db
WORKDIR /app

# Copiar requirements primeiro (para cache do Docker)
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY code_rag_docker.py ./code_rag.py
COPY interactive_docker.py ./interactive.py
COPY web_api.py .
COPY entrypoint.sh .
COPY healthcheck.sh .

# Tornar scripts executáveis
RUN chmod +x entrypoint.sh healthcheck.sh

# Criar usuário não-root
RUN groupadd -r coderag && useradd -r -g coderag -d /app -s /bin/bash coderag
RUN chown -R coderag:coderag /app /data /projects /chroma_db

# Expor porta para API web
EXPOSE 8080

# Configurar healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD ["./healthcheck.sh"]

# Mudar para usuário não-root
USER coderag

# Ponto de entrada
ENTRYPOINT ["./entrypoint.sh"]
CMD ["web"]
