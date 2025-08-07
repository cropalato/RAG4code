# 🤖 CodeRAG Docker - Code Analysis System

Complete RAG (Retrieval-Augmented Generation) system for code analysis using Ollama, with support for multiple vector database backends (ChromaDB and OpenSearch), fully containerized.

## 🚀 Quick Start

### 1. Prerequisites

```bash
# Install Docker and Docker Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install and start Ollama on host
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &

# Download required models
ollama pull nomic-embed-text
ollama pull qwen2.5-coder
```

### 2. Quick Setup

```bash
# Clone or download files
git clone <repo> # or download files manually
cd coderag-docker

# Initial setup
make setup

# Place projects in folder
cp -r /caminho/seus/projetos ./projects/

# Start system
make run
```

### 3. Access Interface

- **Interface Web**: http://localhost:8080
- **Logs**: `make logs`
- **Shell**: `make shell`

## 🗄️ Vector Database Backends

This system supports two vector database backends:

### ChromaDB (Default)
- **Usage**: Local, embeddings and data stored in Docker volume
- **Advantages**: Simple, fast setup, great for development
- **Configuration**: `VECTOR_DB_TYPE=chroma` (default)

### OpenSearch
- **Usage**: Remote cluster, hybrid search (vector + text)
- **Advantages**: Scalable, advanced search, ideal for production
- **Configuration**: `VECTOR_DB_TYPE=opensearch`

### Comparison and When to Use

| Aspecto               | ChromaDB                | OpenSearch               |
| --------------------- | ----------------------- | ------------------------ |
| **Setup**             | ✅ Simples              | ⚙️ Requer cluster         |
| **Performance**       | ✅ Rápido (local)       | ⚡ Escalável              |
| **Busca**             | 🔍 Vetorial             | 🔍🔤 Híbrida (vet+text)   |
| **Ideal for**         | Development/Testing     | Production/Large volumes |
| **Dependencies**      | 📦 Docker Volume        | 🌐 External cluster        |
| **Resources**         | 💻 Low                 | 🖥️ Configurable           |

## 📁 Estrutura de Arquivos

```
coderag-docker/
├── Dockerfile                  # Imagem Docker
├── docker-compose.yml          # Orquestração
├── code_rag_docker.py         # Sistema RAG com ChromaDB
├── code_rag_opensearch.py     # Sistema RAG com OpenSearch
├── interactive_docker.py      # Modo interativo (suporta ambos backends)
├── web_api.py                 # API web com interface
├── entrypoint.sh              # Script de entrada
├── healthcheck.sh             # Health check
├── requirements.txt           # Dependências Python
├── Makefile                  # Comandos facilitados
├── .env.example              # Configurações exemplo
├── projects/                 # Seus projetos (volume)
└── README.md                # Esta documentação
```

## 🐳 Modos de Uso

### 1. Interface Web (Recomendado)

```bash
make run
# Acesse: http://localhost:8080
```

**Recursos da interface:**

- 💬 Fazer perguntas sobre código
- 📁 Indexar projetos via dropdown
- 📊 Ver estatísticas em tempo real
- 📂 Gerenciar projetos

### 2. Linha de Comando

```bash
# Indexar projeto
make index PROJECT=meu-projeto

# Fazer pergunta
make ask QUESTION="Como funciona a autenticação?"

# Ver estatísticas
make stats

# Listar projetos
make projects
```

### 3. Modo Interativo

```bash
# ChromaDB (padrão)
make interactive

# OpenSearch
VECTOR_DB_TYPE=opensearch make interactive
```

**Recursos do modo interativo:**
- 🔄 Seleção automática do backend baseada em `VECTOR_DB_TYPE`
- 📊 Exibição clara do backend ativo
- 🛠️ Comandos específicos por backend (clear_collection vs clear_index)

### 4. Docker Run Direto

#### ChromaDB (Local)
```bash
# API Web
docker run -d \
  -p 8080:8080 \
  -e VECTOR_DB_TYPE=chroma \
  -v ./projects:/projects:ro \
  -v coderag_data:/data \
  -v coderag_chroma:/chroma_db \
  --add-host=host.docker.internal:host-gateway \
  coderag web

# Modo Interativo
docker run -it --rm \
  -e VECTOR_DB_TYPE=chroma \
  -v ./projects:/projects:ro \
  -v coderag_data:/data \
  -v coderag_chroma:/chroma_db \
  --add-host=host.docker.internal:host-gateway \
  coderag python interactive_docker.py
```

#### OpenSearch (Remoto)
```bash
# API Web
docker run -d \
  -p 8080:8080 \
  -e VECTOR_DB_TYPE=opensearch \
  -e OPENSEARCH_HOST=your-opensearch-host \
  -e OPENSEARCH_USER=admin \
  -e OPENSEARCH_PASSWORD=admin \
  -v ./projects:/projects:ro \
  -v coderag_data:/data \
  --add-host=host.docker.internal:host-gateway \
  coderag web

# Modo Interativo
docker run -it --rm \
  -e VECTOR_DB_TYPE=opensearch \
  -e OPENSEARCH_HOST=your-opensearch-host \
  -e OPENSEARCH_USER=admin \
  -e OPENSEARCH_PASSWORD=admin \
  -v ./projects:/projects:ro \
  -v coderag_data:/data \
  --add-host=host.docker.internal:host-gateway \
  coderag python interactive_docker.py
```

## ⚙️ Configuração

### Variáveis de Ambiente Principais

#### Configurações Gerais
| Variável             | Padrão                              | Descrição                     |
| -------------------- | ----------------------------------- | ----------------------------- |
| `VECTOR_DB_TYPE`     | `chroma`                            | Backend: `chroma` ou `opensearch` |
| `OLLAMA_HOST`        | `http://host.docker.internal:11434` | URL do servidor Ollama        |
| `EMBEDDING_MODEL`    | `nomic-embed-text`                  | Modelo para embeddings        |
| `CHAT_MODEL`         | `qwen2.5-coder`                     | Modelo para chat/respostas    |
| `CHUNK_SIZE`         | `1500`                              | Tamanho dos chunks de código  |
| `MAX_CONTEXT_CHUNKS` | `5`                                 | Chunks enviados para contexto |
| `FILE_PATTERNS`      | `*.py,*.js,*.ts,...`                | Padrões de arquivos a indexar |
| `IGNORE_PATTERNS`    | `node_modules,.git,...`             | Padrões a ignorar             |

#### ChromaDB Específicas
| Variável             | Padrão                              | Descrição                     |
| -------------------- | ----------------------------------- | ----------------------------- |
| `COLLECTION_NAME`    | `code_project`                      | Nome da coleção no ChromaDB   |
| `CHROMA_DB_PATH`     | `/chroma_db`                        | Caminho do banco ChromaDB     |

#### OpenSearch Específicas
| Variável                 | Padrão              | Descrição                         |
| ------------------------ | ------------------- | --------------------------------- |
| `OPENSEARCH_INDEX`       | `code-rag-index`    | Nome do índice OpenSearch         |
| `OPENSEARCH_HOST`        | `localhost`         | Host do cluster OpenSearch        |
| `OPENSEARCH_PORT`        | `9200`              | Porta do cluster OpenSearch       |
| `OPENSEARCH_USER`        | `admin`             | Usuário para autenticação         |
| `OPENSEARCH_PASSWORD`    | `admin`             | Senha para autenticação           |
| `OPENSEARCH_USE_SSL`     | `false`             | Usar SSL/TLS                      |
| `OPENSEARCH_VERIFY_CERTS`| `false`             | Verificar certificados SSL        |

### Arquivo .env

```bash
# Copiar exemplo e editar
cp .env.example .env
nano .env
```

## 📊 Volumes Docker

| Volume           | Caminho      | Descrição                           | Backend     |
| ---------------- | ------------ | ----------------------------------- | ----------- |
| `./projects`     | `/projects`  | Seus projetos de código (read-only) | Ambos       |
| `coderag_data`   | `/data`      | Logs e dados da aplicação           | Ambos       |
| `coderag_chroma` | `/chroma_db` | Banco vetorial ChromaDB (local)     | ChromaDB    |

**Nota**: Para OpenSearch, os dados são armazenados no cluster remoto, não necessitando volume local.

## 🔧 Comandos Úteis

### Desenvolvimento

```bash
# Build para desenvolvimento
make dev-build
make dev-run

# Logs em tempo real
make logs

# Shell no container
make shell
```

### Manutenção

```bash
# Limpar tudo (CUIDADO: remove volumes!)
make clean

# Apenas parar
make stop

# Reiniciar
make stop && make run
```

### Debugging

```bash
# Ver logs específicos
docker-compose logs coderag

# Verificar saúde
docker-compose ps

# Exec comandos
docker-compose exec coderag python code_rag.py stats
```

## 🚨 Troubleshooting

### Problema: "Erro ao conectar com Ollama"

```bash
# Verificar se Ollama está rodando no host
ollama serve

# Verificar se modelos estão baixados
ollama list

# Testar conexão
curl http://localhost:11434/api/tags
```

### Problema: "Erro ao conectar OpenSearch"

```bash
# Verificar se OpenSearch está acessível
curl -u admin:admin http://your-opensearch-host:9200

# Testar credenciais
curl -u admin:admin http://your-opensearch-host:9200/_cluster/health

# Verificar variáveis de ambiente
echo $OPENSEARCH_HOST
echo $OPENSEARCH_USER
echo $OPENSEARCH_PASSWORD
```

### Problema: "Backend não suportado"

```bash
# Verificar variável de ambiente
echo $VECTOR_DB_TYPE

# Definir backend correto
export VECTOR_DB_TYPE=chroma
# ou
export VECTOR_DB_TYPE=opensearch
```

### Problema: "Nenhum projeto encontrado"

```bash
# Verificar se projetos estão no local correto
ls -la ./projects/

# Verificar permissões
chmod -R 755 ./projects/
```

### Problema: "Container não inicia"

```bash
# Ver logs detalhados
make logs

# Verificar configuração
docker-compose config

# Verificar recursos
docker system df
```

### Problema: Performance lenta

```bash
# Ajustar chunk size
export CHUNK_SIZE=1000

# Reduzir contexto
export MAX_CONTEXT_CHUNKS=3

# Verificar recursos da máquina
docker stats
```

## 📈 Otimização

### Para Projetos Grandes

```bash
# Aumentar timeout
REQUEST_TIMEOUT=300

# Chunk size maior
CHUNK_SIZE=2000

# Mais contexto
MAX_CONTEXT_CHUNKS=10
```

### Para Máquinas Menores

```bash
# Chunk size menor
CHUNK_SIZE=800

# Menos contexto
MAX_CONTEXT_CHUNKS=3

# Filtros mais específicos
FILE_PATTERNS="*.py,*.js"
```

## 🔐 Segurança

- ✅ **Execução como usuário não-root**
- ✅ **Volumes read-only para projetos**
- ✅ **Dados persistentes isolados**
- ✅ **Sem acesso à internet dos containers**
- ✅ **Health checks configurados**

## 🆕 Recursos Avançados

### Multi-modelo

```bash
# Usar modelos diferentes por projeto
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CHAT_MODEL=codellama:7b
```

### Filtros Customizados

```bash
# Apenas Python e JavaScript
FILE_PATTERNS="*.py,*.js,*.ts"

# Ignorar testes
IGNORE_PATTERNS="*test*,*spec*,__pycache__"
```

### API Customizada

```python
# Estender web_api.py
@app.route('/api/custom')
def custom_endpoint():
    return jsonify({"custom": "response"})
```

## 🤝 Contribuição

1. Fork do projeto
2. Criar branch: `git checkout -b feature/nova-funcionalidade`
3. Commit: `git commit -m 'Add nova funcionalidade'`
4. Push: `git push origin feature/nova-funcionalidade`
5. Pull Request

## 📄 Licença

MIT License - veja LICENSE para detalhes.
